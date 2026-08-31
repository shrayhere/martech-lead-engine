import pandas as pd
import io
import uuid
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.schemas import RawLead

# Smart Header Alias Map for Real-World CSV Ingestion
COLUMN_ALIASES = {
    "first_name": ["first_name", "fname", "first name", "given name", "forename", "first"],
    "last_name": ["last_name", "lname", "last name", "surname", "family name", "last"],
    "email": ["email", "email_address", "email address", "e-mail", "mail", "contact_email", "primary_email"],
    "company": ["company", "company_name", "company name", "organization", "org", "account", "business", "employer"],
    "job_title": ["job_title", "job title", "title", "role", "position", "designation", "occupation"],
    "phone": ["phone", "phone_number", "phone number", "mobile", "telephone", "cell", "contact_number"],
    "state": ["state", "state_code", "state/province", "province", "region", "location", "address_state"],
    "industry": ["industry", "vertical", "segment", "sector", "business_type", "domain"],
    "company_size": ["company_size", "company size", "size", "employees", "employee_count", "headcount", "num_employees"],
    "engagement_score": ["engagement_score", "engagement score", "engagement", "score", "activity_score", "lead_score", "rating"],
    "last_activity_date": ["last_activity_date", "last activity date", "activity_date", "date", "last_seen", "updated_at", "created_at", "timestamp"]
}

def map_column_headers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, list]:
    """
    Intelligently maps arbitrary CSV column headers to canonical schema names.
    Supports full name splitting and records which fields were mapped vs defaulted.
    """
    mapped_df = pd.DataFrame()
    detected_headers = {str(c).strip().lower(): c for c in df.columns}
    mapped_fields = {}
    defaulted_fields = []

    # Check for combined 'name' or 'full_name' column if first_name / last_name not explicitly present
    name_col = None
    for alias in ["name", "full_name", "full name", "lead_name"]:
        if alias in detected_headers:
            name_col = detected_headers[alias]
            break

    # Map each target schema field using aliases
    for field, aliases in COLUMN_ALIASES.items():
        found_col = None
        for alias in aliases:
            if alias in detected_headers:
                found_col = detected_headers[alias]
                break

        if found_col is not None:
            mapped_df[field] = df[found_col]
            mapped_fields[field] = str(found_col)
        else:
            mapped_df[field] = None
            defaulted_fields.append(field)

    # Handle Full Name splitting if first_name / last_name were missing
    if name_col is not None and (mapped_df["first_name"].isnull().all() or mapped_df["last_name"].isnull().all()):
        first_names = []
        last_names = []
        for val in df[name_col]:
            if pd.notnull(val) and str(val).strip():
                parts = str(val).strip().split(maxsplit=1)
                first_names.append(parts[0])
                last_names.append(parts[1] if len(parts) > 1 else "")
            else:
                first_names.append(None)
                last_names.append(None)
        
        if mapped_df["first_name"].isnull().all():
            mapped_df["first_name"] = first_names
            mapped_fields["first_name"] = f"{name_col} (Split)"
            if "first_name" in defaulted_fields: defaulted_fields.remove("first_name")
        if mapped_df["last_name"].isnull().all():
            mapped_df["last_name"] = last_names
            mapped_fields["last_name"] = f"{name_col} (Split)"
            if "last_name" in defaulted_fields: defaulted_fields.remove("last_name")

    return mapped_df, mapped_fields, defaulted_fields

def process_csv_upload(file_content: bytes, filename: str, db: Session) -> dict:
    """
    Parses any arbitrary CSV file, flexibly maps column headers to schema fields,
    applies intelligent real-time fallbacks for missing columns, and stores in raw_leads.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_content))
    except Exception as e:
        raise ValueError(f"Invalid CSV file format: {str(e)}")

    if df.empty:
        raise ValueError("Uploaded CSV file is completely empty.")

    mapped_df, mapped_fields, defaulted_fields = map_column_headers(df)

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
