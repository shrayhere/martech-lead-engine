import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Automatically load .env file if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
                    if _k not in os.environ:
                        os.environ[_k] = _v
    except Exception as _e:
        logging.getLogger(__name__).warning("Failed to parse .env file: %s", _e)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, ensure_sqlite_columns
from app.routes import ingestion, cleaning, scoring, assignment, pipeline, band_leads
from app.routes import quality, review, classification, hubspot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan: start/stop APScheduler for background HubSpot sync
# ---------------------------------------------------------------------------

_scheduler = None


def _scheduled_hubspot_import():
    """Called by APScheduler every hour to pull new workflows from HubSpot."""
    if not os.getenv("HUBSPOT_ACCESS_TOKEN"):
        return
    from app.database import SessionLocal
    from app.services.hubspot_import import import_workflows
    db = SessionLocal()
    try:
        result = import_workflows(db, triggered_by="scheduled")
        logger.info(
            "Scheduled HubSpot import: %d workflows found, %d mapped, %d rules",
            result.get("workflows_found", 0),
            result.get("workflows_mapped", 0),
            result.get("rules_created", 0),
        )
    except Exception as e:
        logger.error("Scheduled HubSpot import failed: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    # Create / migrate database tables
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns(engine)

    # Start background scheduler
    sync_interval_hours = int(os.getenv("HUBSPOT_SYNC_INTERVAL_HOURS", "1"))
    bg_task = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(
            _scheduled_hubspot_import,
            "interval",
            hours=sync_interval_hours,
            id="hubspot_import",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("APScheduler started: HubSpot sync every %d hour(s)", sync_interval_hours)
    except Exception as e:
        logger.info("APScheduler not available, using asyncio background worker: %s", e)
        import asyncio
        async def _async_sync_worker():
            while True:
                try:
                    await asyncio.sleep(sync_interval_hours * 3600)
                    _scheduled_hubspot_import()
                except asyncio.CancelledError:
                    break
                except Exception as err:
                    logger.error("Async HubSpot background sync error: %s", err)
        bg_task = asyncio.create_task(_async_sync_worker())

    yield  # app runs

    if _scheduler and getattr(_scheduler, "running", False):
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    if bg_task:
        bg_task.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MarTech Data Quality & Lead Scoring Engine API",
    description=(
        "Backend API for B2B lead ingestion, deduplication, scoring, "
        "HubSpot workflow import, and sales rep assignment."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
_default_origins = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.getenv("CORS_ORIGINS", _default_origins).split(",")
        if o.strip()
    ],
    allow_origin_regex=os.getenv(
        "CORS_ORIGIN_REGEX",
        r"https://martech-lead-engine(-[a-z0-9-]+)?\.vercel\.app",
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(pipeline.router, prefix="/api")
app.include_router(band_leads.router, prefix="/api")
app.include_router(ingestion.router, prefix="/api")
app.include_router(cleaning.router, prefix="/api")
app.include_router(scoring.router, prefix="/api")
app.include_router(assignment.router, prefix="/api")
app.include_router(quality.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(classification.router, prefix="/api")
app.include_router(hubspot.router, prefix="/api")


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "MarTech Lead Engine API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
def health_check():
    """Health-check endpoint used by Render and load balancers."""
    from app.database import SessionLocal
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "scheduler": "running" if (_scheduler and _scheduler.running) else "stopped",
    }


@app.get("/api/report-pdf")
def download_architecture_report():
    from fastapi.responses import FileResponse
    report_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "MarTech_Lead_Engine_Architecture_And_QA_Report.pdf")
    )
    if not os.path.exists(report_path):
        report_path = os.path.abspath("MarTech_Lead_Engine_Architecture_And_QA_Report.pdf")
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename="MarTech_Lead_Engine_Architecture_And_QA_Report.pdf",
    )
