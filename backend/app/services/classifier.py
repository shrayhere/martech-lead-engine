"""AI lead classification: persona, buying role and interest from the job title, then business rules
that turn the labels (plus the lead score band) into a recommended next action.

Two engines:
  local  - scikit-learn text classifier (word + character n-gram TF-IDF, logistic regression) trained on
           app/ml/title_labels_train.csv. Always available, no API key, no cost.
  claude - Claude (Anthropic API) labels each distinct job title using the same label definitions.
           Used only when an Anthropic credential is configured (ANTHROPIC_API_KEY); every title Claude
           cannot label falls back to the local model.

Accuracy is measured on app/ml/title_labels_test.csv, a held-out set whose titles never appear in the
training file (see evaluate_classifier.py and docs/classification_evaluation.md). Both label files were
written by hand for this project from the definitions in LABEL_DEFINITIONS below; they are not real
CRM outcomes.
"""
import csv
import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.cleaning_service import JUNK_PLACEHOLDERS

ML_DIR = os.path.join(os.path.dirname(__file__), "..", "ml")
TRAIN_FILE = os.path.join(ML_DIR, "title_labels_train.csv")
TEST_FILE = os.path.join(ML_DIR, "title_labels_test.csv")

TARGETS = ("persona", "buying_role", "interest")
LABELS = {
    "persona": ["Executive", "Marketing", "Sales", "Technical", "Product", "Operations", "Unknown"],
    "buying_role": ["Decision Maker", "Influencer", "End User", "Unknown"],
    "interest": ["Demand Generation", "Sales Productivity", "Technical Integration", "Data & Analytics",
                 "Business Strategy & ROI", "Unknown"],
}
LABEL_DEFINITIONS = """\
persona (the person's function):
  Executive  - C-suite, founder, owner, president, managing director/partner, general manager
  Marketing  - marketing, growth, demand gen, content, brand, PR, social, SEO (not marketing operations)
  Sales      - sales, business development, account management, partnerships, customer success
  Technical  - engineering, IT, security, architecture, DevOps, data science / data engineering
  Product    - product management, product owner, UX / product design and research
  Operations - revenue/sales/marketing operations, CRM admins, business analysts, finance, procurement,
               HR, office administration, chief of staff
  Unknown    - placeholder, junk, student or no usable title
buying_role (influence on a B2B purchase):
  Decision Maker - C-level, founder, owner, president, partner, general manager, VP/SVP/EVP, "Head of"
  Influencer     - director, senior manager, manager of a team, lead, principal/staff, architect,
                   controller, chief of staff
  End User       - individual contributors: specialist, coordinator, analyst, engineer, developer,
                   designer, rep, associate, account executive, account/customer success manager,
                   administrator, assistant
  Unknown        - no usable title
interest (what the lead most likely cares about, from the function):
  Demand Generation       - marketing functions (incl. CMO)
  Sales Productivity      - sales, business development, customer success (incl. CRO)
  Technical Integration   - engineering, IT, security, product, design (incl. CTO, CIO, CISO, CPO)
  Data & Analytics        - data science/engineering, BI, analytics, revenue/sales/marketing operations, CRM admin
  Business Strategy & ROI - CEO, COO, CFO, founders, general management, finance, procurement, HR, admin
  Unknown                 - no usable title
"""

ABBREVIATIONS = {
    r"\bvp\b": "vice president", r"\bsvp\b": "senior vice president", r"\bevp\b": "executive vice president",
    r"\bavp\b": "assistant vice president", r"\bsr\b": "senior", r"\bjr\b": "junior", r"\bmgr\b": "manager",
    r"\bdir\b": "director", r"\bops\b": "operations", r"\brevops\b": "revenue operations",
    r"\bsdr\b": "sales development representative", r"\bbdr\b": "business development representative",
    r"\brep\b": "representative", r"\badmin\b": "administrator", r"\bbi\b": "business intelligence",
    r"\bit\b": "information technology", r"\bux\b": "user experience", r"\bui\b": "user interface",
}


@lru_cache(maxsize=20000)
def normalize_title(title: Optional[str]) -> str:
    t = (title or "").lower()
    t = re.sub(r"[&/,\-()|.]", " ", t)
    for pattern, repl in ABBREVIATIONS.items():
        t = re.sub(pattern, repl, t)
    return re.sub(r"\s+", " ", t).strip()


def is_unusable_title(title: Optional[str]) -> bool:
    t = (title or "").strip().lower()
    return not t or t in JUNK_PLACEHOLDERS or len(re.sub(r"[^a-z]", "", t)) < 2


