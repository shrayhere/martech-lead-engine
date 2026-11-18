"""Compute every number quoted in the architecture report from a real run of the code.

Runs on a throw-away SQLite database (never the main one):
  sample CSV -> /api/leads/upload -> /api/leads/clean -> /api/leads/assign
plus the deduplication evaluation in evaluate_dedup.py.
"""
import os
import re
import sys
import tempfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def collect():
    tmp = tempfile.mkdtemp(prefix="martech_report_")
    os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tmp, "report.db").replace("\\", "/")

    from fastapi.testclient import TestClient
    from rapidfuzz import fuzz

    import evaluate_dedup as ev
    from app.database import SessionLocal
    from app.main import app
    from app.models.schemas import AssignmentLog, CleanLead, RawLead
    from app.services.match_rules import composite_string, fuzzy_match

    m = {}
    # ---- deduplication accuracy -------------------------------------------------------------
    leads = ev.prepared_leads()
    truth = ev.true_pairs(leads)
    by_row = {l["row_index"]: l for l in leads}
    m["planted_pairs"] = len(truth)
    m["eval"] = []
    for rule, fn in (("Old (composite only)", ev.old_rule_pairs), ("New (guarded)", ev.new_rule_pairs)):
        for t in ev.THRESHOLDS:
            pred, _ = fn(leads, t)
            tp, fp, fn_, p, r = ev.metrics(pred, truth)
            m["eval"].append((rule, t, tp, fp, fn_, p, r))
    old_pred, _ = ev.old_rule_pairs(leads, 85.0)
    wrong = []
    for a, b in sorted(old_pred - truth):
        la, lb = by_row[a], by_row[b]
        wrong.append((round(fuzz.token_sort_ratio(composite_string(la), composite_string(lb)), 1),
                      f"{la['first_name']} {la['last_name']} | {la['company']}",
                      f"{lb['first_name']} {lb['last_name']} | {lb['company']}"))
    m["old_wrong_merges"] = sorted(wrong)
    _, logs = ev.new_rule_pairs(leads, 85.0)
    m["new_merges"] = len(logs)
    m["new_exact_merges"] = sum(1 for x in logs if x["merge_reason"].startswith("Exact"))
    # fuzzy-path examples (constructed pairs with no shared email/phone)
    examples = [
        ({"first_name": "Jonathan", "last_name": "Smith", "company": "Acme Corp", "email": "jonathan.smith@acmecorp.com"},
         {"first_name": "Jonathon", "last_name": "Smith", "company": "Acme Corporation", "email": "jonathon.smith@acmecorp.com"}),
        ({"first_name": "Jordan", "last_name": "Davis", "company": "TechFlow Inc", "email": "jordan.davis@techflowinc.com"},
         {"first_name": "Jordan", "last_name": "Davis", "company": "TechFlow Corporation", "email": "jordan.davis.lead@techflowinc.com"}),
    ]
    m["fuzzy_examples"] = [(fuzzy_match(a, b, 85.0), a, b) for a, b in examples]

    # ---- end-to-end legacy pipeline ---------------------------------------------------------
    client = TestClient(app)
    csv = client.get("/api/leads/sample-csv").content
    client.post("/api/leads/upload", files={"file": ("sample.csv", csv, "text/csv")})
    clean = client.post("/api/leads/clean").json()
    client.post("/api/leads/assign")
    m["clean"] = clean
    db = SessionLocal()
    try:
        raw = db.query(RawLead).all()
        cl = db.query(CleanLead).all()
        valid = [c for c in cl if not c.is_junk]
        m["raw_count"] = len(raw)
        m["clean_count"] = len(cl)
        m["junk_count"] = len(cl) - len(valid)
        raw_phones = [r.phone for r in raw if r.phone]
        m["raw_phone_e164"] = sum(1 for p in raw_phones if re.fullmatch(r"\+\d{8,15}", str(p))) / max(1, len(raw_phones))
        phones = [c.phone for c in valid if c.phone]
        m["phone_e164"] = sum(1 for p in phones if re.fullmatch(r"\+\d{8,15}", p)) / max(1, len(phones))
        raw_states = [r.state for r in raw if r.state]
        m["raw_state_codes"] = sum(1 for s in raw_states if re.fullmatch(r"[A-Z]{2}", s)) / max(1, len(raw_states))
        states = [c.state for c in valid if c.state]
        m["state_codes"] = sum(1 for s in states if re.fullmatch(r"[A-Z]{2}", s)) / max(1, len(states))
        rules = Counter(a.rule_matched.split(":")[0] for a in db.query(AssignmentLog).all())
        m["assigned"] = sum(rules.values())
        m["rules"] = {k: v for k, v in sorted(rules.items())}
    finally:
        db.close()
    return m


if __name__ == "__main__":
    import json
    data = collect()
    data["fuzzy_examples"] = [(r, f"{a['first_name']} {a['last_name']}", f"{b['first_name']} {b['last_name']}")
                              for r, a, b in data["fuzzy_examples"]]
    print(json.dumps(data, indent=1, default=str))
