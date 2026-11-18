"""Push cleaned, scored and classified leads into HubSpot as contacts (upsert by email).

Safety:
  - The private-app token is read only from the HUBSPOT_ACCESS_TOKEN environment variable. It is never
    stored, logged or returned by the API.
  - dry_run=True (the default) builds and returns the exact payload without any network call.
  - Junk leads and leads without an email are never sent.

HubSpot endpoints used (CRM v3):
  POST /crm/v3/properties/contacts/groups          create the "MarTech Lead Engine" property group
  POST /crm/v3/properties/contacts                 create each custom property (409 = already exists)
  POST /crm/v3/objects/contacts/batch/upsert       upsert up to 100 contacts per call, idProperty=email
Private-app scopes needed: crm.objects.contacts.read, crm.objects.contacts.write,
crm.schemas.contacts.read, crm.schemas.contacts.write. See docs/hubspot_setup.md.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.models.schemas import CleanLead, Rep
from app.services.quality_service import EMAIL_RE

HUBSPOT_BASE = "https://api.hubapi.com"
BATCH_SIZE = 100
GROUP_NAME = "martech_lead_engine"

CUSTOM_PROPERTIES = [
    {"name": "mle_lead_score", "label": "Lead Engine Score", "type": "number", "fieldType": "number"},
    {"name": "mle_score_band", "label": "Lead Engine Band", "type": "enumeration", "fieldType": "select",
     "options": [{"label": b, "value": b, "displayOrder": i} for i, b in enumerate(["Hot", "Warm", "Cold"])]},
    {"name": "mle_persona", "label": "Lead Engine Persona", "type": "string", "fieldType": "text"},
    {"name": "mle_buying_role", "label": "Lead Engine Buying Role", "type": "string", "fieldType": "text"},
    {"name": "mle_interest", "label": "Lead Engine Interest", "type": "string", "fieldType": "text"},
    {"name": "mle_recommended_action", "label": "Lead Engine Next Action", "type": "string", "fieldType": "textarea"},
    {"name": "mle_assigned_rep", "label": "Lead Engine Assigned Rep", "type": "string", "fieldType": "text"},
]


def token_configured() -> bool:
    return bool(os.getenv("HUBSPOT_ACCESS_TOKEN"))


def _client(transport: Optional[httpx.BaseTransport] = None) -> httpx.Client:
    token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("HUBSPOT_ACCESS_TOKEN is not set on the server")
    return httpx.Client(base_url=HUBSPOT_BASE, timeout=30.0, transport=transport,
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})


def contact_properties(lead: CleanLead, rep_names: Dict[int, str]) -> Dict[str, Any]:
    props = {
        "email": lead.email, "firstname": lead.first_name, "lastname": lead.last_name,
        "company": lead.company, "jobtitle": lead.job_title, "phone": lead.phone,
        "state": None if (lead.state or "").upper() == "UNKNOWN" else lead.state,
        "mle_lead_score": None if lead.active_score is None else round(float(lead.active_score), 1),
        "mle_score_band": lead.score_band, "mle_persona": lead.persona, "mle_buying_role": lead.buying_role,
        "mle_interest": lead.interest, "mle_recommended_action": lead.recommended_action,
        "mle_assigned_rep": rep_names.get(lead.assigned_rep_id) if lead.assigned_rep_id else None,
    }
    # HubSpot treats "" as "clear the value"; leave unknown fields out instead of erasing data in the portal.
    return {k: v for k, v in props.items() if v not in (None, "")}


def select_leads(db: Session, run_id: Optional[str], limit: Optional[int]) -> List[CleanLead]:
    q = db.query(CleanLead).filter(CleanLead.is_junk == False, CleanLead.email.isnot(None),  # noqa: E712
                                   CleanLead.email != "")
    q = q.filter(CleanLead.run_id == run_id) if run_id else q.filter(CleanLead.run_id.is_(None))
    q = q.order_by(CleanLead.active_score.desc().nullslast(), CleanLead.id)
    return q.limit(limit).all() if limit else q.all()


def ensure_properties(client: httpx.Client) -> Dict[str, str]:
    status: Dict[str, str] = {}
    r = client.post("/crm/v3/properties/contacts/groups",
                    json={"name": GROUP_NAME, "label": "MarTech Lead Engine", "displayOrder": -1})
    status["group"] = "created" if r.status_code in (200, 201) else ("exists" if r.status_code == 409 else
                                                                     f"error {r.status_code}")
    for prop in CUSTOM_PROPERTIES:
        r = client.post("/crm/v3/properties/contacts", json={**prop, "groupName": GROUP_NAME})
        if r.status_code in (200, 201):
            status[prop["name"]] = "created"
        elif r.status_code == 409:
            status[prop["name"]] = "exists"
        else:
            raise RuntimeError(f"Could not create HubSpot property {prop['name']}: HTTP {r.status_code} "
                               f"{r.text[:300]}")
    return status


def sync_leads(db: Session, run_id: Optional[str] = None, dry_run: bool = True, limit: Optional[int] = None,
               transport: Optional[httpx.BaseTransport] = None) -> Dict[str, Any]:
    candidates = select_leads(db, run_id, limit)
    # HubSpot rejects malformed emails (e.g. "name@@domain.com"); leave them out and report them
    leads = [l for l in candidates if EMAIL_RE.match(l.email.strip())]
    invalid_emails = [l.email for l in candidates if not EMAIL_RE.match(l.email.strip())]
    rep_names = {r.id: r.name for r in db.query(Rep).all()}
    inputs = [{"idProperty": "email", "id": l.email.strip().lower(), "properties": contact_properties(l, rep_names)}
              for l in leads]
    batches = [inputs[i:i + BATCH_SIZE] for i in range(0, len(inputs), BATCH_SIZE)]
    result: Dict[str, Any] = {
        "dry_run": dry_run, "source": run_id or "staged", "contacts_selected": len(inputs),
        "batches": len(batches), "endpoint": "POST /crm/v3/objects/contacts/batch/upsert",
        "unscored_or_unclassified": sum(1 for l in leads if l.score_band is None or l.persona is None),
        "skipped_invalid_email": len(invalid_emails),
        "skipped_invalid_email_examples": invalid_emails[:5],
    }
    if dry_run:
        result["preview"] = inputs[:5]
        result["custom_properties"] = [p["name"] for p in CUSTOM_PROPERTIES]
        return result

    synced, errors = 0, []
    with _client(transport) as client:
        result["properties"] = ensure_properties(client)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        by_email = {l.email.strip().lower(): l for l in leads}
        for batch in batches:
            r = client.post("/crm/v3/objects/contacts/batch/upsert", json={"inputs": batch})
            if r.status_code in (200, 201, 207):
                body = r.json()
                for rec in body.get("results", []):
                    email = (rec.get("properties", {}).get("email") or "").lower()
                    if email in by_email:
                        by_email[email].hubspot_synced_at = now
                    synced += 1
                for err in body.get("errors", []):
                    errors.append({"status": err.get("status"), "message": err.get("message")})
            else:
                errors.append({"status": r.status_code, "message": r.text[:300]})
        db.commit()
    result.update({"contacts_upserted": synced, "errors": errors})
    return result
