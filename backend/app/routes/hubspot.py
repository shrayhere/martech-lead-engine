from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import hubspot_sync

router = APIRouter(prefix="/hubspot", tags=["HubSpot Sync"])


class SyncRequest(BaseModel):
    run_id: Optional[str] = None
    dry_run: bool = True
    limit: Optional[int] = None


@router.get("/status")
def hubspot_status():
    """Whether a HubSpot private-app token is configured on the server (the token is never returned)."""
    return {"token_configured": hubspot_sync.token_configured(),
            "custom_properties": [p["name"] for p in hubspot_sync.CUSTOM_PROPERTIES]}


@router.post("/sync")
def hubspot_sync_leads(req: SyncRequest, db: Session = Depends(get_db)):
    """Dry run by default. With dry_run=false, upserts the selected contacts into HubSpot."""
    if not req.dry_run and not hubspot_sync.token_configured():
        raise HTTPException(status_code=400, detail="HUBSPOT_ACCESS_TOKEN is not set on the server")
    try:
        return hubspot_sync.sync_leads(db, req.run_id, req.dry_run, req.limit)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
