"""Tests for the data-quality score, human review queue, AI classification and HubSpot sync."""
import io
import json
import os
import sys
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.schemas import CleanLead, MergedLeadLog  # noqa: E402
from app.services import classifier, hubspot_sync  # noqa: E402
from app.services.fast_dedup import fast_deduplicate_leads  # noqa: E402
from app.services.quality_service import compute_quality  # noqa: E402

client = TestClient(app)

BASE = {"job_title": "VP of Sales", "state": "California", "industry": "SaaS", "company_size": 500,
        "engagement_score": 70, "last_activity_date": "2026-11-01"}
# Guarded fuzzy pair that scores ~81% (inside the 80-90% review band): same last name, similar first name,
# same company, different email local part, different phone.
BORDERLINE = [
    {**BASE, "first_name": "Michael", "last_name": "Rodriguez", "company": "Acme Corp",
     "email": "michael.rodriguez@acmecorp.com", "phone": "(415) 555-0101"},
    {**BASE, "first_name": "Micheal", "last_name": "Rodriguez", "company": "Acme Corp",
     "email": "m.rodriguez@acmecorp.com", "phone": "(415) 555-0199"},
]
OTHERS = [
    {**BASE, "first_name": "Ana", "last_name": "Lopez", "company": "Apex Global", "email": "ana@apexglobal.com",
     "phone": "212-555-0102", "state": "NY", "job_title": "Marketing Coordinator"},
    {**BASE, "first_name": "Ana", "last_name": "Lopez", "company": "Apex Global", "email": "ana@apexglobal.com",
     "phone": "", "state": "ny"},  # exact email duplicate -> auto-merged
    {**BASE, "first_name": "Test", "last_name": "User", "company": "test company", "email": "",
     "phone": "", "job_title": "Tester"},  # junk
]


@pytest.fixture(autouse=True)
def empty_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def upload_and_clean(rows):
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    r = client.post("/api/leads/upload", files={"file": ("t.csv", buf.getvalue().encode(), "text/csv")})
    assert r.status_code == 200, r.text
    r = client.post("/api/leads/clean")
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ data-quality score
def test_quality_score_before_after_and_top_issues():
    report = upload_and_clean(BORDERLINE + OTHERS)
    assert report["duplicate_records_merged"] == 1
    client.post("/api/leads/score?mode=rule")
    client.post("/api/leads/assign")
    q = client.get("/api/quality/report").json()
    before, after = q["before"], q["after"]
    assert before["total_records"] == 5 and after["total_records"] == 3  # 2 borderline + Ana; junk excluded
    assert after["score"] > before["score"] and q["score_improvement"] > 0
    assert after["metrics"]["phone_e164"] == 100.0 and before["metrics"]["phone_e164"] == 0.0
    assert before["metrics"]["not_duplicate"] == 80.0 and after["metrics"]["not_duplicate"] == 100.0
    assert after["missing_owner_pct"] == 0.0 and before["missing_owner_pct"] is None
    assert len(before["top_issues"]) <= 5
    counts = [i["records"] for i in before["top_issues"]]
    assert counts == sorted(counts, reverse=True)
    assert q["junk_flagged_and_excluded"] == 1


def test_compute_quality_flags_invalid_email_and_placeholder():
    q = compute_quality([{"email": "not-an-email", "phone": "+14155550101", "state": "CA", "company": "n/a",
                          "job_title": "CEO", "industry": "SaaS"}], include_owner=False)
    assert q["metrics"]["valid_email"] == 0.0 and q["metrics"]["has_company"] == 0.0
    assert q["metrics"]["phone_e164"] == 100.0 and q["metrics"]["has_owner"] is None


