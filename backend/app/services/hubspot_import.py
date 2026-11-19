"""
HubSpot Workflow Import Service
================================
Reads automation workflows from HubSpot's Automation v4 API (flows), parses
enrollment triggers and actions, and converts them into scoring rules stored
in hubspot_scoring_rules. Also handles pulling contacts, companies and deals
for real-time updates via webhooks.
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
REQUIRED_SCOPES = [
    "automation",
    "crm.objects.contacts.read",
    "crm.objects.contacts.write",
    "crm.objects.companies.read",
    "crm.objects.deals.read",
    "crm.schemas.contacts.read",
    "crm.schemas.contacts.write",
]

PROPERTY_SCORE_MAP = {
    "lifecyclestage": {
        "salesqualifiedlead": 25,
        "opportunity": 30,
        "lead": 10,
        "subscriber": 5,
        "marketingqualifiedlead": 20,
    },
    "hs_lead_status": {
        "new": 5,
        "open": 5,
        "in_progress": 10,
        "connected": 15,
        "qualified": 25,
        "unqualified": -20,
    },
    "lead_score_custom": {
        "gte": 25
    }
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
            "HUBSPOT_ACCESS_TOKEN is not set on the server."
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
    """
    Fetch all workflows via Automation v4 API.
    HubSpot /automation/v4/flows list endpoint returns basic flow metadata.
    We fetch the detailed flow for each id to get full actions and enrollmentCriteria.
    """
    detailed_workflows = []
    
    # Try v4 flows API first
    resp = client.get("/automation/v4/flows", params={"limit": 100})
    if resp.status_code == 200:
        flows = resp.json().get("results", [])
        for f in flows:
            fid = f.get("id")
            if fid:
                det = client.get(f"/automation/v4/flows/{fid}")
                if det.status_code == 200:
                    detailed_workflows.append(det.json())
                else:
                    detailed_workflows.append(f)
            else:
                detailed_workflows.append(f)
        if detailed_workflows:
            return detailed_workflows

    # Fallback to v3 workflows API
    resp3 = client.get("/automation/v3/workflows")
    if resp3.status_code == 200:
        wfs = resp3.json().get("workflows", [])
        for w in wfs:
            wid = w.get("id")
            if wid:
                det = client.get(f"/automation/v3/workflows/{wid}")
                if det.status_code == 200:
                    detailed_workflows.append(det.json())
                else:
                    detailed_workflows.append(w)
            else:
                detailed_workflows.append(w)
        return detailed_workflows

    return detailed_workflows


# ---------------------------------------------------------------------------
# Workflow parsing
# ---------------------------------------------------------------------------

def _extract_v4_triggers(flow: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts trigger criteria from v4 enrollmentCriteria."""
    triggers = []
    crit = flow.get("enrollmentCriteria", {})
    lfb = crit.get("listFilterBranch", {})
    
    for branch in lfb.get("filterBranches", []):
        for f in branch.get("filters", []):
            prop = f.get("property")
            op = f.get("operation", {})
            operator = op.get("operator", "")
            val = op.get("value")
            triggers.append({
                "raw_type": "PROPERTY",
                "property": prop,
                "operator": operator,
                "value": val,
                "summary": f"Property '{prop}' {operator} {val}",
                "supported": True
            })

    # Direct filters
    for f in lfb.get("filters", []):
        prop = f.get("property")
        op = f.get("operation", {})
        operator = op.get("operator", "")
        val = op.get("value")
        triggers.append({
            "raw_type": "PROPERTY",
            "property": prop,
            "operator": operator,
            "value": val,
            "summary": f"Property '{prop}' {operator} {val}",
            "supported": True
        })

    # v3 segmentCriteria fallback
    for seg_group in flow.get("segmentCriteria", []):
        for sc in seg_group:
            prop = sc.get("property")
            val = sc.get("value")
            op = sc.get("operator", "")
            triggers.append({
                "raw_type": "PROPERTY",
                "property": prop,
                "operator": op,
                "value": val,
                "summary": f"Property '{prop}' {op} {val}",
                "supported": True
            })

    return triggers


