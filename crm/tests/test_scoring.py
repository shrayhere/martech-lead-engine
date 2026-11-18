from datetime import timedelta

from app.models import DEFAULT_SCORING_RULES, AuditLog
from app.models.base import utcnow
from app.services.lead_scoring import category_for, compute_score

POINTS = {k: v[1] for k, v in DEFAULT_SCORING_RULES.items()}


def test_compute_score_rules():
    now = utcnow()
    recent = now - timedelta(days=2)
    assert compute_score([("demo_requested", recent), ("pricing_inquiry", recent)], POINTS, now)[0] == 70
    assert compute_score([("email_opened", recent)], POINTS, now)[0] == 5
    many = [(t, recent) for t in ("demo_requested", "pricing_inquiry", "meeting_scheduled", "form_submitted")]
    assert compute_score(many, POINTS, now)[0] == 100  # bounded at 100
    old = now - timedelta(days=45)
    score, last, penalty = compute_score([("demo_requested", old)], POINTS, now)
    assert (score, penalty) == (25, True) and last == old  # 40 - 15
    assert compute_score([("email_opened", old)], POINTS, now)[0] == 0  # bounded at 0
    logged = [("pricing_inquiry", recent), ("no_recent_engagement", now)]
    assert compute_score(logged, POINTS, now)[0] == 15
    assert compute_score([], POINTS, now)[0] == 0


def test_category_bands():
    assert [category_for(s) for s in (0, 29, 30, 59, 60, 100)] == ["cold", "cold", "warm", "warm", "hot", "hot"]


def _contact(client, **fields):
    resp = client.post("/api/contacts", json={"first_name": "Lead", "email": "lead@example.com", **fields})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["contact"]


def test_activities_recalculate_score(auth):
    c = _contact(auth)
    assert (c["lead_score"], c["lead_category"]) == (0, "cold")
    cid = c["contact_id"]
    r = auth.post(f"/api/contacts/{cid}/activities", json={"activity_type": "demo_requested"})
    assert r.status_code == 201 and r.get_json()["contact"]["lead_score"] == 40
    assert r.get_json()["contact"]["lead_category"] == "warm"
    r = auth.post(f"/api/contacts/{cid}/activities", json={"activity_type": "pricing_inquiry"})
    act_id = r.get_json()["activity"]["activity_id"]
    assert r.get_json()["contact"]["lead_category"] == "hot"
    r = auth.put(f"/api/activities/{act_id}", json={"activity_type": "email_opened"})
    assert r.get_json()["contact"]["lead_score"] == 45
    r = auth.delete(f"/api/activities/{act_id}")
    assert r.get_json()["contact"]["lead_score"] == 40
    assert auth.post(f"/api/contacts/{cid}/activities", json={"activity_type": "bogus"}).status_code == 422
    detail = auth.get(f"/api/contacts/{cid}").get_json()
    assert detail["score_breakdown"]["score"] == 40 and detail["activities"][0]["activity_score"] == 40
    assert detail["contact"]["last_activity_at"]


def test_invalid_contacts_excluded_from_qualification(auth):
    c = _contact(auth, email=None, first_name="NoContactInfo")
    assert c["lead_category"] is None and c["lead_status"] == "excluded"
    r = auth.put(f"/api/leads/{c['contact_id']}/category", json={"category": "hot"})
    assert r.status_code == 422
    r = auth.put(f"/api/contacts/{c['contact_id']}", json={"phone": "+44 20 7946 0958"})
    assert r.get_json()["contact"]["lead_category"] == "cold"


def test_manual_override_preserves_auto_category_and_audits(auth):
    cid = _contact(auth)["contact_id"]
    r = auth.put(f"/api/leads/{cid}/category", json={"category": "hot", "reason": "Met at conference"})
    data = r.get_json()["contact"]
    assert data["lead_category"] == "hot" and data["lead_category_auto"] == "cold"
    log = AuditLog.query.filter_by(operation="category_override", entity_id=cid).one()
    assert log.to_dict()["new_values"]["reason"] == "Met at conference"
    auth.post(f"/api/contacts/{cid}/activities", json={"activity_type": "demo_requested"})
    data = auth.get(f"/api/leads/{cid}").get_json()["contact"]
    assert data["lead_category_auto"] == "warm" and data["lead_category"] == "hot"
    r = auth.put(f"/api/leads/{cid}/category", json={"category": None})
    assert r.get_json()["contact"]["lead_category"] == "warm"
    pipeline = auth.get("/api/leads/pipeline").get_json()["columns"]
    assert pipeline["warm"]["total"] == 1 and pipeline["hot"]["total"] == 0


def test_configurable_rules_rescore_everyone(auth):
    cid = _contact(auth)["contact_id"]
    auth.post(f"/api/contacts/{cid}/activities", json={"activity_type": "email_opened"})
    r = auth.put("/api/settings/scoring-rules", json={"rules": [{"activity_type": "email_opened", "points": 35}]})
    assert r.status_code == 200 and r.get_json()["changed"] == 1
    assert auth.get(f"/api/contacts/{cid}").get_json()["contact"]["lead_category"] == "warm"
    bad = auth.put("/api/settings/scoring-rules", json={"rules": [{"activity_type": "email_opened", "points": 500}]})
    assert bad.status_code == 422
    auth.put("/api/settings/scoring-rules", json={"reset": True})
    assert auth.get(f"/api/contacts/{cid}").get_json()["contact"]["lead_score"] == 5
