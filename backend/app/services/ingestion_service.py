import pandas as pd
import uuid
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.schemas import RawLead
from app.services.smart_parser import parse_csv_file
from app.services.schema_mapper import apply_schema_mapping

# Fields the staged flow stores in raw_leads
STAGED_FIELDS = ["first_name", "last_name", "email", "company", "job_title", "phone", "state", "industry",
                 "company_size", "engagement_score", "last_activity_date"]


def process_csv_upload(file_content: bytes, filename: str, db: Session) -> dict:
    """
    Parses any CSV, maps its headers to schema fields and stores the rows in raw_leads.
    Uses the same parser and header mapper as Smart Upload, so the staged flow accepts the same files:
    comma / semicolon / tab / pipe delimiters, UTF-8 (with or without BOM) or Latin-1, and header names
    such as "E-mail Address", "Tel", "Org" or a single "Full Name" column (split into first/last).
    """
    try:
        df, _ = parse_csv_file(file_content, filename)
    except ValueError as e:
        raise ValueError(f"Invalid CSV file format: {e}")

    if df.empty:
        raise ValueError("Uploaded CSV file is completely empty.")

    mapped_df, mapping_summary = apply_schema_mapping(df, None)
    source_of = mapping_summary.get("canonical_to_source", {})
    mapped_fields = {f: str(source_of[f]) for f in STAGED_FIELDS if f in source_of}
    defaulted_fields = [f for f in STAGED_FIELDS if f not in source_of]
    for f in STAGED_FIELDS:
        if f not in mapped_df.columns:
            mapped_df[f] = None

    # Ensure at least 1 core contact/identity column was mapped (email, name, or company)
    has_contact = (
        not mapped_df["email"].isnull().all() or
        not mapped_df["company"].isnull().all() or
        not mapped_df["first_name"].isnull().all()
    )
    if not has_contact:
        raise ValueError(
            f"CSV file must contain at least one identifiable contact column (e.g. Email, Name, or Company). Mapped headers: {list(mapped_fields.values())}"
        )

    batch_id = str(uuid.uuid4())[:8]
    raw_lead_objects = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Convert pandas NaNs to Python None
    mapped_df = mapped_df.where(pd.notnull(mapped_df), None)

    for idx, row in mapped_df.iterrows():
        # Smart numeric parse for company size
        cs_val = row["company_size"]
        if cs_val is not None:
            digits = re.sub(r"[^\d]", "", str(cs_val))
            company_sz = int(digits) if digits else 50
        else:
            company_sz = 50

        # Smart float parse for engagement score
        eng_val = row["engagement_score"]
        if eng_val is not None:
            try:
                eng_score = float(str(eng_val).replace("%", "").strip())
            except:
                eng_score = 50.0
        else:
            eng_score = 50.0

        # Fallback date
        act_date = str(row["last_activity_date"]).strip() if row["last_activity_date"] else today_str

        raw_lead = RawLead(
            upload_batch_id=batch_id,
            first_name=str(row["first_name"]).strip() if row["first_name"] else None,
            last_name=str(row["last_name"]).strip() if row["last_name"] else None,
            email=str(row["email"]).strip() if row["email"] else None,
            company=str(row["company"]).strip() if row["company"] else None,
            job_title=str(row["job_title"]).strip() if row["job_title"] else None,
            phone=str(row["phone"]).strip() if row["phone"] else None,
            state=str(row["state"]).strip() if row["state"] else "UNKNOWN",
            industry=str(row["industry"]).strip() if row["industry"] else "General Business",
            company_size=company_sz,
            engagement_score=eng_score,
            last_activity_date=act_date
        )
        raw_lead_objects.append(raw_lead)

    db.bulk_save_objects(raw_lead_objects)
    db.commit()

    return {
        "success": True,
        "batch_id": batch_id,
        "filename": filename,
        "records_ingested": len(raw_lead_objects),
        "columns_mapped": mapped_fields,
        "defaulted_fields": defaulted_fields
    }
