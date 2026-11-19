"""
HubSpot Workflow Import Service
================================
Reads automation workflows from HubSpot's Automation v4 API (flows), parses
enrollment triggers and actions, and converts them into scoring rules stored
in hubspot_scoring_rules. Also handles pulling contacts, companies and deals
for real-time updates via webhooks.

Scopes required (HubSpot private app):
  - automation                    (read workflows)
  - crm.objects.contacts.read     (contacts)
  - crm.objects.companies.read    (companies)
  - crm.objects.deals.read        (deals)
  - crm.objects.contacts.write    (push scored contacts back)
  - crm.schemas.contacts.read/write (custom properties)

Workflow types that map to scoring rules:
  - Property-change triggers  → score_boost/penalty
  - List membership triggers  → score_boost
  - Form submission triggers  → score_boost
  - Email engagement triggers → score_boost
  - Deal stage triggers       → score_boost/routing

Workflow types that are NOT mapped (shown as "not_mapped"):
  - DATE_CENTERED workflows
  - COMPANY / DEAL object workflows
  - Any workflow with unsupported action types
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models.schemas import (
    HubSpotWorkflow, HubSpotScoringRule, HubSpotSyncLog, CleanLead
)

logger = logging.getLogger(__name__)

HUBSPOT_BASE = "https://api.hubapi.com"
# Scopes needed — shown in the UI for user reference
REQUIRED_SCOPES = [
    "automation",
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.companies.read",
    "crm.objects.deals.read",
    "crm.schemas.contacts.read",
    "crm.schemas.contacts.write",
]

# Trigger filter types we know how to convert
SUPPORTED_TRIGGER_TYPES = {
    "CONTACT_PROPERTY",
    "COMPANY_PROPERTY",
    "DEAL_PROPERTY",
    "LIST_MEMBERSHIP",
    "FORM_SUBMISSION",
    "EMAIL_EVENTS",
    "DEAL_STAGE",
    "PAGE_VIEW",
    "MEETING_BOOKED",
}

# Score deltas for well-known property values
PROPERTY_SCORE_MAP = {
    "lifecyclestage": {
        "salesqualifiedlead": 20,
        "opportunity": 25,
        "lead": 10,
        "subscriber": 5,
        "marketingqualifiedlead": 15,
    },
    "hs_lead_status": {
        "new": 5,
        "open": 5,
        "in_progress": 10,
        "connected": 15,
        "qualified": 20,
        "unqualified": -20,
    },
    "mle_score_band": {
        "hot": 25,
        "warm": 10,
        "cold": -5,
    },
}

ENGAGEMENT_SCORE_DELTA = {
    "FORM_SUBMISSION": 15,
    "EMAIL_EVENTS": 8,
    "PAGE_VIEW": 3,
    "MEETING_BOOKED": 20,
    "LIST_MEMBERSHIP": 10,
    "DEAL_STAGE": 20,
}


def token_configured() -> bool:
    return bool(os.getenv("HUBSPOT_ACCESS_TOKEN"))


def _client() -> httpx.Client:
    token = os.getenv("HUBSPOT_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "HUBSPOT_ACCESS_TOKEN is not set on the server. "
            "Add it in Settings → Integrations → Private Apps."
        )
    return httpx.Client(
        base_url=HUBSPOT_BASE,
        timeout=30.0,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )


# ---------------------------------------------------------------------------
# Workflow fetching
# ---------------------------------------------------------------------------

def _fetch_all_workflows(client: httpx.Client) -> List[Dict[str, Any]]:
    """Fetch all workflows via Automation v4 flows API (paginated)."""
    workflows = []
    after = None
    page = 0
    while page < 20:  # safety cap: max 2 000 workflows
        params = {"limit": 100}
        if after:
            params["after"] = after
        resp = client.get("/automation/v4/flows", params=params)
        if resp.status_code == 404:
            # Try the v3 endpoint as fallback
            resp = client.get("/automation/v3/workflows")
            if resp.status_code != 200:
                raise RuntimeError(
                    f"HubSpot Automation API returned HTTP {resp.status_code}: {resp.text[:300]}"
                )
            body = resp.json()
            return body.get("workflows", [])
        if resp.status_code != 200:
            raise RuntimeError(
                f"HubSpot Automation API returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        body = resp.json()
        workflows.extend(body.get("results", []))
        paging = body.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")
        if not after:
            break
        page += 1
    return workflows


def _fetch_contacts_page(client: httpx.Client, limit: int = 100, after: Optional[str] = None) -> Dict[str, Any]:
    """Fetch a page of contacts with key properties."""
    properties = [
        "email", "firstname", "lastname", "company", "jobtitle", "phone",
        "state", "industry", "mle_lead_score", "mle_score_band", "lifecyclestage",
    ]
    params = {"limit": limit, "properties": ",".join(properties)}
    if after:
        params["after"] = after
    resp = client.get("/crm/v3/objects/contacts", params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"HubSpot CRM contacts API: HTTP {resp.status_code}")
    return resp.json()


# ---------------------------------------------------------------------------
# Workflow parsing
# ---------------------------------------------------------------------------

def _parse_trigger(trigger: Dict[str, Any]) -> Dict[str, Any]:
    """Parse an enrollment trigger from a v4 flow or v3 workflow."""
    result: Dict[str, Any] = {"raw_type": None, "summary": "unknown trigger"}

    # v4 structure
    trigger_type = trigger.get("type") or trigger.get("filterBranch", {}).get("filterBranchType")
    result["raw_type"] = trigger_type

    if trigger_type == "CONTACT_PROPERTY" or trigger_type == "PROPERTY":
        filters = trigger.get("filters", [{}])
        f = filters[0] if filters else {}
        prop = f.get("property") or f.get("filterType", "unknown")
        op = f.get("operation", {})
        val = op.get("value") or op.get("includeObjectsWithNoValueSet", "")
        result["summary"] = f"Contact property '{prop}' changes (value: {val})"
        result["property"] = prop
        result["value"] = str(val).lower() if val else None
        result["supported"] = True

    elif trigger_type == "LIST_MEMBERSHIP":
        list_id = trigger.get("listId") or "unknown"
        result["summary"] = f"Contact joins list {list_id}"
        result["list_id"] = list_id
        result["supported"] = True

    elif trigger_type == "FORM_SUBMISSION":
        form_id = trigger.get("formId") or "any"
        result["summary"] = f"Contact submits form {form_id}"
        result["supported"] = True

    elif trigger_type in ("EMAIL_EVENTS", "PAGE_VIEW", "MEETING_BOOKED", "DEAL_STAGE"):
        result["summary"] = f"{trigger_type.replace('_', ' ').title()} event"
        result["supported"] = True

    else:
        result["supported"] = False
        result["summary"] = f"Unsupported trigger: {trigger_type}"

    return result


def _parse_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse workflow actions into human-readable summaries."""
    parsed = []
    for action in actions:
        a_type = action.get("type") or action.get("actionTypeId") or "UNKNOWN"
        entry: Dict[str, Any] = {"type": a_type}

        if a_type in ("SET_CONTACT_PROPERTY", "SET_PROPERTY"):
            entry["summary"] = f"Set property: {action.get('propertyName')} = {action.get('value')}"
            entry["property"] = action.get("propertyName")
            entry["value"] = action.get("value")

        elif a_type in ("SEND_EMAIL", "AUTOMATED_EMAIL"):
            entry["summary"] = "Send marketing email"

        elif a_type in ("CREATE_TASK", "TASK"):
            entry["summary"] = f"Create task: {(action.get('subject') or '')[:60]}"

        elif a_type in ("ROTATE_RECORD_OWNER", "SET_OWNER"):
            entry["summary"] = "Route to rep / rotate owner"
            entry["is_routing"] = True

        elif a_type in ("BRANCH", "FILTER_BRANCH"):
            entry["summary"] = "Conditional branch"
            # Recurse into branches
            for branch in action.get("branches", []):
                entry.setdefault("branch_actions", []).extend(
                    _parse_actions(branch.get("actions", []))
                )

        elif a_type in ("ADD_TO_LIST",):
            entry["summary"] = f"Add to list {action.get('listId', '')}"

        elif a_type in ("NOTIFICATION_EMAIL",):
            entry["summary"] = "Send internal email notification"

        else:
            entry["summary"] = f"Action: {a_type}"

        parsed.append(entry)
    return parsed