# ------------------------------------------------------------------ human review queue
def test_borderline_pair_goes_to_review_not_auto_merge():
    report = upload_and_clean(BORDERLINE + OTHERS)
    assert report["borderline_pairs_queued_for_review"] == 1
    assert report["junk_rows_queued_for_review"] == 1
    db = SessionLocal()
    try:
        assert db.query(CleanLead).filter(CleanLead.last_name == "Rodriguez").count() == 2  # not merged yet
    finally:
        db.close()
    items = client.get("/api/review?item_type=merge").json()["items"]
    assert len(items) == 1 and 80 <= items[0]["similarity_score"] < 90

    r = client.post(f"/api/review/{items[0]['id']}/approve", json={"note": "same person"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    db = SessionLocal()
    try:
        assert db.query(CleanLead).filter(CleanLead.last_name == "Rodriguez").count() == 1
        log = db.query(MergedLeadLog).filter(MergedLeadLog.merge_reason.like("Approved by reviewer%")).one()
        assert log.winner_raw_lead_id != log.archived_raw_lead_id and log.id_type == "raw_lead_id"
    finally:
        db.close()
    assert client.post(f"/api/review/{items[0]['id']}/reject").status_code == 400  # already resolved


def test_reject_merge_keeps_both_and_junk_decisions():
    upload_and_clean(BORDERLINE + OTHERS)
    merge = client.get("/api/review?item_type=merge").json()["items"][0]
    assert client.post(f"/api/review/{merge['id']}/reject").json()["status"] == "rejected"
    junk = client.get("/api/review?item_type=junk").json()["items"][0]
    assert client.post(f"/api/review/{junk['id']}/reject").status_code == 200
    db = SessionLocal()
    try:
        assert db.query(CleanLead).filter(CleanLead.last_name == "Rodriguez").count() == 2
        restored = db.query(CleanLead).filter(CleanLead.first_name == "Test").one()
        assert restored.is_junk is False
    finally:
        db.close()
    summary = client.get("/api/review?status=all").json()["summary"]
    assert summary["rejected"] == 2 and summary["pending"] == 0


def test_fast_dedup_returns_review_pairs_instead_of_merging():
    leads = [dict(l, row_index=i + 2, is_junk=False, phone=None) for i, l in enumerate(BORDERLINE)]
    winners, logs, stats = fast_deduplicate_leads(leads, "unit", threshold=85.0)
    assert len(winners) == 2 and logs == []
    assert len(stats["review_pairs"]) == 1 and 80 <= stats["review_pairs"][0]["similarity_score"] < 90


# ------------------------------------------------------------------ AI classification
def test_local_classifier_accuracy_on_held_out_titles():
    r = classifier.evaluate("local")
    assert r["titles_also_in_training"] == []          # no leakage between train and test
    assert r["test_titles"] >= 60
    for label in classifier.TARGETS:
        assert r["accuracy_pct"][label] >= 85.0, r


def test_unusable_titles_and_business_rules():
    out = classifier.classify_titles_local(["", "n/a", "Chief Marketing Officer"])
    assert out[0]["persona"] == "Unknown" and out[1]["buying_role"] == "Unknown"
    assert out[2]["persona"] == "Executive" and out[2]["interest"] == "Demand Generation"
    assert classifier.recommend_action("Sales", "Decision Maker", "Sales Productivity", "Hot").startswith("Route to")
    assert "SDR call" in classifier.recommend_action("Marketing", "Influencer", "Demand Generation", "Hot")
    assert classifier.recommend_action("Sales", "End User", "Sales Productivity", "Cold").startswith("Add to")
    assert classifier.recommend_action("Unknown", "Unknown", "Unknown", "Hot").startswith("Enrich")
    assert classifier.recommend_action("Sales", "Decision Maker", "x", "Hot", is_junk=True).startswith("Exclude")


class FakeClaude:
    """Stands in for anthropic.Anthropic(); records calls, returns structured output or a refusal."""

    def __init__(self, refuse=False):
        self.calls = []
        self.refuse = refuse
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.refuse:
            return SimpleNamespace(stop_reason="refusal", content=[])
        titles = [line.split(": ", 1) for line in kwargs["messages"][0]["content"].splitlines()[1:]]
        labels = [{"index": int(i), "persona": "Sales", "buying_role": "Influencer",
                   "interest": "Sales Productivity"} for i, _ in titles]
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps({"labels": labels}))])


