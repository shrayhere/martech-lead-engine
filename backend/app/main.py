from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import ingestion

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
app.include_router(ingestion.router, prefix="/api")

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
