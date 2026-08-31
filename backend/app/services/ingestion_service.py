import pandas as pd
import io
import uuid
from sqlalchemy.orm import Session
from app.models.schemas import RawLead

REQUIRED_COLUMNS = [
    "first_name", "last_name", "email", "company", "job_title", 
    "phone", "state", "industry", "company_size", "engagement_score", "last_activity_date"
]

def process_csv_upload(file_content: bytes, filename: str, db: Session) -> dict:
    """
    Parses CSV content with pandas, validates required columns,
    and inserts raw records into the `raw_leads` table.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_content))
    except Exception as e:
        raise ValueError(f"Invalid CSV file format: {str(e)}")

    # Standardize column headers (lowercase, strip whitespace)
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required CSV columns: {', '.join(missing_cols)}")

    batch_id = str(uuid.uuid4())[:8]
    raw_lead_objects = []

    # Clean missing values to None for SQL storage
    df = df.where(pd.notnull(df), None)

    for idx, row in df.iterrows():
        try:
            company_sz = int(row["company_size"]) if row["company_size"] is not None and str(row["company_size"]).replace('.','',1).isdigit() else None
        except:
            company_sz = None

        try:
            eng_score = float(row["engagement_score"]) if row["engagement_score"] is not None and str(row["engagement_score"]).replace('.','',1).isdigit() else 0.0
        except:
            eng_score = 0.0

        raw_lead = RawLead(
            upload_batch_id=batch_id,
            first_name=str(row["first_name"]).strip() if row["first_name"] else None,
            last_name=str(row["last_name"]).strip() if row["last_name"] else None,
            email=str(row["email"]).strip() if row["email"] else None,
            company=str(row["company"]).strip() if row["company"] else None,
            job_title=str(row["job_title"]).strip() if row["job_title"] else None,
            phone=str(row["phone"]).strip() if row["phone"] else None,
            state=str(row["state"]).strip() if row["state"] else None,
            industry=str(row["industry"]).strip() if row["industry"] else None,
            company_size=company_sz,
            engagement_score=eng_score,
            last_activity_date=str(row["last_activity_date"]).strip() if row["last_activity_date"] else None
        )
        raw_lead_objects.append(raw_lead)

    db.bulk_save_objects(raw_lead_objects)
    db.commit()

    return {
        "success": True,
        "batch_id": batch_id,
        "filename": filename,
        "records_ingested": len(raw_lead_objects),
        "columns_detected": list(df.columns)
    }
