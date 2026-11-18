from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import CleanLead
from app.services import classifier

router = APIRouter(prefix="/classify", tags=["AI Classification"])


@router.get("/status")
def classification_status():
    """Which engines are available. Never returns the key itself."""
    return {"local": True, "claude": classifier.claude_available(), "claude_model": classifier.CLAUDE_MODEL,
            "labels": classifier.LABELS}


@router.post("/run")
def run_classification(run_id: Optional[str] = None,
                       engine: Literal["local", "claude"] = Query("local"),
                       db: Session = Depends(get_db)):
    """Labels persona, buying role and interest for every clean lead, then applies the business rules."""
    result = classifier.classify_leads(db, run_id, engine)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/accuracy")
def classification_accuracy():
    """Local model accuracy on the held-out test titles (free; the Claude engine is evaluated from the CLI)."""
    return classifier.evaluate("local")


@router.get("/leads")
def classified_leads(run_id: Optional[str] = None, limit: int = 500, db: Session = Depends(get_db)):
    q = db.query(CleanLead)
    q = q.filter(CleanLead.run_id == run_id) if run_id else q.filter(CleanLead.run_id.is_(None))
    leads = q.order_by(CleanLead.active_score.desc().nullslast(), CleanLead.id).limit(limit).all()
    return {"count": len(leads), "leads": [{
        "id": l.id, "name": f"{l.first_name or ''} {l.last_name or ''}".strip(), "company": l.company,
        "job_title": l.job_title, "score_band": l.score_band, "active_score": l.active_score,
        "is_junk": l.is_junk, "persona": l.persona, "buying_role": l.buying_role, "interest": l.interest,
        "confidence": l.classification_confidence, "engine": l.classification_engine,
        "recommended_action": l.recommended_action} for l in leads]}
