"""Data-quality score: per-field checks, an overall 0-100 score, the top 5 issues, and before/after numbers.

"Before" is measured on the records as they arrived (raw_leads for the staged flow, the mapped CSV rows for a
pipeline run, captured at run time). "After" is measured on the active (non-junk) clean_leads.

The overall score is the average pass rate of eight checks that apply to both sides:
valid email, phone in E.164, standardised US state, job title present, company present, industry present,
not an exact duplicate, not junk. Country and owner are reported separately and are NOT in the score:
raw files have no owner, and the sample file has no country column, so including them would only measure
which columns a file happens to have.
"""
import json
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.schemas import CleanLead, PipelineRun, RawLead
from app.services.cleaning_service import JUNK_PLACEHOLDERS, US_STATES_MAP, is_junk_lead

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
US_CODES = set(US_STATES_MAP.values())

SCORE_CHECKS = [
    ("valid_email", "Invalid or missing email"),
    ("phone_e164", "Phone missing or not in E.164 format"),
    ("state_standard", "State missing or not a 2-letter US code"),
    ("has_job_title", "Missing job title"),
    ("has_company", "Missing company"),
    ("has_industry", "Missing industry"),
    ("not_duplicate", "Exact duplicate (same email or phone as another record)"),
    ("not_junk", "Junk or placeholder record"),
]
EXTRA_CHECKS = [
    ("has_country", "Missing country"),
    ("has_owner", "No owner (sales rep) assigned"),
]


def _present(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    return bool(s) and s.lower() not in JUNK_PLACEHOLDERS and s.lower() not in {"nan", "none", "unknown"}


def _digits(phone: Any) -> str:
    return re.sub(r"\D", "", str(phone or ""))


def _record(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    return {c: getattr(obj, c, None) for c in (
        "first_name", "last_name", "email", "company", "job_title", "phone", "state", "country",
        "industry", "assigned_rep_id", "is_junk")}


def compute_quality(records: Iterable[Any], include_owner: bool) -> Dict[str, Any]:
    """Measures a list of lead records (dicts or ORM rows)."""
    rows = [_record(r) for r in records]
    total = len(rows)
    if total == 0:
        return {"total_records": 0, "score": None, "metrics": {}, "issue_counts": {}, "top_issues": []}

    # Exact-duplicate detection inside this set: a record is a duplicate if an earlier record
    # has the same (lower-cased) email or the same phone digits.
    seen_email, seen_phone = set(), set()
    passed = Counter()
    for r in rows:
        email = (r.get("email") or "").strip().lower()
        digits = _digits(r.get("phone"))
        digits = digits[-10:] if len(digits) >= 10 else digits
        dup = bool((email and email in seen_email) or (len(digits) >= 7 and digits in seen_phone))
        if email:
            seen_email.add(email)
        if len(digits) >= 7:
            seen_phone.add(digits)

        junk = r.get("is_junk")
        if junk is None:
            junk = is_junk_lead(r.get("first_name"), r.get("last_name"), email, r.get("company"),
                                r.get("phone"))[0]

        checks = {
            "valid_email": bool(email and EMAIL_RE.match(email)),
            "phone_e164": bool(r.get("phone") and E164_RE.match(str(r.get("phone")).strip())),
            "state_standard": str(r.get("state") or "").strip() in US_CODES,
            "has_job_title": _present(r.get("job_title")),
            "has_company": _present(r.get("company")),
            "has_industry": _present(r.get("industry")),
            "not_duplicate": not dup,
            "not_junk": not junk,
            "has_country": _present(r.get("country")),
            "has_owner": r.get("assigned_rep_id") is not None,
        }
        for k, ok in checks.items():
            if ok:
                passed[k] += 1

    def pct(k):
        return round(100.0 * passed[k] / total, 1)

    metrics = {k: pct(k) for k, _ in SCORE_CHECKS + EXTRA_CHECKS}
    if not include_owner:
        metrics["has_owner"] = None
    score = round(sum(metrics[k] for k, _ in SCORE_CHECKS) / len(SCORE_CHECKS), 1)

    issue_counts = {}
    for k, label in SCORE_CHECKS + EXTRA_CHECKS:
        if k == "has_owner" and not include_owner:
            continue
        failed = total - passed[k]
        if failed:
            issue_counts[label] = failed
    top = sorted(issue_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {
        "total_records": total,
        "score": score,
        "metrics": metrics,
        # Convenience fields named the way the internship plan asks for them
        "valid_email_pct": metrics["valid_email"],
        "missing_country_pct": round(100.0 - metrics["has_country"], 1),
        "missing_owner_pct": None if metrics["has_owner"] is None else round(100.0 - metrics["has_owner"], 1),
        "issue_counts": issue_counts,
        "top_issues": [{"issue": k, "records": v, "pct": round(100.0 * v / total, 1)} for k, v in top],
    }


def quality_report(db: Session, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Before/after data-quality report for the staged flow (run_id=None) or one pipeline run."""
    after_rows = db.query(CleanLead).filter(CleanLead.run_id == run_id).all() if run_id else \
        db.query(CleanLead).filter(CleanLead.run_id.is_(None)).all()
    active = [r for r in after_rows if not r.is_junk]
    junk_flagged = len(after_rows) - len(active)

    before: Optional[Dict[str, Any]] = None
    if run_id:
        run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if run and run.summary:
            before = json.loads(run.summary).get("quality_before")
    else:
        raw = db.query(RawLead).filter(RawLead.run_id.is_(None)).all()
        if raw:
            before = compute_quality(raw, include_owner=False)

    after = compute_quality(active, include_owner=True) if active else None
    return {
        "source": run_id or "staged",
        "before": before,
        "after": after,
        "junk_flagged_and_excluded": junk_flagged,
        "score_improvement": (round(after["score"] - before["score"], 1)
                              if before and after and before.get("score") is not None else None),
        "score_definition": ("Average pass rate of 8 checks: valid email, phone in E.164, 2-letter US state, "
                             "job title, company, industry, not an exact duplicate, not junk. Country and owner "
                             "are shown separately and are not part of the score."),
    }


def quality_before_from_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Used by the pipeline to capture the 'before' side at run time (the raw file is not stored)."""
    return compute_quality(records, include_owner=False)