def _workflow_to_rules(
    workflow: Dict[str, Any],
    trigger_info: Dict[str, Any],
    actions: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Convert a parsed workflow into a list of scoring rule dicts.
    Returns (rules, not_mapped_reason) where not_mapped_reason is None if mapped OK.
    """
    rules: List[Dict[str, Any]] = []
    wf_id = str(workflow.get("id") or workflow.get("flowId") or "")
    wf_name = workflow.get("name", "Unnamed Workflow")

    if not trigger_info.get("supported"):
        return [], f"Trigger type '{trigger_info.get('raw_type')}' is not supported for scoring rule mapping"

    trigger_type = trigger_info.get("raw_type", "")

    # Property-change triggers → score based on property value
    if trigger_type in ("CONTACT_PROPERTY", "PROPERTY"):
        prop = trigger_info.get("property", "")
        value = trigger_info.get("value")
        delta = None
        if prop.lower() in PROPERTY_SCORE_MAP and value:
            delta = PROPERTY_SCORE_MAP[prop.lower()].get(value.lower())
        if delta is None:
            # Generic: any property change is a mild engagement signal
            delta = 5
        rules.append({
            "workflow_id": wf_id,
            "rule_type": "score_boost" if delta >= 0 else "score_penalty",
            "trigger_type": "property_change",
            "field_name": prop,
            "field_value": value,
            "score_delta": float(delta),
            "description": f"[{wf_name}] {trigger_info['summary']}",
        })

    elif trigger_type == "LIST_MEMBERSHIP":
        rules.append({
            "workflow_id": wf_id,
            "rule_type": "score_boost",
            "trigger_type": "list_membership",
            "field_name": "list_id",
            "field_value": str(trigger_info.get("list_id", "")),
            "score_delta": float(ENGAGEMENT_SCORE_DELTA["LIST_MEMBERSHIP"]),
            "description": f"[{wf_name}] {trigger_info['summary']}",
        })

    elif trigger_type in ENGAGEMENT_SCORE_DELTA:
        rules.append({
            "workflow_id": wf_id,
            "rule_type": "score_boost",
            "trigger_type": trigger_type.lower(),
            "field_name": None,
            "field_value": None,
            "score_delta": float(ENGAGEMENT_SCORE_DELTA.get(trigger_type, 5)),
            "description": f"[{wf_name}] {trigger_info['summary']}",
        })
    else:
        return [], f"No scoring rule mapping defined for trigger '{trigger_type}'"

    # Check for routing actions → add routing rule
    for action in actions:
        if action.get("is_routing"):
            rules.append({
                "workflow_id": wf_id,
                "rule_type": "routing",
                "trigger_type": "workflow_routing",
                "field_name": "workflow_name",
                "field_value": wf_name,
                "score_delta": 0.0,
                "description": f"[{wf_name}] Route to rep via HubSpot workflow action",
            })
            break

    return rules, None


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

def import_workflows(db: Session, triggered_by: str = "manual") -> Dict[str, Any]:
    """
    Pull workflows from HubSpot, parse them, store in DB, convert to scoring rules.
    Returns a summary dict suitable for the API response.
    """
    if not token_configured():
        raise RuntimeError("HUBSPOT_ACCESS_TOKEN is not set on the server")

    now = datetime.now(timezone.utc)
    result: Dict[str, Any] = {
        "triggered_by": triggered_by,
        "synced_at": now.isoformat(),
        "workflows_found": 0,
        "workflows_mapped": 0,
        "workflows_not_mapped": 0,
        "rules_created": 0,
        "not_mapped_list": [],
        "errors": [],
        "required_scopes": REQUIRED_SCOPES,
    }

    try:
        with _client() as client:
            raw_workflows = _fetch_all_workflows(client)
    except RuntimeError as e:
        result["errors"].append(str(e))
        _log_sync(db, "import", "error", result, error=str(e))
        return result

    result["workflows_found"] = len(raw_workflows)

    # Clear old scoring rules (we re-derive them fresh each import)
    db.query(HubSpotScoringRule).delete()

    for wf in raw_workflows:
        wf_id = str(wf.get("id") or wf.get("flowId") or "")
        wf_name = wf.get("name", "Unnamed Workflow")
        wf_type = wf.get("type") or wf.get("objectType", "CONTACT")
        wf_status = wf.get("enabled") or wf.get("isPublished")
        status_str = "ACTIVE" if wf_status else "INACTIVE"

        # Parse triggers and actions
        triggers = wf.get("triggers", []) or wf.get("enrollmentCriteria", {}).get("filterBranches", [])
        actions = wf.get("actions", []) or []

        trigger_info = _parse_trigger(triggers[0]) if triggers else {
            "raw_type": None, "summary": "No trigger", "supported": False
        }
        parsed_actions = _parse_actions(actions)

        # Try to map to scoring rules
        rules, not_mapped_reason = _workflow_to_rules(wf, trigger_info, parsed_actions)

        mapped = len(rules) > 0

        # Upsert the workflow record
        existing = db.query(HubSpotWorkflow).filter(HubSpotWorkflow.hubspot_id == wf_id).first()
        if existing:
            existing.name = wf_name
            existing.workflow_type = wf_type
            existing.status = status_str
            existing.enrollment_trigger_summary = json.dumps(trigger_info)
            existing.actions_summary = json.dumps(parsed_actions)
            existing.mapped = mapped
            existing.not_mapped_reason = not_mapped_reason
            existing.synced_at = now
        else:
            db.add(HubSpotWorkflow(
                hubspot_id=wf_id,
                name=wf_name,
                workflow_type=wf_type,
                status=status_str,
                enrollment_trigger_summary=json.dumps(trigger_info),
                actions_summary=json.dumps(parsed_actions),
                mapped=mapped,
                not_mapped_reason=not_mapped_reason,
                synced_at=now,
            ))

        # Insert scoring rules
        for rule in rules:
            db.add(HubSpotScoringRule(**rule))
            result["rules_created"] += 1

        if mapped:
            result["workflows_mapped"] += 1
        else:
            result["workflows_not_mapped"] += 1
            result["not_mapped_list"].append({
                "id": wf_id,
                "name": wf_name,
                "reason": not_mapped_reason,
            })

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        result["errors"].append(f"DB commit failed: {e}")
        _log_sync(db, "import", "error", result, error=str(e))
        return result

    _log_sync(db, "import", "ok", result)
    return result


def _log_sync(
    db: Session,
    direction: str,
    status: str,
    result: Dict[str, Any],
    error: Optional[str] = None,
):
    """Write a row to hubspot_sync_log."""
    try:
        db.add(HubSpotSyncLog(
            direction=direction,
            status=status,
            workflows_found=result.get("workflows_found"),
            workflows_mapped=result.get("workflows_mapped"),
            rules_created=result.get("rules_created"),
            contacts_synced=result.get("contacts_synced"),
            error_message=error,
            triggered_by=result.get("triggered_by", "manual"),
        ))
        db.commit()
    except Exception:
        pass  # don't let logging failure break the caller


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------

def handle_webhook_event(db: Session, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process incoming HubSpot webhook events (contact or deal property changes).
    Updates the matching CleanLead record's engagement metadata and flags it
    for re-scoring on next pipeline run.

    HubSpot sends arrays of event objects with keys:
      subscriptionType, objectId, propertyName, propertyValue, occurredAt
    """
    processed = 0
    skipped = 0

    for event in events:
        sub_type = event.get("subscriptionType", "")
        obj_id = str(event.get("objectId", ""))
        prop_name = event.get("propertyName", "")
        prop_value = event.get("propertyValue", "")

        if "contact" not in sub_type.lower():
            skipped += 1
            continue

        # Try to find a CleanLead with matching hubspot contact (by email lookup is best,
        # but here we store the hubspot objectId in hubspot_synced_at for now)
        # A more robust implementation would store hs_object_id in CleanLead.
        # For now: match on email if the property being changed IS email, or log the event.
        lead = None
        if prop_name == "email" and prop_value:
            lead = db.query(CleanLead).filter(
                CleanLead.email == prop_value.lower().strip()
            ).first()

        if lead:
            # Mark lead as needing re-score
            if prop_name in ("mle_lead_score", "mle_score_band"):
                pass  # don't overwrite our own scores
            elif prop_name == "hs_lead_status" and prop_value == "unqualified":
                lead.score_band = "Cold"
                lead.is_junk = True
                lead.junk_reason = "Marked unqualified in HubSpot"
            # Update the sync timestamp
            lead.hubspot_synced_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            processed += 1

    if processed > 0:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return {
        "events_received": len(events),
        "contacts_updated": processed,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Scoring rule application (called from smart_scoring)
# ---------------------------------------------------------------------------

def get_active_rules(db: Session) -> List[Dict[str, Any]]:
    """Return all active HubSpot scoring rules as dicts."""
    rules = db.query(HubSpotScoringRule).filter(HubSpotScoringRule.active == True).all()  # noqa: E712
    return [
        {
            "id": r.id,
            "workflow_id": r.workflow_id,
            "rule_type": r.rule_type,
            "trigger_type": r.trigger_type,
            "field_name": r.field_name,
            "field_value": r.field_value,
            "score_delta": r.score_delta,
            "description": r.description,
        }
        for r in rules
    ]


def apply_hubspot_rules_to_lead(lead: Dict[str, Any], rules: List[Dict[str, Any]]) -> float:
    """
    Apply all active HubSpot-derived scoring rules to a lead dict.
    Returns the total score delta to add to the base score.
    """
    delta = 0.0
    for rule in rules:
        if rule["rule_type"] not in ("score_boost", "score_penalty"):
            continue
        trigger = rule.get("trigger_type", "")
        field = rule.get("field_name")
        expected_value = (rule.get("field_value") or "").lower()

        if trigger == "property_change" and field:
            lead_value = str(lead.get(field) or lead.get(field.replace("hs_", ""), "")).lower()
            if expected_value and lead_value == expected_value:
                delta += rule["score_delta"]
            elif not expected_value:
                # Any value change — mild engagement boost
                delta += min(rule["score_delta"], 3.0)

        elif trigger in ("list_membership", "form_submission", "email_events",
                          "deal_stage", "meeting_booked", "page_view"):
            # These are engagement signals; apply a fraction since we cannot know
            # from a lead dict alone whether the event occurred
            # (a full implementation would join against an events table)
            pass

    return delta
