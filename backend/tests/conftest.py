"""Point the whole app at a throw-away test database BEFORE any app module is imported,
so tests never create or modify the main martech.db."""
import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="martech_tests_")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or \
    "sqlite:///" + os.path.join(_TEST_DIR, "test_martech.db").replace("\\", "/")
