from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./martech.db")
# Render/Heroku-style URLs use the "postgres://" scheme, which SQLAlchemy 2 does not accept.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# For SQLite, connect_args={"check_same_thread": False} is required
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

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
            ]
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

