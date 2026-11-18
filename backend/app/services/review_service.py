"""Human review queue: approve/reject borderline merges and junk rows.

merge item  - approve: the two records are merged (the less complete one is archived into merged_leads_log)
            - reject:  both records stay as separate leads
junk item   - approve: the record stays flagged as junk (excluded from scoring, routing and HubSpot sync)
            - reject:  the junk flag is removed; re-run scoring/assignment to score and route the lead
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.schemas import AssignmentLog, CleanLead, MergedLeadLog, ReviewItem


class ReviewError(ValueError):
    pass


def _scope(query, model, run_id: Optional[str]):
    return query.filter(model.run_id == run_id) if run_id else query.filter(model.run_id.is_(None))


def _find_lead(db: Session, item: ReviewItem, ref: int) -> Optional[CleanLead]:
    q = _scope(db.query(CleanLead), CleanLead, item.run_id)
    if item.id_type == "raw_lead_id":
        return q.filter(CleanLead.raw_lead_id == ref).first()
    return q.filter(CleanLead.source_row == ref).first()


def _completeness(lead: CleanLead) -> float:
    fields = [lead.first_name, lead.last_name, lead.email, lead.company, lead.job_title, lead.phone,
              lead.state, lead.industry, lead.company_size]
    filled = sum(1 for f in fields if f not in (None, "") and str(f).upper() != "UNKNOWN")
    return filled / len(fields) * 100 + (lead.engagement_score or 0) / 10


def to_dict(item: ReviewItem) -> Dict[str, Any]:
    return {
        "id": item.id, "run_id": item.run_id, "item_type": item.item_type, "status": item.status,
        "id_type": item.id_type, "record_a_ref": item.record_a_ref, "record_b_ref": item.record_b_ref,
        "record_a": json.loads(item.record_a) if item.record_a else None,
        "record_b": json.loads(item.record_b) if item.record_b else None,
        "similarity_score": item.similarity_score, "reason": item.reason,
        "resolution_note": item.resolution_note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }


def list_items(db: Session, run_id: Optional[str], status: Optional[str] = "pending",
               item_type: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    q = _scope(db.query(ReviewItem), ReviewItem, run_id)
    if status and status != "all":
        q = q.filter(ReviewItem.status == status)
    if item_type:
        q = q.filter(ReviewItem.item_type == item_type)
    return [to_dict(i) for i in q.order_by(ReviewItem.item_type, ReviewItem.id).limit(limit).all()]


def summary(db: Session, run_id: Optional[str]) -> Dict[str, Any]:
    items = _scope(db.query(ReviewItem), ReviewItem, run_id).all()
    out = {"pending": 0, "approved": 0, "rejected": 0, "merge_pending": 0, "junk_pending": 0, "total": len(items)}
    for i in items:
        out[i.status] = out.get(i.status, 0) + 1
        if i.status == "pending":
            out[f"{i.item_type}_pending"] += 1
    return out


def resolve(db: Session, item_id: int, decision: str, note: Optional[str] = None) -> Dict[str, Any]:
    if decision not in ("approve", "reject"):
        raise ReviewError("decision must be 'approve' or 'reject'")
    item = db.query(ReviewItem).filter(ReviewItem.id == item_id).first()
    if not item:
        raise ReviewError(f"Review item {item_id} not found")
    if item.status != "pending":
        raise ReviewError(f"Review item {item_id} is already {item.status}")

    outcome = ""
    if item.item_type == "merge":
        a, b = _find_lead(db, item, item.record_a_ref), _find_lead(db, item, item.record_b_ref)
        if decision == "approve":
            if not a or not b:
                raise ReviewError("One of the two records no longer exists (was it merged already?)")
            winner, loser = (a, b) if _completeness(a) >= _completeness(b) else (b, a)
            winner_ref = item.record_a_ref if winner is a else item.record_b_ref
            loser_ref = item.record_b_ref if winner is a else item.record_a_ref
            db.add(MergedLeadLog(
                run_id=item.run_id, winner_lead_id=winner.id, winner_raw_lead_id=winner_ref,
                archived_raw_lead_id=loser_ref, id_type=item.id_type,
                archived_lead_name=f"{loser.first_name or ''} {loser.last_name or ''}".strip(),
                archived_company=loser.company, archived_email=loser.email,
                similarity_score=item.similarity_score or 0.0,
                merge_reason=f"Approved by reviewer: {item.reason}. Record {loser_ref} archived; "
                             f"record {winner_ref} kept."))
            winner.duplicate_cluster_id = winner.duplicate_cluster_id or f"REVIEW-{item.id}"
            db.query(AssignmentLog).filter(AssignmentLog.lead_id == loser.id).delete(synchronize_session=False)
            db.delete(loser)
            outcome = f"Merged: record {loser_ref} archived into record {winner_ref}"
        else:
            outcome = "Kept as two separate leads"
    else:  # junk
        lead = _find_lead(db, item, item.record_a_ref)
        if decision == "approve":
            outcome = "Confirmed as junk (stays excluded)"
        else:
            if lead:
                lead.is_junk = False
                lead.junk_reason = None
            else:
                # A pipeline row dropped at cleaning: recreate it from the stored snapshot
                snap = json.loads(item.record_a or "{}")
                db.add(CleanLead(run_id=item.run_id, source_row=item.record_a_ref, is_junk=False,
                                 first_name=snap.get("first_name"), last_name=snap.get("last_name"),
                                 company=snap.get("company"), job_title=snap.get("job_title"),
                                 email=snap.get("email"), phone=snap.get("phone"), state=snap.get("state"),
                                 industry=snap.get("industry")))
            outcome = "Not junk: restored as an active lead (re-run scoring and routing to include it)"

    item.status = "approved" if decision == "approve" else "rejected"
    item.resolution_note = f"{outcome}" + (f" | Reviewer note: {note}" if note else "")
    item.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return to_dict(item)
