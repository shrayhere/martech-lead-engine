import os
import pytest
from app.database import get_db, Base, engine, SessionLocal
from app.models.schemas import RawLead, CleanLead, PipelineRun

def test_database_persistence_across_sessions():
    """Verify that records committed to the database persist across new DB sessions."""
    Base.metadata.create_all(bind=engine)
    db1 = SessionLocal()
    lead = RawLead(
        upload_batch_id="test_batch_1",
        first_name="Persistent",
        last_name="User",
        email="persist@test.com",
        company="Persistent Co",
        job_title="CTO",
        state="CA",
        industry="Tech",
        company_size=50,
        engagement_score=80.0,
        last_activity_date="2026-11-01"
    )
    db1.add(lead)
    db1.commit()
    lead_id = lead.id
    db1.close()

    # Reopen brand new database session
    db2 = SessionLocal()
    fetched = db2.query(RawLead).filter(RawLead.id == lead_id).first()
    assert fetched is not None
    assert fetched.email == "persist@test.com"
    assert fetched.company == "Persistent Co"
    db2.close()


def test_alembic_migration_configured():
    """Verify Alembic configuration file and migration scripts exist."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    ini_path = os.path.join(base_dir, "alembic.ini")
    versions_path = os.path.join(base_dir, "alembic", "versions")

    assert os.path.exists(ini_path), "alembic.ini must exist"
    assert os.path.isdir(versions_path), "alembic/versions directory must exist"
    migration_files = [f for f in os.listdir(versions_path) if f.endswith(".py")]
    assert len(migration_files) > 0, "At least one Alembic migration must exist"
