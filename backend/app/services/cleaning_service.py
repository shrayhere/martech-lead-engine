import re
import json
from datetime import datetime
from app.services.match_rules import fuzzy_match, REVIEW_BAND, auto_merge_min, classify_fuzzy_score
from sqlalchemy.orm import Session
from app.models.schemas import RawLead, CleanLead, MergedLeadLog, ReviewItem, AssignmentLog
from app.config import settings
from app.utils.geo_utils import (
    US_STATES_MAP,
    INDIAN_STATES,
    DISPOSABLE_DOMAINS,
    FAKE_NAMES,
    normalize_phone_intl,
    validate_email_intl,
    normalize_state_intl,
    detect_country,
    is_advanced_junk_lead
)

JUNK_PLACEHOLDERS = {
    'test', 'n/a', 'na', 'asdf', 'none', 'null', 'dummy', 'testing 123',
    'xyz', 'test company', 'asdf inc', 'dummy corp', 'noemail', 'n/a inc',
    'sample', 'unknown', 'bot', 'script', '0000000000', '1234567'
}

def normalize_state(state_raw: str, country_hint: str = None) -> str:
    st, _ = normalize_state_intl(state_raw, country_hint)
    return st

def normalize_phone(phone_raw: str, default_country: str = 'IN') -> str:
    return normalize_phone_intl(phone_raw, default_country)

def normalize_company(company_raw: str) -> str:
    if not company_raw:
        return None
    clean = company_raw.strip()
    if clean.isupper() or clean.islower():
        words = clean.split()
        capitalized = []
        for w in words:
            if w.upper() in {'AI', 'IT', 'SAAS', 'IP', 'LLC', 'INC', 'CORP', 'VP', 'CTO', 'CEO', 'PVT', 'LTD'}:
                capitalized.append(w.upper())
            else:
                capitalized.append(w.capitalize())
        return ' '.join(capitalized)
    return clean

def is_junk_lead(first_name: str, last_name: str, email: str, company: str, phone: str) -> tuple[bool, str]:
    is_junk, reason, _ = is_advanced_junk_lead(first_name, last_name, email, company, phone)
    return is_junk, reason

def calculate_completeness_score(lead) -> float:
    """Calculates data completeness percentage (0 to 100) based on key fields."""
    fields = [
        lead.first_name, lead.last_name, lead.email, lead.company,
        lead.job_title, lead.phone, lead.state, lead.industry, lead.company_size
    ]
    populated = sum(1 for f in fields if f is not None and str(f).strip() != "" and str(f).lower() != "unknown")
    return round((populated / len(fields)) * 100, 1)

