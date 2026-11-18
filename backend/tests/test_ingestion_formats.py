"""The staged "1. Ingestion" upload accepts the same files as Smart Upload (delimiters, encodings, header names)."""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

HEADER = ["Full Name", "E-mail Address", "Org", "Position", "Tel", "Region", "Engagement %", "Last Touch"]
ROWS = [
    ["  priya SHARMA ", "PRIYA.SHARMA@NovaCloud.io", "novacloud inc", "VP Sales", "(415) 555 0101", "calif", "92%", "2026-11-10"],
    ["James O'Neil", "james.oneil@finbridge.com", "FinBridge", "Chief Financial Officer", "+1 212 555 0144", "New York", "71", "2026-10-02"],
]


@pytest.fixture(autouse=True)
def empty_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.mark.parametrize("sep,encoding", [(",", "utf-8"), (";", "utf-8"), ("\t", "utf-8"), (";", "utf-8-sig"), (";", "cp1252")])
def test_staged_upload_accepts_delimiters_and_encodings(sep, encoding):
    text = "\n".join(sep.join(r) for r in [HEADER] + ROWS) + "\n"
    r = client.post("/api/leads/upload", files={"file": ("leads.csv", text.encode(encoding), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["records_ingested"] == 2
    for field in ("first_name", "last_name", "email", "company", "job_title", "phone", "state",
                  "engagement_score", "last_activity_date"):
        assert field in body["columns_mapped"], (field, body["columns_mapped"])
    raw = client.get("/api/leads/raw").json()["leads"]
    priya = next(l for l in raw if (l["email"] or "").lower().startswith("priya"))
    assert priya["first_name"] == "priya" and priya["last_name"] == "SHARMA"
    assert priya["engagement_score"] == 92.0


def test_staged_upload_still_rejects_files_without_contact_columns():
    r = client.post("/api/leads/upload", files={"file": ("x.csv", b"foo;bar\n1;2\n", "text/csv")})
    assert r.status_code == 400 and "identifiable contact column" in r.json()["detail"]
