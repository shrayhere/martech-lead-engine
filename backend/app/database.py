from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./martech.db")
# Render/Heroku-style URLs use the "postgres://" scheme, which SQLAlchemy 2 does not accept.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300
    )
else:
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_sqlite_columns(target_engine):
    """Adds newly introduced columns to tables that already exist (create_all never alters tables).
    Works on SQLite and Postgres."""
    from sqlalchemy import text, inspect
    is_sqlite = str(target_engine.url).startswith("sqlite")
    float_type = "REAL" if is_sqlite else "DOUBLE PRECISION"
    with target_engine.connect() as conn:
        needed_cols = {
            "clean_leads": [
                ("run_id", "VARCHAR"),
                ("city", "VARCHAR"),
                ("country", "VARCHAR"),
                ("lead_source", "VARCHAR"),
                ("created_date", "VARCHAR"),
                ("extra_fields", "TEXT"),
                ("source_row", "INTEGER"),
                ("persona", "VARCHAR"),
                ("buying_role", "VARCHAR"),
                ("interest", "VARCHAR"),
                ("classification_confidence", float_type),
                ("classification_engine", "VARCHAR"),
                ("recommended_action", "VARCHAR"),
                ("hubspot_synced_at", "VARCHAR"),
            ],
            "merged_leads_log": [
                ("run_id", "VARCHAR"),
                ("winner_raw_lead_id", "INTEGER"),
                ("id_type", "VARCHAR")
            ],
            "cleaning_log": [
                ("run_id", "VARCHAR")
            ],
            "assignment_log": [
                ("run_id", "VARCHAR")
            ],
            "hubspot_workflows": [
                ("mapped", "BOOLEAN"),
                ("not_mapped_reason", "VARCHAR"),
                ("synced_at", "TIMESTAMP"),
            ],
            "hubspot_scoring_rules": [
                ("active", "BOOLEAN"),
            ],
            "hubspot_sync_log": [
                ("triggered_by", "VARCHAR"),
            ],
        }
        inspector = inspect(conn)
        for tbl, cols in needed_cols.items():
            try:
                if not inspector.has_table(tbl):
                    continue
                existing = [c["name"] for c in inspector.get_columns(tbl)]
                for col_name, col_type in cols:
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass


def run_migrations():
    """Applies Alembic migrations up to head automatically at startup."""
    if os.getenv("TESTING") == "1":
        return
    try:
        from alembic.config import Config
        from alembic import command
        alembic_ini = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        if os.path.exists(alembic_ini):
            cfg = Config(alembic_ini)
            command.upgrade(cfg, "head")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Alembic migration notice: %s", e)

