from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.scoring_service import run_lead_scoring
from app.models.schemas import CleanLead
from app.config import settings

router = APIRouter(prefix="/leads", tags=["Scoring"])

@router.post("/score")
def trigger_scoring(mode: Literal["rule", "ml"] = Query("rule"), db: Session = Depends(get_db)):
    """
    Triggers lead scoring pipeline across all clean leads.
    Supports toggle between 'rule' (Weighted Rule-Based) and 'ml' (Scikit-Learn ML Classifier).
    """
    try:
        res = run_lead_scoring(db, scoring_mode=mode)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lead scoring failed: {str(e)}")

@router.get("/scored")
def get_scored_leads(
    band: str = None,
    industry: str = None,
    scoring_mode: str = "rule",
    limit: int = 250,
    db: Session = Depends(get_db)
):
    """
    Retrieves clean leads with scores, color bands (Hot/Warm/Cold), and signal breakdown.
    Supports filtering by score band (Hot/Warm/Cold) and industry.
    """
    query = db.query(CleanLead).filter(CleanLead.is_junk == False)
    
    if band:
        query = query.filter(CleanLead.score_band == band)
    if industry:
        query = query.filter(CleanLead.industry == industry)

    leads = query.order_by(CleanLead.active_score.desc()).limit(limit).all()

    return {
        "count": len(leads),
        "scoring_mode": scoring_mode,
        "leads": leads
    }

@router.get("/score-config")
def get_score_config():
    """
    Returns configurable scoring model weights, signal categories, and target industries.
    """
    return {
        "weights": {
            "company_size": settings.WEIGHT_COMPANY_SIZE,
            "target_industry": settings.WEIGHT_TARGET_INDUSTRY,
            "title_seniority": settings.WEIGHT_TITLE_SENIORITY,
            "engagement": settings.WEIGHT_ENGAGEMENT,
            "recency": settings.WEIGHT_RECENCY
        },
        "target_industries": settings.TARGET_INDUSTRIES,
        "score_bands": {
            "Hot": "80 - 100",
            "Warm": "50 - 79",
            "Cold": "0 - 49"
        }
    }
