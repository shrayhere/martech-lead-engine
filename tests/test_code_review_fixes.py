import time
import hmac
import hashlib
import json
import pytest
from app.database import Base, engine, SessionLocal
from app.main import _login_reqs, is_rate_limited
from app.services.smart_scoring import smart_score_leads
from app.routes.settings import get_current_settings, update_settings, SettingsPayload


@pytest.fixture(autouse=True)
def init_tables():
    Base.metadata.create_all(bind=engine)
    yield


def test_item1_production_refuses_startup_without_secrets(monkeypatch):
    """Item 1: If ENV=production and APP_PASSWORD or SECRET_KEY is missing, app refuses to start."""
    import importlib
    import app.services.auth_service

    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv("SECRET_KEY", "some-secret-key-1234")

    with pytest.raises(RuntimeError) as exc_info:
        importlib.reload(app.services.auth_service)
    assert "APP_PASSWORD" in str(exc_info.value)

    monkeypatch.setenv("APP_PASSWORD", "some-pass-1234")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc_info2:
        importlib.reload(app.services.auth_service)
    assert "SECRET_KEY" in str(exc_info2.value)

    # Restore valid env and reload so subsequent imports stay clean
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("APP_PASSWORD", "testpass123")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-unit-tests-1234567890")
    importlib.reload(app.services.auth_service)


def _run_coro(coro):
    """Steps a simple async coroutine without opening an OS event-loop socketpair."""
    try:
        while True:
            coro.send(None)
    except StopIteration as stop:
        return stop.value


def test_item3_hubspot_webhook_signature_and_production_check(monkeypatch):
    """Item 3: In production, reject calls if HUBSPOT_CLIENT_SECRET is missing. Verify against WEBHOOK_PUBLIC_URL."""
    from app.routes.hubspot import hubspot_webhook

    # 1. Reject in production when HUBSPOT_CLIENT_SECRET is missing
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("HUBSPOT_CLIENT_SECRET", raising=False)

    class MockRequestMissingSecret:
        method = "POST"
        url = "http://localhost/api/hubspot/webhook"
        headers = {}
        async def body(self):
            return b"[]"

    db = SessionLocal()
    try:
        with pytest.raises(Exception) as exc:
            _run_coro(hubspot_webhook(MockRequestMissingSecret(), db))
        assert exc.value.status_code == 401

        # 2. Verify signature against WEBHOOK_PUBLIC_URL
        secret = "test-hubspot-secret-key"
        monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", secret)
        public_url = "https://martech.example.com/api/hubspot/webhook"
        monkeypatch.setenv("WEBHOOK_PUBLIC_URL", public_url)

        body = b'[{"subscriptionType": "contact.propertyChange"}]'
        ts = str(int(time.time() * 1000))
        source = f"POST{public_url}{body.decode()}{ts}"
        sig = hmac.new(secret.encode(), source.encode(), hashlib.sha256).hexdigest()

        class MockRequestValid:
            method = "POST"
            url = "http://internal-render-host/api/hubspot/webhook"
            headers = {
                "X-HubSpot-Signature-v3": sig,
                "X-HubSpot-Request-Timestamp": ts,
            }
            async def body(self):
                return body

        res = _run_coro(hubspot_webhook(MockRequestValid(), db))
        assert res["events_received"] == 1
    finally:
        db.close()


def test_item4_rate_limiting_xff_and_login_limit(monkeypatch):
    """Item 4: Rate limit takes IP from X-Forwarded-For (first IP), 5/min limit on /api/auth/login."""
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("TEST_RATE_LIMIT", "1")
    _login_reqs.clear()

    # Simulate client IP parsed from X-Forwarded-For: "203.0.113.195, 198.51.100.1"
    xff = "203.0.113.195, 198.51.100.1"
    client_ip = xff.split(",")[0].strip()

    for _ in range(5):
        assert is_rate_limited(client_ip, "login") is False

    # 6th attempt is rate-limited
    assert is_rate_limited(client_ip, "login") is True


def test_item7_settings_crud_in_db():
    """Item 7: GET/PUT /api/settings stores scoring weights and default country in DB."""
    db = SessionLocal()
    try:
        curr = get_current_settings(db)
        assert "country" in curr
        assert "weights" in curr

        payload = SettingsPayload(
            country="Germany",
            weights={
                "company_size": 20,
                "target_industry": 20,
                "title_seniority": 10,
                "engagement": 30,
                "recency": 20,
            },
        )
        res = update_settings(payload, db)
        assert res["success"] is True
        assert res["settings"]["country"] == "Germany"
        assert get_current_settings(db)["country"] == "Germany"

        # Verify invalid weights sum != 100 rejects with 400
        bad_payload = SettingsPayload(
            country="Germany",
            weights={"company_size": 10, "target_industry": 10, "title_seniority": 10, "engagement": 10, "recency": 10},
        )
        with pytest.raises(Exception) as exc:
            update_settings(bad_payload, db)
        assert exc.value.status_code == 400
    finally:
        db.close()


def test_item8_scoring_no_behavioral_data_capped_warm():
    """Item 8: If a lead has no behavioral data (no engagement AND no activity date), cap at Warm and label 'Fit score only'."""
    leads = [{
        "first_name": "Satya",
        "last_name": "Nadella",
        "company": "Microsoft",
        "job_title": "Chief Executive Officer",
        "company_size": 10000,
        "industry": "Software",
        "engagement_score": None,
        "last_activity_date": None,
        "is_junk": False,
    }]

    scored, _ = smart_score_leads(leads, scoring_mode="rule")
    lead = scored[0]
    assert lead["score_band"] == "Warm"
    assert lead["active_score"] <= 74.9
    breakdown = json.loads(lead["score_breakdown"])
    assert breakdown.get("fit_only") is True
    assert any("Fit score only" in r for r in breakdown.get("top_reasons", []))
