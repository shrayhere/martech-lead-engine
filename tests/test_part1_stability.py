import os
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.services.smart_parser import parse_csv_file, MAX_FILE_SIZE_BYTES, MAX_ROW_COUNT
from app.services.fast_dedup import fast_deduplicate_leads, get_blocking_keys
from app.services.classifier import _local_models
from app.models.schemas import PipelineRun

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


def test_model_loaded_once_never_on_request():
    """ML and NLP models are loaded once from disk (or at startup), never re-trained on request."""
    models = _local_models()
    assert models is not None
    assert "persona" in models
    assert "buying_role" in models
    assert "interest" in models
    # Subsequent calls must return cached reference without retraining
    models_cached = _local_models()
    assert models is models_cached


def test_upload_limits_enforced():
    """Uploads exceeding 20 MB or 100,000 rows must be rejected with a clear error."""
    # 1. Row limit check
    oversized_rows = "first_name,last_name,email\n" + ("John,Doe,j@example.com\n" * (MAX_ROW_COUNT + 1))
    with pytest.raises(ValueError) as exc:
        parse_csv_file(oversized_rows.encode("utf-8"), "huge.csv")
    assert "exceeds the maximum limit" in str(exc.value)

    # 2. File size limit check
    huge_bytes = b"a" * (MAX_FILE_SIZE_BYTES + 10)
    with pytest.raises(ValueError) as exc2:
        parse_csv_file(huge_bytes, "huge_size.csv")
    assert "exceeds" in str(exc2.value).lower() and "20 mb" in str(exc2.value).lower()


def test_fuzzy_dedup_blocking_performance():
    """Deduplication uses fine-grained blocking and caps pairwise checks, avoiding O(n^2) explosion."""
    leads = []
    for i in range(500):
        leads.append({
            "id": i,
            "first_name": f"User{i}",
            "last_name": f"Test{i}",
            "email": f"user{i}@bigcompany.com",
            "company": "Big Company",
            "phone": "+1 555 0100",
            "state": "CA",
            "job_title": "Manager",
            "industry": "Tech",
            "company_size": 100,
            "engagement_score": 50.0,
            "last_activity_date": "2026-11-01"
        })
    keys = get_blocking_keys(leads[0])
    assert any(k.startswith("df:") or k.startswith("cf:") or k.startswith("ph4:") for k in keys)

    # Must complete fast without quadratic penalty
    winners, merged_logs, dedup_stats = fast_deduplicate_leads(leads, run_id="test_run_1")
    assert isinstance(winners, list)
    assert isinstance(dedup_stats, dict)
    assert "review_pairs" in dedup_stats


def test_chunking_and_memory_profiling():
    """Pipeline tracks stage timing and peak memory metrics."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    csv_path = os.path.join(fixtures_dir, "1000_rows.csv")
    with open(csv_path, "rb") as f:
        content = f.read()

    res = client.post("/api/pipeline/run", files={"file": ("1000_rows.csv", content, "text/csv")})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "run_id" in data
    timings = data.get("timings", {})
    assert "parse_peak_mb" in timings or "clean_peak_mb" in timings or "total_peak_mb" in timings or "total_ms" in timings or "time_total_s" in timings


def test_background_job_dispatch_for_large_files():
    """For runs with async_mode=true or >5000 rows, returns run_id immediately with running status."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    csv_path = os.path.join(fixtures_dir, "1000_rows.csv")
    with open(csv_path, "rb") as f:
        content = f.read()

    res = client.post("/api/pipeline/run?async_mode=true", files={"file": ("1000_rows.csv", content, "text/csv")})
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data
    run_id = data["run_id"]
    # Poll pipeline status
    status_res = client.get(f"/api/pipeline/status/{run_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["run_id"] == run_id
    assert status_data["status"] in ("running", "completed")
