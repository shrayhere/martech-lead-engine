from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.quality_service import quality_report

router = APIRouter(prefix="/quality", tags=["Data Quality Score"])


@router.get("/report")
def get_quality_report(run_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Data-quality score, per-check percentages, top 5 issues, before vs after.
    No run_id = staged flow (Stages 1-4); otherwise one Smart Upload pipeline run."""
    return quality_report(db, run_id)
