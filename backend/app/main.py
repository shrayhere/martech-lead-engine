from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import ingestion, cleaning, scoring, assignment, pipeline, band_leads

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MarTech Data Quality & Lead Scoring Engine API",
    description="Backend API for B2B lead ingestion, deduplication, scoring, and sales rep assignment.",
    version="1.0.0"
)

# CORS configuration to allow local Vite frontend and production hosts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
