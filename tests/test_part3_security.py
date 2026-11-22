import os
import time
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import verify_password, create_session_token, verify_session_token
from app.utils.security import sanitize_csv_cell

client = TestClient(app)

def test_unauthenticated_api_returns_401():
    """Every /api route (except health, login, webhook) must reject unauthenticated requests with 401."""
    unauth = TestClient(app)
    unauth.cookies.clear()
    res = unauth.get("/api/pipeline/runs", headers={"X-No-Auth": "1"})
    assert res.status_code == 401
    assert "Authentication required" in res.json().get("detail", "")

    res_leads = unauth.get("/api/leads/raw", headers={"X-No-Auth": "1"})
    assert res_leads.status_code == 401


def test_public_routes_exempt_from_auth():
    """Health check, auth login/status are accessible without authentication."""
    res_health = client.get("/api/health", headers={"X-No-Auth": "1"})
    assert res_health.status_code == 200

    res_status = client.get("/api/auth/status", headers={"X-No-Auth": "1"})
    assert res_status.status_code == 200
    assert "authenticated" in res_status.json()


def test_login_flow_and_session_token():
    """Login with correct APP_PASSWORD returns 200, JWT token and sets session_token cookie."""
    # Bad password
    bad_res = client.post("/api/auth/login", json={"password": "wrong_password"})
    assert bad_res.status_code == 401

    # Good password
    good_res = client.post("/api/auth/login", json={"password": "martech2026"})
    assert good_res.status_code == 200
    data = good_res.json()
    assert "token" in data
    assert verify_session_token(data["token"]) is True
    assert "session_token" in good_res.cookies


def test_csv_formula_injection_sanitization():
    """Cells starting with =, +, -, @, \\t, or \\r must be prefixed with a single quote."""
    assert sanitize_csv_cell("=HYPERLINK('http://evil.com')") == "'=HYPERLINK('http://evil.com')"
    assert sanitize_csv_cell("+123456") == "'+123456"
    assert sanitize_csv_cell("-CMD") == "'-CMD"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("Regular Company") == "Regular Company"


def test_security_headers_present():
    """Security headers (CSP, X-Frame-Options, nosniff, Referrer-Policy) must be present."""
    res = client.get("/api/health")
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert "strict-origin" in res.headers.get("Referrer-Policy", "")
    assert "Content-Security-Policy" in res.headers
    assert "x-render-origin-server" not in res.headers


def test_hubspot_webhook_signature_verification():
    """HubSpot webhook requires valid HMAC-SHA256 signature and fresh timestamp (<= 5 min)."""
    secret = "test_hubspot_secret"
    os.environ["HUBSPOT_CLIENT_SECRET"] = secret

    # 1. Forged / invalid signature -> 401
    now_ms = str(int(time.time() * 1000))
    res_forged = client.post(
        "/api/hubspot/webhook",
        headers={"X-HubSpot-Signature-v3": "invalid_signature", "X-HubSpot-Request-Timestamp": now_ms},
        json={"event": "contact.creation"}
    )
    assert res_forged.status_code == 401

    # 2. Expired timestamp (> 5 minutes old) -> 401
    old_ms = str(int((time.time() - 301) * 1000))
    source = f"POSThttps://api.test.com/api/hubspot/webhook{old_ms}"
    sig = hmac.new(secret.encode("utf-8"), source.encode("utf-8"), hashlib.sha256).hexdigest()
    res_expired = client.post(
        "/api/hubspot/webhook",
        headers={"X-HubSpot-Signature-v3": sig, "X-HubSpot-Request-Timestamp": old_ms},
        json={"event": "contact.creation"}
    )
    assert res_expired.status_code == 401


def test_rate_limiting():
    """Requests exceeding limits (10/min upload, 60/min general) return 429."""
    os.environ["TEST_RATE_LIMIT"] = "1"
    try:
        from app.main import is_rate_limited
        ip = "192.168.1.100"
        # Test 10/min for upload
        for _ in range(10):
            assert is_rate_limited(ip, is_upload=True) is False
        assert is_rate_limited(ip, is_upload=True) is True
    finally:
        os.environ.pop("TEST_RATE_LIMIT", None)
