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
        assigned_leads = db.query(CleanLead).filter(CleanLead.assigned_rep_id == rep.id, CleanLead.run_id.is_(None)).all()
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

from pydantic import BaseModel

class RepUpdate(BaseModel):
    name: str
    territory: str
    industry_specialty: str

class RepCreate(BaseModel):
    name: str
    territory: str
    industry_specialty: str

@router.post("/reps")
def create_rep(rep_in: RepCreate, db: Session = Depends(get_db)):
    """Create a new sales rep with custom territory and industry routing."""
    new_rep = Rep(
        name=rep_in.name,
        territory=rep_in.territory,
        industry_specialty=rep_in.industry_specialty,
        assigned_lead_count=0
    )
    db.add(new_rep)
    db.commit()
    db.refresh(new_rep)
    return {"success": True, "rep": {"id": new_rep.id, "name": new_rep.name, "territory": new_rep.territory, "industry_specialty": new_rep.industry_specialty}}

@router.put("/reps/{rep_id}")
def update_rep(rep_id: int, rep_in: RepUpdate, db: Session = Depends(get_db)):
    """Update sales rep territory, industry specialty or name."""
    rep = db.query(Rep).filter(Rep.id == rep_id).first()
    if not rep:
        raise HTTPException(status_code=404, detail="Sales rep not found")
    rep.name = rep_in.name
    rep.territory = rep_in.territory
    rep.industry_specialty = rep_in.industry_specialty
    db.commit()
    return {"success": True, "rep": {"id": rep.id, "name": rep.name, "territory": rep.territory, "industry_specialty": rep.industry_specialty}}

@router.delete("/reps/{rep_id}")
def delete_rep(rep_id: int, db: Session = Depends(get_db)):
    """Delete a sales rep."""
    rep = db.query(Rep).filter(Rep.id == rep_id).first()
    if not rep:
        raise HTTPException(status_code=404, detail="Sales rep not found")
    db.delete(rep)
    db.commit()
    return {"success": True, "deleted_id": rep_id}