def load_labeled(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def _local_models():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer

    rows = load_labeled(TRAIN_FILE)
    x = [normalize_title(r["title"]) for r in rows]
    models = {}
    for target in TARGETS:
        model = Pipeline([
            ("features", FeatureUnion([
                ("words", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True)),
                ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
            ])),
            ("clf", LogisticRegression(C=20.0, max_iter=5000, class_weight="balanced")),
        ])
        model.fit(x, [r[target] for r in rows])
        models[target] = model
    return models


def classify_titles_local(titles: List[str]) -> List[Dict[str, Any]]:
    out: List[Optional[Dict[str, Any]]] = [None] * len(titles)
    todo = []
    for i, t in enumerate(titles):
        if is_unusable_title(t):
            out[i] = {"persona": "Unknown", "buying_role": "Unknown", "interest": "Unknown",
                      "confidence": 1.0, "engine": "rule"}
        else:
            todo.append(i)
    if todo:
        models = _local_models()
        # Predict each distinct normalised title once (lead lists repeat the same titles many times)
        distinct = sorted({normalize_title(titles[i]) for i in todo})
        preds = {}
        for target, model in models.items():
            probs = model.predict_proba(distinct)
            classes = model.classes_
            preds[target] = {d: (str(classes[p.argmax()]), float(p.max())) for d, p in zip(distinct, probs)}
        for i in todo:
            key = normalize_title(titles[i])
            labels = {t: preds[t][key][0] for t in TARGETS}
            conf = round(sum(preds[t][key][1] for t in TARGETS) / len(TARGETS), 3)
            out[i] = {**labels, "confidence": conf, "engine": "local"}
    return out  # type: ignore[return-value]


# ----------------------------------------------------------------------------- Claude engine
CLAUDE_MODEL = "claude-opus-5-5"
CLAUDE_BATCH = 40


def claude_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _claude_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer"},
                        "persona": {"type": "string", "enum": LABELS["persona"]},
                        "buying_role": {"type": "string", "enum": LABELS["buying_role"]},
                        "interest": {"type": "string", "enum": LABELS["interest"]},
                    },
                    "required": ["index", "persona", "buying_role", "interest"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["labels"],
        "additionalProperties": False,
    }


SYSTEM_PROMPT = ("You label B2B job titles for a lead-routing system. Apply these definitions exactly; when a "
                 "title mixes signals, the seniority word decides buying_role and the function decides persona "
                 "and interest. Return one entry per input index.\n\n" + LABEL_DEFINITIONS)


def classify_titles_claude(titles: List[str], client: Any = None) -> List[Dict[str, Any]]:
    """Labels each distinct usable title with Claude; anything Claude does not return falls back to local."""
    results = classify_titles_local(titles)  # baseline + fallback
    distinct = sorted({t.strip() for t in titles if not is_unusable_title(t)})
    if not distinct:
        return results
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    labelled: Dict[str, Dict[str, str]] = {}
    for start in range(0, len(distinct), CLAUDE_BATCH):
        batch = distinct[start:start + CLAUDE_BATCH]
        listing = "\n".join(f"{i}: {t}" for i, t in enumerate(batch))
        # Server-side fallback: if Claude Opus 5.5 declines, the API retries on its default fallback model.
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _claude_schema()}},
            messages=[{"role": "user", "content": f"Label these job titles:\n{listing}"}],
        )
        if getattr(response, "stop_reason", None) in ("refusal", "max_tokens"):
            continue  # keep the local labels for this batch
        text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
        if not text:
            continue
        for item in json.loads(text).get("labels", []):
            idx = item.get("index")
            if isinstance(idx, int) and 0 <= idx < len(batch):
                labelled[batch[idx]] = {t: item[t] for t in TARGETS}

    for i, t in enumerate(titles):
        key = (t or "").strip()
        if key in labelled:
            results[i] = {**labelled[key], "confidence": None, "engine": "claude"}
    return results


# ----------------------------------------------------------------------------- business rules
def recommend_action(persona: str, buying_role: str, interest: str, band: Optional[str],
                     is_junk: bool = False) -> str:
    """Business rules: (buying role x score band) decides the motion; interest picks the content."""
    if is_junk:
        return "Exclude: junk record"
    if buying_role == "Unknown" or persona == "Unknown":
        return "Enrich: find a real job title before outreach"
    topic = {"Demand Generation": "pipeline-growth", "Sales Productivity": "sales-efficiency",
             "Technical Integration": "integration/API", "Data & Analytics": "reporting & data-quality",
             "Business Strategy & ROI": "ROI"}.get(interest, "product")
    band = band or "Unscored"
    if buying_role == "Decision Maker":
        return {"Hot": "Route to account executive: book a discovery call within 24 hours",
                "Warm": f"Executive outreach with a case study on {topic}; follow up in 3 days",
                "Cold": "Add to the monthly executive nurture",
                }.get(band, f"Score first; then executive outreach with a case study on {topic}")
    if buying_role == "Influencer":
        return {"Hot": "SDR call this week: qualify the need and ask who signs off",
                "Warm": f"Nurture with {topic} content and offer a demo",
                "Cold": f"Add to the {topic} educational nurture",
                }.get(band, f"Score first; then nurture with {topic} content")
    # End User
    return {"Hot": "Offer a product trial and ask the user to introduce the decision maker",
            "Warm": f"Send {topic} how-to content; invite to a webinar",
            "Cold": f"Add to the {topic} newsletter",
            }.get(band, f"Score first; then send {topic} how-to content")