def test_claude_engine_uses_structured_output_and_falls_back_on_refusal():
    fake = FakeClaude()
    out = classifier.classify_titles_claude(["Head of Sales", "Head of Sales", "", "Data Engineer"], client=fake)
    assert len(fake.calls) == 1  # distinct titles only, one batch
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["output_config"]["format"]["type"] == "json_schema"
    assert out[0]["engine"] == "claude" and out[2]["engine"] == "rule"
    refused = classifier.classify_titles_claude(["Head of Sales"], client=FakeClaude(refuse=True))
    assert refused[0]["engine"] == "local"  # refusal -> local model


def test_classify_api_labels_leads_and_pipeline_auto_classifies():
    upload_and_clean(BORDERLINE + OTHERS)
    r = client.post("/api/classify/run")
    assert r.status_code == 200 and r.json()["leads_classified"] == 4
    leads = client.get("/api/classify/leads").json()["leads"]
    assert all(l["persona"] and l["recommended_action"] for l in leads)
    assert client.post("/api/classify/run?engine=claude").status_code in (200, 400)  # 400 without a key

    buf = io.StringIO()
    pd.DataFrame(BORDERLINE + OTHERS).to_csv(buf, index=False)
    run = client.post("/api/pipeline/run", files={"file": ("p.csv", buf.getvalue().encode(), "text/csv")},
                      data={"scoring_mode": "rule"}).json()
    run_leads = client.get(f"/api/classify/leads?run_id={run['run_id']}").json()["leads"]
    assert run_leads and all(l["persona"] and l["recommended_action"] for l in run_leads)
    assert client.get(f"/api/review?run_id={run['run_id']}&item_type=merge").json()["summary"]["merge_pending"] == 1


# ------------------------------------------------------------------ HubSpot sync
def test_hubspot_dry_run_excludes_junk_and_needs_no_token(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    upload_and_clean(BORDERLINE + OTHERS)
    r = client.post("/api/hubspot/sync", json={"dry_run": True}).json()
    assert r["dry_run"] and r["contacts_selected"] == 3  # junk row (no email) excluded
    props = r["preview"][0]["properties"]
    assert "email" in props and all(v not in (None, "") for v in props.values())
    assert client.post("/api/hubspot/sync", json={"dry_run": False}).status_code == 400  # no token


def test_hubspot_real_sync_with_mock_transport(monkeypatch):
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "pat-test-not-a-real-token")
    upload_and_clean(BORDERLINE + OTHERS)
    client.post("/api/leads/score?mode=rule")
    client.post("/api/classify/run")
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        assert request.headers["authorization"] == "Bearer pat-test-not-a-real-token"
        if request.url.path.endswith("/groups"):
            return httpx.Response(409, json={"message": "exists"})
        if request.url.path == "/crm/v3/properties/contacts":
            return httpx.Response(201, json={})
        body = json.loads(request.content)
        assert len(body["inputs"]) <= 100 and all(i["idProperty"] == "email" for i in body["inputs"])
        return httpx.Response(200, json={"results": [{"properties": {"email": i["id"]}} for i in body["inputs"]]})

    db = SessionLocal()
    try:
        result = hubspot_sync.sync_leads(db, None, dry_run=False, transport=httpx.MockTransport(handler))
        assert result["contacts_upserted"] == 3 and result["errors"] == []
        assert result["properties"]["group"] == "exists"
        assert db.query(CleanLead).filter(CleanLead.hubspot_synced_at.isnot(None)).count() == 3
    finally:
        db.close()
    assert any(r.url.path.endswith("/batch/upsert") for r in seen)
