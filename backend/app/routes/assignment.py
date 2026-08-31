from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.assignment_service import run_lead_assignment, seed_sales_reps
from app.models.schemas import Rep, CleanLead, AssignmentLog

router = APIRouter(prefix="/leads", tags=["Assignment"])

@router.post("/assign")
def trigger_lead_assignment(db: Session = Depends(get_db)):
    """
    Executes automated sales rep lead assignment rules engine.
    Routes leads by Territory Match -> Industry Specialty -> Round-Robin Fallback.
    Stores human-readable assignment reason on every clean lead.
    """
    try:
        res = run_lead_assignment(db)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lead assignment failed: {str(e)}")

@router.get("/reps")
def get_reps_overview(db: Session = Depends(get_db)):
    """
    Retrieves sales reps overview along with their assigned leads and workload details.
    """
    seed_sales_reps(db)
    reps = db.query(Rep).all()

    result = []
    for rep in reps:
        assigned_leads = db.query(CleanLead).filter(CleanLead.assigned_rep_id == rep.id).all()
        result.append({
            "id": rep.id,
            "name": rep.name,
            "territory": rep.territory,
            "industry_specialty": rep.industry_specialty,
            "assigned_count": len(assigned_leads),
            "leads": assigned_leads
        })

    return {
        "count": len(result),
        "reps": result
    }
