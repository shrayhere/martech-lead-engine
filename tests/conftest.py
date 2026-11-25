import os
import sys
import tempfile
import pytest

os.environ["TESTING"] = "1"
os.environ.setdefault("APP_PASSWORD", "testpass123")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-1234567890")
_TEST_DIR = tempfile.mkdtemp(prefix="martech_root_tests_")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or \
    "sqlite:///" + os.path.join(_TEST_DIR, "test_martech.db").replace("\\", "/")

# Add backend directory to sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from starlette.testclient import TestClient
_orig_request = TestClient.request

def _patched_request(self, *args, **kwargs):
    headers = dict(kwargs.get("headers") or {})
    if headers.get("X-No-Auth") == "1":
        del headers["X-No-Auth"]
        kwargs["headers"] = headers
        self.cookies.clear()
    else:
        if "Authorization" not in headers:
            from app.services.auth_service import create_session_token
            headers["Authorization"] = f"Bearer {create_session_token()}"
            kwargs["headers"] = headers
    return _orig_request(self, *args, **kwargs)

TestClient.request = _patched_request