def run_cleaning_pipeline(db: Session) -> dict:
    """
    Executes the full Data Quality & Fuzzy Deduplication Pipeline:
    1. Reads all raw_leads records.
    2. Normalizes state, phone, name, and company fields.
    3. Identifies junk rows.
    4. Groups duplicates: exact email/phone, or a guarded fuzzy match (see match_rules.py).
    5. Selects the most complete/recent lead in each cluster as winner (`clean_leads`).
    6. Archives secondary duplicates into `merged_leads_log`.
    7. Computes before/after completeness and duplicate metrics.
    """
    raw_leads = db.query(RawLead).all()
    if not raw_leads:
        return {"error": "No raw leads found. Please upload a CSV first."}

    # Clear the staged flow's previous results (pipeline runs, which carry a run_id, are left alone)
    db.query(MergedLeadLog).filter(MergedLeadLog.run_id.is_(None)).delete(synchronize_session=False)
    db.query(ReviewItem).filter(ReviewItem.run_id.is_(None)).delete(synchronize_session=False)
    db.query(AssignmentLog).filter(AssignmentLog.run_id.is_(None)).delete(synchronize_session=False)  # FK to clean_leads
    db.query(CleanLead).filter(CleanLead.run_id.is_(None)).delete(synchronize_session=False)
    db.commit()

    processed_records = []
    junk_count = 0
    total_fields_raw = 0
    populated_fields_raw = 0

    for r in raw_leads:
        fn = r.first_name.strip() if r.first_name else None
        ln = r.last_name.strip() if r.last_name else None
        em = r.email.strip().lower() if r.email else None
        comp = normalize_company(r.company)
        title = r.job_title.strip() if r.job_title else None
        ph = normalize_phone(r.phone)
        st = normalize_state(r.state)
        ind = r.industry.strip() if r.industry else None
        
        junk, junk_reason = is_junk_lead(fn, ln, em, comp, ph)
        if junk:
            junk_count += 1

        # Track raw completeness
        raw_fields = [r.first_name, r.last_name, r.email, r.company, r.job_title, r.phone, r.state, r.industry]
        total_fields_raw += len(raw_fields)
        populated_fields_raw += sum(1 for f in raw_fields if f and str(f).strip() and str(f).lower() not in JUNK_PLACEHOLDERS)

        processed_records.append({
            "raw_id": r.id,
            "first_name": fn,
            "last_name": ln,
            "email": em,
            "company": comp,
            "job_title": title,
            "phone": ph,
            "state": st,
            "industry": ind,
            "company_size": r.company_size,
            "engagement_score": r.engagement_score or 0.0,
            "last_activity_date": r.last_activity_date or "2025-01-01",
            "is_junk": junk,
            "junk_reason": junk_reason
        })

    # Cluster deduplication. Records merge on an exact email/phone match, or on a guarded fuzzy
    # match (same last name, near-identical first name, same company/domain, composite score >= threshold).
    # See app/services/match_rules.py and evaluate_dedup.py for the rule and its measured accuracy.
    
    threshold = settings.FUZZY_MATCH_THRESHOLD
    visited = set()
    clusters = []
    review_pairs = []  # borderline guarded fuzzy pairs (REVIEW_BAND) -> human review instead of auto-merge

    for i, lead in enumerate(processed_records):
        if i in visited:
            continue

        if lead["is_junk"]:
            # Junk rows form singletons
            clusters.append([lead])
            visited.add(i)
            continue

        cluster = [lead]
        visited.add(i)

        for j in range(i + 1, len(processed_records)):
            if j in visited:
                continue

            other = processed_records[j]
            if other["is_junk"]:
                continue

            if lead["email"] and lead["email"] == other["email"]:
                matched, similarity, reason = True, 100.0, f"Exact match on email address ({other['email']})"
            elif lead["phone"] and lead["phone"] == other["phone"]:
                matched, similarity, reason = True, 100.0, f"Exact match on phone number ({other['phone']})"
            else:
                passed, similarity, reason = fuzzy_match(lead, other, REVIEW_BAND[0])
                decision = classify_fuzzy_score(similarity, threshold) if passed else "none"
                if decision == "review":
                    review_pairs.append((lead, other, similarity, reason))
                matched = decision == "merge"
                reason = f"Fuzzy match: {reason}"

            if matched:
                other["similarity_with_winner"] = similarity
                other["match_reason"] = f"{reason}; matched against raw lead #{lead['raw_id']}"
                cluster.append(other)
                visited.add(j)

        clusters.append(cluster)

    # Process Clusters: Pick winner & archive duplicates
    clean_lead_objects = []
    merged_logs = []
    duplicate_clusters_count = 0
    duplicate_records_count = 0

    total_fields_clean = 0
    populated_fields_clean = 0

    for cluster in clusters:
        if len(cluster) > 1:
            duplicate_clusters_count += 1
            duplicate_records_count += (len(cluster) - 1)

            # Sort cluster by completeness score + engagement score + recency
            def score_lead_for_merge(item):
                # Calculate completeness ratio
                fields = [item["first_name"], item["last_name"], item["email"], item["company"], item["phone"], item["state"]]
                comp_ratio = sum(1 for f in fields if f) / len(fields)
                eng = item["engagement_score"] or 0
                return (comp_ratio * 10) + (eng / 10)

            cluster.sort(key=score_lead_for_merge, reverse=True)

        winner = cluster[0]
        cluster_id = f"CLUSTER-{winner['raw_id']}"

        clean_lead = CleanLead(
            raw_lead_id=winner["raw_id"],
            first_name=winner["first_name"],
            last_name=winner["last_name"],
            email=winner["email"],
            company=winner["company"],
            job_title=winner["job_title"],
            phone=winner["phone"],
            state=winner["state"],
            industry=winner["industry"],
            company_size=winner["company_size"],
            engagement_score=winner["engagement_score"],
            last_activity_date=winner["last_activity_date"],
            is_junk=winner["is_junk"],
            junk_reason=winner["junk_reason"],
            duplicate_cluster_id=cluster_id if len(cluster) > 1 else None,
            source_row=winner["raw_id"],
        )

        db.add(clean_lead)
        db.flush() # get winner clean_lead.id

        # Track clean completeness
        clean_fields = [winner["first_name"], winner["last_name"], winner["email"], winner["company"], winner["job_title"], winner["phone"], winner["state"], winner["industry"]]
        total_fields_clean += len(clean_fields)
        populated_fields_clean += sum(1 for f in clean_fields if f and str(f).strip())

        # Archive secondary duplicates into audit log
        for dup in cluster[1:]:
            # After sorting, the record that anchored the cluster can lose: it has no match_reason of its
            # own, so use the reason stored on the winner (which was matched against that anchor).
            if "match_reason" not in dup:
                dup["match_reason"] = winner.get("match_reason", "Matched")
                dup["similarity_with_winner"] = winner.get("similarity_with_winner", 100.0)
            sim_score = dup.get("similarity_with_winner", 100.0)
            log_entry = MergedLeadLog(
                winner_lead_id=clean_lead.id,
                winner_raw_lead_id=winner["raw_id"],
                archived_raw_lead_id=dup["raw_id"],
                id_type="raw_lead_id",
                archived_lead_name=f"{dup['first_name'] or ''} {dup['last_name'] or ''}".strip(),
                archived_company=dup["company"],
                archived_email=dup["email"],
                similarity_score=sim_score,
                merge_reason=f"{dup.get('match_reason', 'Matched')}. Raw lead #{dup['raw_id']} archived; "
                             f"raw lead #{winner['raw_id']} kept as clean lead #{clean_lead.id}."
            )
            merged_logs.append(log_entry)

    db.bulk_save_objects(merged_logs)

    # Human review queue: borderline pairs whose two records both survived as clean leads, and every junk row.
    winners = {c[0]["raw_id"] for c in clusters}
    review_objects = []
    for a, b, sim, reason in review_pairs:
        if a["raw_id"] in winners and b["raw_id"] in winners:
            review_objects.append(ReviewItem(
                run_id=None, item_type="merge", status="pending", id_type="raw_lead_id",
                record_a_ref=a["raw_id"], record_b_ref=b["raw_id"],
                record_a=json.dumps(_snapshot(a)), record_b=json.dumps(_snapshot(b)),
                similarity_score=sim,
                reason=f"Borderline fuzzy match ({REVIEW_BAND[0]:.0f}-{REVIEW_BAND[1]:.0f}% band): {reason}"))
    for c in clusters:
        w = c[0]
        if w["is_junk"]:
            review_objects.append(ReviewItem(
                run_id=None, item_type="junk", status="pending", id_type="raw_lead_id",
                record_a_ref=w["raw_id"], record_a=json.dumps(_snapshot(w)), reason=w["junk_reason"]))
    db.bulk_save_objects(review_objects)
    db.commit()
    review_merge_count = sum(1 for r in review_objects if r.item_type == "merge")

    # Calculate Data Quality Metrics Report
    total_raw = len(raw_leads)
    duplicate_rate_before = round((duplicate_records_count / total_raw) * 100, 1) if total_raw > 0 else 0.0
    duplicate_rate_after = 0.0 # All duplicates merged into winners

    completeness_before = round((populated_fields_raw / total_fields_raw) * 100, 1) if total_fields_raw > 0 else 0.0
    completeness_after = round((populated_fields_clean / total_fields_clean) * 100, 1) if total_fields_clean > 0 else 0.0

    report = {
        "total_raw_processed": total_raw,
        "total_clean_stored": len(clusters),
        "junk_rows_removed": junk_count,
        "duplicate_clusters_detected": duplicate_clusters_count,
        "duplicate_records_merged": duplicate_records_count,
        "duplicate_rate_before": duplicate_rate_before,
        "duplicate_rate_after": duplicate_rate_after,
        "completeness_score_before": completeness_before,
        "completeness_score_after": completeness_after,
        "fuzzy_threshold_used": threshold,
        "auto_merge_min_score": auto_merge_min(threshold),
        "review_band": list(REVIEW_BAND),
        "borderline_pairs_queued_for_review": review_merge_count,
        "junk_rows_queued_for_review": junk_count,
    }

    return report


def _snapshot(rec: dict) -> dict:
    keys = ("first_name", "last_name", "email", "company", "job_title", "phone", "state", "industry",
            "engagement_score", "junk_reason")
    return {k: rec.get(k) for k in keys}
