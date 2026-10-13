import json
import io
import csv
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_

from app.database import get_db
from app.models.schemas import CleanLead, Rep, CleaningLog, PipelineRun

router = APIRouter(prefix="/leads", tags=["Lead Lists & Bands"])

@router.get("/by-band")
def get_leads_by_band(
    run_id: Optional[str] = Query(None, description="Pipeline run UUID. If omitted, uses latest completed run."),
    band: Optional[str] = Query("all", description="Lead band: hot | warm | cold | all"),
    q: Optional[str] = Query(None, description="Search query matching name, email, company, title"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    state: Optional[str] = Query(None, description="Filter by state"),
    assigned_rep: Optional[str] = Query(None, description="Filter by assigned rep name or ID"),
    sort_by: Optional[str] = Query("score", description="Sort field: score | company | date"),
    order: Optional[str] = Query("desc", description="Sort direction: asc | desc"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=500, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    Retrieves filtered, searched, sorted, and paginated leads by score band (Hot / Warm / Cold / All).
    Each lead includes score, score_band, top 3 reasons, assigned rep, and cleaning flags.
    """
    # If run_id not provided, default to latest run
    target_run_id = run_id
    if not target_run_id:
        latest_run = db.query(PipelineRun).order_by(PipelineRun.created_at.desc()).first()
        if latest_run:
            target_run_id = latest_run.run_id

    query = db.query(CleanLead)
    if target_run_id:
        query = query.filter(CleanLead.run_id == target_run_id)

    # Exclude junk from active lead views unless explicitly requested
    query = query.filter(CleanLead.is_junk == False)

    # Band filter
    band_lower = (band or "all").lower()
    if band_lower in {"hot", "warm", "cold"}:
        query = query.filter(CleanLead.score_band == band_lower.capitalize())

    # Industry filter
    if industry and industry.upper() != "ALL":
        query = query.filter(CleanLead.industry.ilike(f"%{industry}%"))

    # State filter
    if state and state.upper() != "ALL":
        query = query.filter(CleanLead.state == state.upper())

    # Assigned Rep filter
    if assigned_rep and assigned_rep.upper() != "ALL":
        if assigned_rep.isdigit():
            query = query.filter(CleanLead.assigned_rep_id == int(assigned_rep))
        else:
            rep_ids = [r.id for r in db.query(Rep).filter(Rep.name.ilike(f"%{assigned_rep}%")).all()]
            query = query.filter(CleanLead.assigned_rep_id.in_(rep_ids))

    # Search filter
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                CleanLead.first_name.ilike(term),
                CleanLead.last_name.ilike(term),
                CleanLead.email.ilike(term),
                CleanLead.company.ilike(term),
                CleanLead.job_title.ilike(term)
            )
        )

    # Sorting
    is_desc = order.lower() == "desc"
    if sort_by == "company":
        sort_col = CleanLead.company
    elif sort_by == "date":
        sort_col = CleanLead.last_activity_date
    else:  # default score
        sort_col = CleanLead.active_score

    query = query.order_by(desc(sort_col) if is_desc else asc(sort_col))

    total_count = query.count()
    offset_val = (page - 1) * limit
    paged_leads = query.offset(offset_val).limit(limit).all()

    # Pre-fetch reps
    all_reps = {r.id: r for r in db.query(Rep).all()}

    # Format leads
    lead_results = []
    for lead in paged_leads:
        top_reasons = []
        breakdown_data = None
        if lead.score_breakdown:
            try:
                b_json = json.loads(lead.score_breakdown)
                top_reasons = b_json.get("top_reasons", [])
                breakdown_data = b_json
            except Exception:
                pass

        if not top_reasons:
            top_reasons = [
                f"Engagement: {lead.engagement_score or 0:.0f} pts",
                f"Company Size: {lead.company_size or 50} employees",
                f"Industry: {lead.industry or 'General'}"
            ]

        rep_obj = all_reps.get(lead.assigned_rep_id)
        rep_name = rep_obj.name if rep_obj else "Unassigned"

        # Cleaning flags
        cleaning_flags = []
        if lead.phone and lead.phone.startswith("+"):
            cleaning_flags.append("E.164 Phone")
        if lead.state and len(lead.state) == 2 and lead.state != "UNKNOWN":
            cleaning_flags.append(f"State: {lead.state}")
        if lead.duplicate_cluster_id:
            cleaning_flags.append("Deduplicated Winner")

        extra_fields_dict = {}
        if lead.extra_fields:
            try:
                extra_fields_dict = json.loads(lead.extra_fields)
            except Exception:
                pass

        full_name = f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        if not full_name:
            full_name = lead.email or "Unnamed Lead"

        lead_results.append({
            "id": lead.id,
            "run_id": lead.run_id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "name": full_name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "job_title": lead.job_title,
            "industry": lead.industry,
            "company_size": lead.company_size,
            "state": lead.state,
            "city": lead.city,
            "country": lead.country,
            "score": round(lead.active_score or 0.0, 1),
            "rule_score": round(lead.rule_score or 0.0, 1),
            "ml_score": round(lead.ml_score or 0.0, 1) if lead.ml_score is not None else None,
            "band": lead.score_band or "Cold",
            "top_3_reasons": top_reasons,
            "score_breakdown": breakdown_data,
            "assigned_rep": {
                "id": lead.assigned_rep_id,
                "name": rep_name
            },
            "assignment_reason": lead.assignment_reason,
            "cleaning_flags": cleaning_flags,
            "extra_fields": extra_fields_dict,
            "last_activity_date": lead.last_activity_date,
            "created_date": lead.created_date
        })

    total_pages = max(1, (total_count + limit - 1) // limit)

    return {
        "run_id": target_run_id,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "leads": lead_results
    }

@router.get("/band-summary")
def get_band_summary(
    run_id: Optional[str] = Query(None, description="Pipeline run UUID"),
    db: Session = Depends(get_db)
):
    """
    Returns counts and percentages per band (Hot, Warm, Cold) for a run.
    """
    target_run_id = run_id
    if not target_run_id:
        latest_run = db.query(PipelineRun).order_by(PipelineRun.created_at.desc()).first()
        if latest_run:
            target_run_id = latest_run.run_id

    query = db.query(CleanLead).filter(CleanLead.is_junk == False)
    if target_run_id:
        query = query.filter(CleanLead.run_id == target_run_id)

    total_leads = query.count()
    if total_leads == 0:
        return {
            "run_id": target_run_id,
            "total": 0,
            "hot": {"count": 0, "percentage": 0.0},
            "warm": {"count": 0, "percentage": 0.0},
            "cold": {"count": 0, "percentage": 0.0}
        }

    hot_count = query.filter(CleanLead.score_band == "Hot").count()
    warm_count = query.filter(CleanLead.score_band == "Warm").count()
    cold_count = query.filter(CleanLead.score_band == "Cold").count()

    return {
        "run_id": target_run_id,
        "total": total_leads,
        "hot": {
            "count": hot_count,
            "percentage": round((hot_count / total_leads) * 100, 1)
        },
        "warm": {
            "count": warm_count,
            "percentage": round((warm_count / total_leads) * 100, 1)
        },
        "cold": {
            "count": cold_count,
            "percentage": round((cold_count / total_leads) * 100, 1)
        }
    }

@router.get("/export")
def export_leads(
    run_id: Optional[str] = Query(None),
    band: Optional[str] = Query("all"),
    industry: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    assigned_rep: Optional[str] = Query(None),
    format: str = Query("csv"),
    db: Session = Depends(get_db)
):
    """
    Downloads filtered lead dataset as CSV.
    """
    target_run_id = run_id
    if not target_run_id:
        latest_run = db.query(PipelineRun).order_by(PipelineRun.created_at.desc()).first()
        if latest_run:
            target_run_id = latest_run.run_id

    query = db.query(CleanLead).filter(CleanLead.is_junk == False)
    if target_run_id:
        query = query.filter(CleanLead.run_id == target_run_id)

    band_lower = (band or "all").lower()
    if band_lower in {"hot", "warm", "cold"}:
        query = query.filter(CleanLead.score_band == band_lower.capitalize())

    if industry and industry.upper() != "ALL":
        query = query.filter(CleanLead.industry.ilike(f"%{industry}%"))

    if state and state.upper() != "ALL":
        query = query.filter(CleanLead.state == state.upper())

    if assigned_rep and assigned_rep.upper() != "ALL":
        if assigned_rep.isdigit():
            query = query.filter(CleanLead.assigned_rep_id == int(assigned_rep))
        else:
            rep_ids = [r.id for r in db.query(Rep).filter(Rep.name.ilike(f"%{assigned_rep}%")).all()]
            query = query.filter(CleanLead.assigned_rep_id.in_(rep_ids))

    leads = query.order_by(CleanLead.active_score.desc()).all()
    all_reps = {r.id: r.name for r in db.query(Rep).all()}

    output = io.StringIO()
    writer = csv.writer(output)

    # CSV Header
    writer.writerow([
        "ID", "Name", "Email", "Phone", "Company", "Job Title",
        "Industry", "Company Size", "State", "Score", "Band",
        "Assigned Rep", "Assignment Rationale", "Top Reasons", "Last Activity Date"
    ])

    for l in leads:
        name = f"{l.first_name or ''} {l.last_name or ''}".strip() or l.email
        rep_name = all_reps.get(l.assigned_rep_id, "Unassigned")
        top_reasons_str = ""
        if l.score_breakdown:
            try:
                b_json = json.loads(l.score_breakdown)
                top_reasons_str = "; ".join(b_json.get("top_reasons", []))
            except Exception:
                pass

        writer.writerow([
            l.id, name, l.email or "", l.phone or "", l.company or "", l.job_title or "",
            l.industry or "", l.company_size or "", l.state or "", round(l.active_score or 0.0, 1),
            l.score_band or "", rep_name, l.assignment_reason or "", top_reasons_str, l.last_activity_date or ""
        ])

    csv_filename = f"leads_{band_lower}_{(target_run_id or 'all')[:8]}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"}
    )