def _parse_actions(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse workflow actions into human-readable summaries."""
    parsed = []
    for action in actions:
        a_type = action.get("type") or action.get("actionTypeId") or "UNKNOWN"
        fields = action.get("fields", {})
        
        # Check v4 property set
        prop_name = fields.get("property_name") or action.get("propertyName")
        raw_val = fields.get("value", {})
        val = raw_val.get("staticValue") if isinstance(raw_val, dict) else (raw_val or action.get("newValue"))

        entry: Dict[str, Any] = {"type": a_type}

        if prop_name:
            entry["summary"] = f"Set property: {prop_name} = {val}"
            entry["property"] = prop_name
            entry["value"] = val
            if prop_name == "lifecyclestage" and val == "salesqualifiedlead":
                entry["is_sql_transition"] = True
        elif a_type in ("ROTATE_RECORD_OWNER", "SET_OWNER", "0-6"):
            entry["summary"] = "Route to sales rep / rotate owner"
            entry["is_routing"] = True
        elif a_type in ("CREATE_TASK", "TASK", "0-3"):
            entry["summary"] = "Create follow-up sales task"
        elif a_type in ("SEND_EMAIL", "AUTOMATED_EMAIL", "0-1"):
            entry["summary"] = "Send automated marketing email"
        else:
            entry["summary"] = f"Action: {a_type}"

        parsed.append(entry)
    return parsed


def _workflow_to_rules(
    workflow: Dict[str, Any],
    triggers: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Convert parsed workflow triggers and actions into scoring & routing rules."""
    rules = []
    wf_id = str(workflow.get("id") or "")
    wf_name = workflow.get("name", "Unnamed Workflow")

    if not triggers:
        # Check if flow title indicates score-based intent
        if "score" in wf_name.lower() or "sql" in wf_name.lower() or "hot" in wf_name.lower():
            rules.append({
                "workflow_id": wf_id,
                "rule_type": "score_boost",
                "trigger_type": "workflow_action",
                "field_name": "lifecyclestage",
                "field_value": "salesqualifiedlead",
                "score_delta": 25.0,
                "description": f"[{wf_name}] Workflow qualifies lead as Sales Qualified Lead (+25 pts)",
            })
            return rules, None
        return [], "No enrollment criteria or triggers found in workflow"

    for trig in triggers:
        prop = trig.get("property")
        val = trig.get("value")
        op = trig.get("operator", "")
        
        # Determine score delta
        delta = 20.0
        if "score" in str(prop).lower():
            delta = 25.0
        elif prop in PROPERTY_SCORE_MAP and str(val).lower() in PROPERTY_SCORE_MAP[prop]:
            delta = float(PROPERTY_SCORE_MAP[prop][str(val).lower()])

        rules.append({
            "workflow_id": wf_id,
            "rule_type": "score_boost" if delta >= 0 else "score_penalty",
            "trigger_type": "property_change",
            "field_name": prop,
            "field_value": str(val) if val is not None else None,
            "score_delta": delta,
            "description": f"[{wf_name}] {trig['summary']} (+{delta:.0f} pts)",
        })

    # Action-based bonus
    for action in actions:
        if action.get("is_sql_transition"):
            rules.append({
                "workflow_id": wf_id,
                "rule_type": "score_boost",
                "trigger_type": "lifecycle_transition",
                "field_name": "lifecyclestage",
                "field_value": "salesqualifiedlead",
                "score_delta": 15.0,
                "description": f"[{wf_name}] Action sets Lifecycle Stage to Sales Qualified Lead (+15 pts)",
            })
        elif action.get("is_routing"):
            rules.append({
                "workflow_id": wf_id,
                "rule_type": "routing",
                "trigger_type": "workflow_routing",
                "field_name": "workflow_name",
                "field_value": wf_name,
                "score_delta": 0.0,
                "description": f"[{wf_name}] Action rotates record owner to sales rep",
            })

    return rules, None


# ---------------------------------------------------------------------------
# Main import function
# ---------------------------------------------------------------------------

def import_workflows(db: Session, triggered_by: str = "manual") -> Dict[str, Any]:
    """Pull workflows from HubSpot, parse them, store in DB, and convert to scoring rules."""
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
    except Exception as e:
        result["errors"].append(str(e))
        _log_sync(db, "import", "error", result, error=str(e))
        return result

    result["workflows_found"] = len(raw_workflows)

    # Clear old scoring rules for fresh derivation
    db.query(HubSpotScoringRule).delete()

    for wf in raw_workflows:
        wf_id = str(wf.get("id") or wf.get("flowId") or "")
        wf_name = wf.get("name", "Unnamed Workflow")
        wf_type = wf.get("flowType") or wf.get("type") or "WORKFLOW"
        wf_status = wf.get("isEnabled") if "isEnabled" in wf else wf.get("enabled", False)
        status_str = "ACTIVE" if wf_status else "INACTIVE"

        triggers = _extract_v4_triggers(wf)
        actions = _parse_actions(wf.get("actions", []))

        trigger_summary = {"summary": " & ".join(t["summary"] for t in triggers)} if triggers else {"summary": "No trigger", "supported": False}

        rules, not_mapped_reason = _workflow_to_rules(wf, triggers, actions)
        mapped = len(rules) > 0

        existing = db.query(HubSpotWorkflow).filter(HubSpotWorkflow.hubspot_id == wf_id).first()
        if existing:
            existing.name = wf_name
            existing.workflow_type = wf_type
            existing.status = status_str
            existing.enrollment_trigger_summary = json.dumps(trigger_summary)
            existing.actions_summary = json.dumps(actions)
            existing.mapped = mapped
            existing.not_mapped_reason = not_mapped_reason
            existing.synced_at = now
        else:
            db.add(HubSpotWorkflow(
                hubspot_id=wf_id,
                name=wf_name,
                workflow_type=wf_type,
                status=status_str,
                enrollment_trigger_summary=json.dumps(trigger_summary),
                actions_summary=json.dumps(actions),
                mapped=mapped,
                not_mapped_reason=not_mapped_reason,
                synced_at=now,
            ))

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
        pass


def handle_webhook_event(db: Session, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    processed = 0
    skipped = 0

    for event in events:
        sub_type = event.get("subscriptionType", "")
        prop_name = event.get("propertyName", "")
        prop_value = event.get("propertyValue", "")

        if "contact" not in sub_type.lower():
            skipped += 1
            continue

        lead = None
        if prop_name == "email" and prop_value:
            lead = db.query(CleanLead).filter(
                CleanLead.email == prop_value.lower().strip()
            ).first()

        if lead:
            if prop_name == "hs_lead_status" and prop_value == "unqualified":
                lead.score_band = "Cold"
                lead.is_junk = True
                lead.junk_reason = "Marked unqualified in HubSpot"
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


def get_active_rules(db: Session) -> List[Dict[str, Any]]:
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
    delta = 0.0
    for rule in rules:
        if rule["rule_type"] not in ("score_boost", "score_penalty"):
            continue
        trigger = rule.get("trigger_type", "")
        field = rule.get("field_name")
        expected_value = (rule.get("field_value") or "").lower()

        if trigger == "property_change" and field:
            lead_val = str(lead.get(field) or lead.get(field.replace("hs_", ""), "")).lower()
            if expected_value and (lead_val == expected_value or expected_value in lead_val):
                delta += rule["score_delta"]
            elif not expected_value and lead_val:
                delta += min(rule["score_delta"], 5.0)
        elif trigger in ("lifecycle_transition", "workflow_action"):
            delta += rule.get("score_delta", 0.0)

    return delta
