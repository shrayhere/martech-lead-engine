import os
import io
import csv
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.services.sample_generator import generate_sample_leads_csv

# Separate test database (set in tests/conftest.py before the app is imported)
TEST_DB_URL = os.environ["DATABASE_URL"]
TEST_DB_PATH = TEST_DB_URL.replace("sqlite:///", "") if TEST_DB_URL.startswith("sqlite") else None
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False} if TEST_DB_PATH else {})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        from app.services.assignment_service import seed_sales_reps
        seed_sales_reps(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    from app.database import engine as app_engine
    app_engine.dispose()
    if TEST_DB_PATH and os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

@pytest.fixture
def client():
    return TestClient(app)

# -------------------------------------------------------------------
# FIXTURE 1: Synthetic Standard CSV (200 Leads)
# -------------------------------------------------------------------
def test_fixture_1_synthetic_csv(client):
    csv_bytes = generate_sample_leads_csv(200).encode("utf-8")
    response = client.post(
        "/api/pipeline/run",
        files={"file": ("sample_200.csv", csv_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "run_id" in data
    run_id = data["run_id"]
    summary = data["summary"]
    assert summary["rows_in"] == 200
    assert summary["rows_out"] > 0
    assert summary["total_time_ms"] > 0

    # Test Lead Lists endpoints for this run
    band_res = client.get(f"/api/leads/band-summary?run_id={run_id}")
    assert band_res.status_code == 200
    band_data = band_res.json()
    assert band_data["total"] == summary.get("active_leads", summary["rows_out"] - summary.get("junk_removed", 0))
    assert "hot" in band_data and "warm" in band_data and "cold" in band_data

    # Test Hot leads view
    hot_res = client.get(f"/api/leads/by-band?run_id={run_id}&band=hot")
    assert hot_res.status_code == 200
    hot_data = hot_res.json()
    assert isinstance(hot_data["leads"], list)
    for l in hot_data["leads"]:
        assert l["band"] == "Hot"
        assert l["score"] >= 80.0
        assert len(l["top_3_reasons"]) > 0

# -------------------------------------------------------------------
# FIXTURE 2: Completely Different Column Names & Order
# -------------------------------------------------------------------
def test_fixture_2_different_columns_and_order(client):
    rows = [
        ["Contact Person", "Account Firm", "Role Name", "Contact Mail", "Direct Dial", "Territory Code", "Domain", "Head Count", "Last Interaction"],
        ["Alice Henderson", "Alpha Cloud Inc", "VP of Engineering", "alice.h@alphacloud.io", "+1-415-555-0199", "CA", "Cloud Computing", "1200", "2026-03-01"],
        ["Bob Vance", "Vance Refrigeration", "President", "bob@vancerefrig.com", "2125550188", "NY", "Manufacturing", "65", "2026-02-15"],
        ["Carol Danvers", "Danvers Tech", "CEO", "carol@danverstech.com", "3125550177", "IL", "Software", "450", "2026-03-10"],
        ["David Miller", "Apex Fintech", "Director of IT", "david.m@apexfin.com", "4045550166", "GA", "Fintech", "3500", "2026-01-20"]
    ]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(rows)
    csv_bytes = out.getvalue().encode("utf-8")

    response = client.post(
        "/api/pipeline/run",
        files={"file": ("custom_headers.csv", csv_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    run_id = data["run_id"]
    assert data["summary"]["rows_out"] >= 4

    # Check schema mapping detected headers
    mapping = data["column_mapping"]["canonical_to_source"]
    assert "email" in mapping
    assert "company" in mapping

    # Verify leads retrieved correctly
    leads_res = client.get(f"/api/leads/by-band?run_id={run_id}&band=all")
    assert leads_res.status_code == 200
    leads = leads_res.json()["leads"]
    assert len(leads) >= 4
    assert any("Alice" in l["name"] for l in leads)

# -------------------------------------------------------------------
# FIXTURE 3: Semicolon Delimiter & Latin-1 Encoding
# -------------------------------------------------------------------
def test_fixture_3_semicolon_and_latin1_encoding(client):
    csv_text = (
        "Name;Email;Phone;Company;Title;State;Industry;Company Size\n"
        "François Müller;francois@mueller-tech.de;+14155551234;Müller Corp;CTO;CA;SaaS;250\n"
        "Renée Dupont;renee@dupont-sante.fr;+12125554321;Santé Solutions;CEO;NY;Healthcare IT;800\n"
        "Inés González;ines@gonzalez.es;+15125558899;González Global;Director;TX;Fintech;1500\n"
    )
    latin1_bytes = csv_text.encode("latin-1")

    response = client.post(
        "/api/pipeline/run",
        files={"file": ("latin1_semicolon.csv", latin1_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["summary"]["rows_out"] == 3

    # Check that French/German/Spanish characters were decoded properly
    leads_res = client.get(f"/api/leads/by-band?run_id={data['run_id']}&band=all")
    leads = leads_res.json()["leads"]
    names = [l["name"] for l in leads]
    assert any("François" in n or "Francois" in n for n in names)

# -------------------------------------------------------------------
# FIXTURE 4: Missing Engagement & Date Columns (Graceful Degradation)
# -------------------------------------------------------------------
def test_fixture_4_missing_engagement_and_date_signals(client):
    csv_text = (
        "First Name,Last Name,Email,Phone,Company,Job Title,State,Industry,Company Size\n"
        "Samantha,Reed,samantha@reedcorp.com,+14155557766,Reed Cloud,VP of Engineering,CA,Cloud Computing,5500\n"
        "Timothy,Walsh,timothy@walsh.io,+12125556655,Walsh Analytics,Data Scientist,NY,Software,120\n"
        "Karen,Gillan,karen@gillanit.com,+13125554433,Gillan IT,Founder & CEO,IL,Healthcare IT,850\n"
    )
    csv_bytes = csv_text.encode("utf-8")

    response = client.post(
        "/api/pipeline/run",
        files={"file": ("missing_signals.csv", csv_bytes, "text/csv")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Check graceful degradation flags
    degraded = data["degraded_signals"]
    assert "engagement" in degraded or "recency" in degraded

    # Verify re-normalized weights sum to 1.0
    weights = data["re_normalized_weights"]
    total_w = sum(weights.values())
    assert 0.99 <= total_w <= 1.01

    # Verify leads were scored and assigned bands
    leads_res = client.get(f"/api/leads/by-band?run_id={data['run_id']}&band=all")
    leads = leads_res.json()["leads"]
    assert len(leads) == 3
    for l in leads:
        assert l["score"] > 0
        assert l["band"] in ["Hot", "Warm", "Cold"]

# -------------------------------------------------------------------
# FIXTURE 5: Empty & Garbage Files
# -------------------------------------------------------------------
def test_fixture_5_empty_file_rejected(client):
    response = client.post(
        "/api/pipeline/run",
        files={"file": ("empty.csv", b"", "text/csv")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()

def test_fixture_5_garbage_binary_file_rejected(client):
    garbage_bytes = b"\x00\x01\x02\x03\xff\xfe\x00\x12binarygarbagebytes"
    response = client.post(
        "/api/pipeline/run",
        files={"file": ("corrupt.csv", garbage_bytes, "text/csv")}
    )
    assert response.status_code == 400
    assert "binary" in response.json()["detail"].lower()

# -------------------------------------------------------------------
# Pipeline Status & Past Runs
# -------------------------------------------------------------------
def test_pipeline_status_and_runs_list(client):
    csv_bytes = generate_sample_leads_csv(50).encode("utf-8")
    run_res = client.post(
        "/api/pipeline/run",
        files={"file": ("test_run.csv", csv_bytes, "text/csv")}
    )
    run_id = run_res.json()["run_id"]

    # Status endpoint
    status_res = client.get(f"/api/pipeline/status/{run_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "completed"
    assert status_data["progress_percent"] == 100

    # Runs list endpoint
    runs_res = client.get("/api/pipeline/runs")
    assert runs_res.status_code == 200
    runs = runs_res.json()["runs"]
    assert len(runs) > 0
    assert any(r["run_id"] == run_id for r in runs)

# -------------------------------------------------------------------
# Band Filtering, Search & Export
# -------------------------------------------------------------------
def test_leads_by_band_search_and_export(client):
    csv_bytes = generate_sample_leads_csv(100).encode("utf-8")
    run_res = client.post(
        "/api/pipeline/run",
        files={"file": ("leads_test.csv", csv_bytes, "text/csv")}
    )
    run_id = run_res.json()["run_id"]

    # Search by band
    hot_res = client.get(f"/api/leads/by-band?run_id={run_id}&band=hot&limit=10")
    assert hot_res.status_code == 200
    hot_leads = hot_res.json()["leads"]
    assert all(l["band"] == "Hot" for l in hot_leads)

    # Search with query
    search_res = client.get(f"/api/leads/by-band?run_id={run_id}&band=all&q=VP")
    assert search_res.status_code == 200

    # Export CSV
    export_res = client.get(f"/api/leads/export?run_id={run_id}&band=hot")
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers["content-type"]
    assert "ID,Name,Email" in export_res.text

# -------------------------------------------------------------------
# Backwards Compatibility: Existing Endpoints Still Work
# -------------------------------------------------------------------
def test_existing_endpoints_unbroken(client):
    # Health check
    h_res = client.get("/api/health")
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "healthy"

    # Sample CSV download
    s_res = client.get("/api/leads/sample-csv")
    assert s_res.status_code == 200
    assert "text/csv" in s_res.headers["content-type"]

    # Reps overview
    r_res = client.get("/api/leads/reps")
    assert r_res.status_code == 200
    assert r_res.json()["count"] > 0