# ----------------------------------------------------------------------------- lead classification
def label_lead_dicts(leads: List[Dict[str, Any]]) -> None:
    """In-memory variant used by the pipeline before its bulk insert (local engine)."""
    labels = classify_titles_local([l.get("job_title") or "" for l in leads])
    for lead, lab in zip(leads, labels):
        lead.update({"persona": lab["persona"], "buying_role": lab["buying_role"], "interest": lab["interest"],
                     "classification_confidence": lab["confidence"], "classification_engine": lab["engine"]})
        lead["recommended_action"] = recommend_action(lab["persona"], lab["buying_role"], lab["interest"],
                                                      lead.get("score_band"), bool(lead.get("is_junk")))


def classify_leads(db, run_id: Optional[str] = None, engine: str = "local", client: Any = None) -> Dict[str, Any]:
    from app.models.schemas import CleanLead

    q = db.query(CleanLead)
    q = q.filter(CleanLead.run_id == run_id) if run_id else q.filter(CleanLead.run_id.is_(None))
    leads = q.all()
    if not leads:
        return {"error": "No clean leads found. Run cleaning (or a Smart Upload) first."}
    if engine == "claude" and not (client or claude_available()):
        return {"error": "Claude engine needs ANTHROPIC_API_KEY on the server. Use engine=local or set the key."}

    titles = [l.job_title or "" for l in leads]
    labels = classify_titles_claude(titles, client) if engine == "claude" else classify_titles_local(titles)

    dist = {t: {} for t in TARGETS}
    actions: Dict[str, int] = {}
    engines: Dict[str, int] = {}
    for lead, lab in zip(leads, labels):
        lead.persona, lead.buying_role, lead.interest = lab["persona"], lab["buying_role"], lab["interest"]
        lead.classification_confidence = lab["confidence"]
        lead.classification_engine = lab["engine"]
        lead.recommended_action = recommend_action(lab["persona"], lab["buying_role"], lab["interest"],
                                                   lead.score_band, bool(lead.is_junk))
        for t in TARGETS:
            dist[t][lab[t]] = dist[t].get(lab[t], 0) + 1
        actions[lead.recommended_action] = actions.get(lead.recommended_action, 0) + 1
        engines[lab["engine"]] = engines.get(lab["engine"], 0) + 1
    db.commit()
    return {"success": True, "engine_requested": engine, "engines_used": engines, "leads_classified": len(leads),
            "distribution": dist, "actions": dict(sorted(actions.items(), key=lambda kv: -kv[1]))}


def evaluate(engine: str = "local", client: Any = None) -> Dict[str, Any]:
    """Accuracy on the held-out test titles (titles that never appear in the training file)."""
    train_titles = {normalize_title(r["title"]) for r in load_labeled(TRAIN_FILE)}
    test = load_labeled(TEST_FILE)
    overlap = [r["title"] for r in test if normalize_title(r["title"]) in train_titles]
    titles = [r["title"] for r in test]
    preds = classify_titles_claude(titles, client) if engine == "claude" else classify_titles_local(titles)
    acc = {}
    errors = []
    for t in TARGETS:
        correct = sum(1 for r, p in zip(test, preds) if r[t] == p[t])
        acc[t] = round(100.0 * correct / len(test), 1)
    all_three = sum(1 for r, p in zip(test, preds) if all(r[t] == p[t] for t in TARGETS))
    for r, p in zip(test, preds):
        wrong = {t: (r[t], p[t]) for t in TARGETS if r[t] != p[t]}
        if wrong:
            errors.append({"title": r["title"], "expected_vs_predicted": wrong})
    return {"engine": engine, "test_titles": len(test), "train_titles": len(train_titles),
            "titles_also_in_training": overlap, "accuracy_pct": acc,
            "all_three_correct_pct": round(100.0 * all_three / len(test), 1), "errors": errors}


def label_counts(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, int]]:
    out = {t: {} for t in TARGETS}
    for r in rows:
        for t in TARGETS:
            out[t][r[t]] = out[t].get(r[t], 0) + 1
    return out
