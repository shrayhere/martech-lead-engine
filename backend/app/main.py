from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, ensure_sqlite_columns
from app.routes import ingestion, cleaning, scoring, assignment, pipeline, band_leads
from app.routes import quality, review, classification, hubspot

# Create database tables automatically
Base.metadata.create_all(bind=engine)
ensure_sqlite_columns(engine)

app = FastAPI(
    title="MarTech Data Quality & Lead Scoring Engine API",
    description="Backend API for B2B lead ingestion, deduplication, scoring, and sales rep assignment.",
    version="1.0.0"
)

# CORS: the Vercel frontend normally proxies /api through vercel.json (same origin), but direct calls
# from the deployed site and local dev are allowed explicitly. Configure with environment variables:
#   CORS_ORIGINS="https://my-app.vercel.app,https://www.example.com"
#   CORS_ORIGIN_REGEX="https://martech-lead-engine(-[a-z0-9-]+)?\.vercel\.app"  (production + preview deploys)
import os  # noqa: E402

_default_origins = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()],
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX", r"https://martech-lead-engine(-[a-z0-9-]+)?\.vercel\.app"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
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
        "docs": "/docs"
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/report-pdf")
def download_architecture_report():
    import os
    from fastapi.responses import FileResponse
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"))
    if not os.path.exists(report_path):
        # Fallback to current working directory
        report_path = os.path.abspath("MarTech_Lead_Engine_Architecture_And_QA_Report.pdf")
    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename="MarTech_Lead_Engine_Architecture_And_QA_Report.pdf"
    )
