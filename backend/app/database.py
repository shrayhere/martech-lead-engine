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
    """Ensures newly added columns exist in existing SQLite databases."""
    if not str(target_engine.url).startswith("sqlite"):
        return
    from sqlalchemy import text
    with target_engine.connect() as conn:
        needed_cols = {
            "clean_leads": [
                ("run_id", "VARCHAR"),
                ("city", "VARCHAR"),
                ("country", "VARCHAR"),
                ("lead_source", "VARCHAR"),
                ("created_date", "VARCHAR"),
                ("extra_fields", "TEXT")
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
        for tbl, cols in needed_cols.items():
            try:
                res = conn.execute(text(f"PRAGMA table_info({tbl})")).fetchall()
                existing = [r[1] for r in res]
                if not existing:
                    continue
                for col_name, col_type in cols:
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_type}"))
                conn.commit()
            except Exception:
                pass

