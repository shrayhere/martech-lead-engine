from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.cleaning_service import run_cleaning_pipeline
from app.models.schemas import CleanLead, MergedLeadLog

router = APIRouter(prefix="/leads", tags=["Data Quality"])

@router.post("/clean")
def trigger_lead_cleaning(db: Session = Depends(get_db)):
    """
    Executes Data Quality & RapidFuzz Deduplication pipeline on raw_leads.
    Normalizes state, phone, company, filters junk, merges duplicates, and stores in clean_leads.
    """
    try:
        report = run_cleaning_pipeline(db)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data cleaning pipeline failed: {str(e)}")

@router.get("/clean")
def get_clean_leads(limit: int = 250, include_junk: bool = True, db: Session = Depends(get_db)):
    """
    Retrieves stored clean leads.
    """
    query = db.query(CleanLead)
    if not include_junk:
        query = query.filter(CleanLead.is_junk == False)
    
    leads = query.order_by(CleanLead.id.asc()).limit(limit).all()
    return {
        "count": len(leads),
        "leads": leads
    }

@router.get("/merged-log")
def get_merged_leads_log(limit: int = 250, db: Session = Depends(get_db)):
    """
    Retrieves the audit trail table of all duplicate leads merged and archived.
    Shows winner ID, archived record, similarity score, and merge rationale.
    """
    logs = db.query(MergedLeadLog).order_by(MergedLeadLog.similarity_score.desc()).limit(limit).all()
    return {
        "count": len(logs),
        "merged_logs": logs
    }
