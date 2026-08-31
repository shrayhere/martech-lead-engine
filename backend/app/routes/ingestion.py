from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.ingestion_service import process_csv_upload
from app.services.sample_generator import generate_sample_leads_csv
from app.models.schemas import RawLead

router = APIRouter(prefix="/leads", tags=["Ingestion"])

@router.post("/upload")
async def upload_leads_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Accepts CSV file upload, parses records, validates columns, and stores in raw_leads table.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    try:
        content = await file.read()
        result = process_csv_upload(content, file.filename, db)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process CSV file: {str(e)}")

@router.get("/sample-csv")
def download_sample_csv():
    """
    Generates and returns downloadable synthetic sample CSV of 200 realistic B2B leads.
    """
    csv_data = generate_sample_leads_csv(200)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=martech_sample_leads_200.csv"}
    )

@router.get("/raw")
def get_raw_leads(limit: int = 250, db: Session = Depends(get_db)):
    """
    Retrieves raw leads stored in the database.
    """
    leads = db.query(RawLead).order_by(RawLead.id.desc()).limit(limit).all()
    return {
        "count": len(leads),
        "leads": leads
    }
