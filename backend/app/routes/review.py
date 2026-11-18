from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import review_service

router = APIRouter(prefix="/review", tags=["Human Review Queue"])


@router.get("")
def list_review_items(run_id: Optional[str] = None, status: str = Query("pending"),
                      item_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Review items for the staged flow (no run_id) or one pipeline run. status: pending|approved|rejected|all."""
    return {"summary": review_service.summary(db, run_id),
            "items": review_service.list_items(db, run_id, status, item_type)}


@router.post("/{item_id}/{decision}")
def resolve_review_item(item_id: int, decision: str, note: Optional[str] = Body(None, embed=True),
                        db: Session = Depends(get_db)):
    """decision: approve | reject."""
    try:
        return review_service.resolve(db, item_id, decision, note)
    except review_service.ReviewError as e:
        raise HTTPException(status_code=400, detail=str(e))
