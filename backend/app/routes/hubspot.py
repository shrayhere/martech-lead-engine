"""
HubSpot Routes
--------------
GET  /api/hubspot/status          → token status + last sync info
GET  /api/hubspot/workflows       → list imported workflows
GET  /api/hubspot/rules           → list active scoring rules derived from workflows
POST /api/hubspot/import-workflows → pull workflows from HubSpot and convert to rules
POST /api/hubspot/sync            → push scored leads TO HubSpot (existing functionality)
POST /api/hubspot/webhook         → receive real-time contact/deal events from HubSpot
GET  /api/hubspot/sync-log        → history of sync attempts
"""
import json
import hashlib
import hmac
import os
import time
import base64
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import (
    HubSpotWorkflow, HubSpotScoringRule, HubSpotSyncLog
)
from app.services import hubspot_sync
from app.services import hubspot_import

router = APIRouter(prefix="/hubspot", tags=["HubSpot"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SyncRequest(BaseModel):
    run_id: Optional[str] = None
    dry_run: bool = True
    limit: Optional[int] = None


class RuleToggleRequest(BaseModel):
    rule_ids: List[int]
    active: bool


# ---------------------------------------------------------------------------
# Status & info
# ---------------------------------------------------------------------------

@router.get("/status")
def hubspot_status(db: Session = Depends(get_db)):
    """
    Returns:
    - whether a token is configured (never returns the token itself)
    - last import sync info
    - last push sync info
    - count of workflows and rules in DB
    - required scopes
    """
    token_ok = hubspot_import.token_configured()

    last_import = (
        db.query(HubSpotSyncLog)
        .filter(HubSpotSyncLog.direction == "import")
        .order_by(HubSpotSyncLog.synced_at.desc())
        .first()
    )
    last_push = (
        db.query(HubSpotSyncLog)
        .filter(HubSpotSyncLog.direction == "push")
        .order_by(HubSpotSyncLog.synced_at.desc())
        .first()
    )

    workflow_count = db.query(HubSpotWorkflow).count()
    mapped_count = db.query(HubSpotWorkflow).filter(HubSpotWorkflow.mapped == True).count()  # noqa: E712
    rule_count = db.query(HubSpotScoringRule).filter(HubSpotScoringRule.active == True).count()  # noqa: E712

    return {
        "token_configured": token_ok,
        "required_scopes": hubspot_import.REQUIRED_SCOPES,
        "custom_properties": [p["name"] for p in hubspot_sync.CUSTOM_PROPERTIES],
        "workflows_in_db": workflow_count,
        "workflows_mapped": mapped_count,
        "active_scoring_rules": rule_count,
        "last_import": {
            "synced_at": last_import.synced_at.isoformat() if last_import else None,
            "status": last_import.status if last_import else None,
            "workflows_found": last_import.workflows_found if last_import else None,
            "workflows_mapped": last_import.workflows_mapped if last_import else None,
            "rules_created": last_import.rules_created if last_import else None,
            "error": last_import.error_message if last_import else None,
            "triggered_by": last_import.triggered_by if last_import else None,
        } if last_import else None,
        "last_push": {
            "synced_at": last_push.synced_at.isoformat() if last_push else None,
            "status": last_push.status if last_push else None,
            "contacts_synced": last_push.contacts_synced if last_push else None,
        } if last_push else None,
    }


# ---------------------------------------------------------------------------
# Workflow import (HubSpot → our DB)
# ---------------------------------------------------------------------------

@router.post("/import-workflows")
def import_workflows(
    background_tasks: BackgroundTasks,
    async_mode: bool = False,
    db: Session = Depends(get_db),
):
    """
    Pull all workflows from the connected HubSpot portal, parse their
    enrollment triggers and actions, and store them as scoring rules.
    Set async_mode=true to run in the background and return immediately.
    """
    if not hubspot_import.token_configured():
        raise HTTPException(
            status_code=400,
            detail="HUBSPOT_ACCESS_TOKEN is not set on the server. See /api/hubspot/status for required scopes.",
        )

    if async_mode:
        from app.database import SessionLocal
        def _run_bg():
            bg_db = SessionLocal()
            try:
                hubspot_import.import_workflows(bg_db, triggered_by="manual")
            finally:
                bg_db.close()
        background_tasks.add_task(_run_bg)
        return {"status": "running", "message": "Workflow import started in background. Poll /api/hubspot/status for results."}

    try:
        result = hubspot_import.import_workflows(db, triggered_by="manual")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return result


@router.get("/workflows")
def list_workflows(
    mapped: Optional[bool] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """List workflows imported from HubSpot, with optional filter by mapped status."""
    q = db.query(HubSpotWorkflow).order_by(HubSpotWorkflow.synced_at.desc())
    if mapped is not None:
        q = q.filter(HubSpotWorkflow.mapped == mapped)
    workflows = q.limit(limit).all()

    results = []
    for wf in workflows:
        trigger = json.loads(wf.enrollment_trigger_summary or "{}")
        actions = json.loads(wf.actions_summary or "[]")
        results.append({
            "hubspot_id": wf.hubspot_id,
            "name": wf.name,
            "workflow_type": wf.workflow_type,
            "status": wf.status,
            "mapped": wf.mapped,
            "not_mapped_reason": wf.not_mapped_reason,
            "trigger_summary": trigger.get("summary", "unknown"),
            "trigger_type": trigger.get("raw_type"),
            "action_count": len(actions),
            "synced_at": wf.synced_at.isoformat() if wf.synced_at else None,
        })

    not_mapped_count = sum(1 for r in results if not r["mapped"])
    return {
        "count": len(results),
        "mapped_count": len(results) - not_mapped_count,
        "not_mapped_count": not_mapped_count,
        "workflows": results,
    }


# ---------------------------------------------------------------------------
# Scoring rules
# ---------------------------------------------------------------------------

@router.get("/rules")
def list_scoring_rules(active_only: bool = True, db: Session = Depends(get_db)):
    """List scoring rules derived from HubSpot workflows."""
    q = db.query(HubSpotScoringRule)
    if active_only:
        q = q.filter(HubSpotScoringRule.active == True)  # noqa: E712
    rules = q.order_by(HubSpotScoringRule.workflow_id).all()
    return {
        "count": len(rules),
        "rules": [
            {
                "id": r.id,
                "workflow_id": r.workflow_id,
                "rule_type": r.rule_type,
                "trigger_type": r.trigger_type,
                "field_name": r.field_name,
                "field_value": r.field_value,
                "score_delta": r.score_delta,
                "description": r.description,
                "active": r.active,
            }
            for r in rules
        ],
    }


@router.patch("/rules/toggle")
def toggle_rules(req: RuleToggleRequest, db: Session = Depends(get_db)):
    """Enable or disable specific scoring rules."""
    updated = (
        db.query(HubSpotScoringRule)
        .filter(HubSpotScoringRule.id.in_(req.rule_ids))
        .update({"active": req.active}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated, "active": req.active}


# ---------------------------------------------------------------------------
# Push scored leads TO HubSpot (existing functionality, enhanced)
# ---------------------------------------------------------------------------

@router.post("/sync")
def hubspot_push_leads(req: SyncRequest, db: Session = Depends(get_db)):
    """
    Dry run by default. With dry_run=false, upserts scored/classified leads
    into HubSpot contacts (upsert by email).
    """
    if not req.dry_run and not hubspot_sync.token_configured():
        raise HTTPException(
            status_code=400,
            detail="HUBSPOT_ACCESS_TOKEN is not set on the server",
        )
    try:
        result = hubspot_sync.sync_leads(db, req.run_id, req.dry_run, req.limit)

        # Log push to sync log
        if not req.dry_run:
            hubspot_import._log_sync(
                db,
                "push",
                "ok" if not result.get("errors") else "error",
                {
                    "triggered_by": "manual",
                    "contacts_synced": result.get("contacts_upserted", 0),
                    "workflows_found": None,
                    "workflows_mapped": None,
                    "rules_created": None,
                },
                error="; ".join(e.get("message", "") for e in result.get("errors", [])) or None,
            )

        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------------------------------------------------------------------------
# Webhook (HubSpot → us, real-time events)
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def hubspot_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive real-time HubSpot webhook events (contact.propertyChange,
    deal.propertyChange, etc.).

    HubSpot signs the request with HMAC-SHA256 using the app's client secret.
    In production, HUBSPOT_CLIENT_SECRET is strictly required; calls without it are rejected (401).
    Signatures are verified against WEBHOOK_PUBLIC_URL (or request.url as fallback).
    """
    body_bytes = await request.body()
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower()
    is_prod = env in ("production", "prod")

    client_secret = os.getenv("HUBSPOT_CLIENT_SECRET")
    if is_prod and not client_secret:
        raise HTTPException(
            status_code=401,
            detail="Webhook configuration error: HUBSPOT_CLIENT_SECRET must be configured in production."
        )

    # Signature verification (mandatory in production, or whenever HUBSPOT_CLIENT_SECRET is set)
    if client_secret:
        sig_header = request.headers.get("X-HubSpot-Signature-v3", "")
        timestamp_header = request.headers.get("X-HubSpot-Request-Timestamp", "")
        if not sig_header or not timestamp_header:
            raise HTTPException(status_code=401, detail="Missing required HubSpot signature headers")

        # Reject timestamps older than 5 minutes (300 seconds)
        try:
            ts_val = float(timestamp_header)
            # If in milliseconds (> 1e11), convert to seconds
            ts_sec = ts_val / 1000.0 if ts_val > 1e11 else ts_val
            if abs(time.time() - ts_sec) > 300:
                raise HTTPException(status_code=401, detail="HubSpot webhook timestamp expired (>5 minutes)")
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid HubSpot timestamp format")

        # In production or behind reverse proxies, HubSpot calls WEBHOOK_PUBLIC_URL
        webhook_public_url = os.getenv("WEBHOOK_PUBLIC_URL")
        uri = webhook_public_url.rstrip("/") if webhook_public_url else str(request.url)
        body_str = body_bytes.decode("utf-8", errors="replace")
        source = f"{request.method}{uri}{body_str}{timestamp_header}"
        expected_hex = hmac.new(
            client_secret.encode(),
            source.encode(),
            hashlib.sha256,
        ).hexdigest()
        expected_b64 = base64.b64encode(
            hmac.new(
                client_secret.encode(),
                source.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()

        if not (hmac.compare_digest(sig_header, expected_hex) or hmac.compare_digest(sig_header, expected_b64)):
            raise HTTPException(status_code=401, detail="Invalid HubSpot webhook signature")

    try:
        events = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(events, list):
        events = [events]

    result = hubspot_import.handle_webhook_event(db, events)
    return result


# ---------------------------------------------------------------------------
# Sync history log
# ---------------------------------------------------------------------------

@router.get("/sync-log")
def get_sync_log(limit: int = 50, db: Session = Depends(get_db)):
    """Return history of sync attempts (both import and push)."""
    logs = (
        db.query(HubSpotSyncLog)
        .order_by(HubSpotSyncLog.synced_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(logs),
        "logs": [
            {
                "id": l.id,
                "direction": l.direction,
                "status": l.status,
                "workflows_found": l.workflows_found,
                "workflows_mapped": l.workflows_mapped,
                "rules_created": l.rules_created,
                "contacts_synced": l.contacts_synced,
                "error_message": l.error_message,
                "triggered_by": l.triggered_by,
                "synced_at": l.synced_at.isoformat() if l.synced_at else None,
            }
            for l in logs
        ],
    }
