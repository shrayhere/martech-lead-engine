"""Point the whole app at a throw-away test database BEFORE any app module is imported,
so tests never create or modify the main martech.db."""
import os
import tempfile

os.environ["TESTING"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="martech_tests_")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or \
    "sqlite:///" + os.path.join(_TEST_DIR, "test_martech.db").replace("\\", "/")

# Patch TestClient to automatically attach session token unless X-No-Auth is passed
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
