import re
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
from app.services.cleaning_service import (
    US_STATES_MAP,
    JUNK_PLACEHOLDERS,
    normalize_state,
    normalize_phone,
    normalize_company,
    is_junk_lead
)

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@([a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}$")
DISALLOWED_EMAIL_DOMAINS = {"asdf.com", "test.com", "example.com", "fake.com", "sample.com", "bot.com", "none.com", "null.com"}

INDUSTRY_MAP = {
    "saas": "SaaS",
    "software": "Software",
    "software development": "Software",
    "tech": "Enterprise Technology",
    "technology": "Enterprise Technology",
    "enterprise tech": "Enterprise Technology",
    "enterprise technology": "Enterprise Technology",
    "fintech": "Fintech",
    "finance": "Fintech",
    "financial services": "Fintech",
    "banking": "Fintech",
    "healthcare": "Healthcare IT",
    "healthcare it": "Healthcare IT",
    "health": "Healthcare IT",
    "hospital": "Healthcare IT",
    "biotech": "Healthcare IT",
    "cybersecurity": "Cybersecurity",
    "security": "Cybersecurity",
    "infosec": "Cybersecurity",
    "cloud": "Cloud Computing",
    "cloud computing": "Cloud Computing",
    "marketing": "Digital Marketing",
    "ecommerce": "E-Commerce",
    "e-commerce": "E-Commerce",
    "retail": "Retail",
    "manufacturing": "Manufacturing",
    "consulting": "Consulting & Services"
}

def parse_company_size_value(val: Any) -> Optional[int]:
    """
    Parses messy company size strings like '50-200', '1k+', '~500', '<50', '10,000' into numeric integer.
    """
    if pd.isnull(val) or val is None:
        return 50

    s = str(val).strip().lower().replace(",", "").replace("employees", "").replace("people", "")
    if not s or s in {"n/a", "none", "unknown", "null", "nan"}:
        return 50

    # Range like '50-200'
    m_range = re.match(r"^(\d+)\s*[-–—to]\s*(\d+)$", s)
    if m_range:
        low, high = int(m_range.group(1)), int(m_range.group(2))
        return int((low + high) / 2)

    # Patterns like '1k+', '5k'
    m_k = re.match(r"^[~<>]?\s*(\d+(?:\.\d+)?)\s*k\+?$", s)
    if m_k:
        return int(float(m_k.group(1)) * 1000)

    # '~500', '500+', '>500'
    m_approx = re.match(r"^[~<>+]?\s*(\d+)\s*\+?$", s)
    if m_approx:
        return int(m_approx.group(1))

    # Strip any other digits
    digits = re.sub(r"[^\d]", "", s)
    if digits:
        try:
            return int(digits)
        except Exception:
            pass
    return 50

def parse_iso_date(val: Any) -> Optional[str]:
    """
    Standardizes arbitrary date formats into ISO-8601 YYYY-MM-DD.
    """
    if pd.isnull(val) or val is None:
        return None

    s = str(val).strip()
    if not s or s.lower() in {"n/a", "none", "unknown", "null", "nan"}:
        return None

    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]

    # Try common date formats
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(s[:10], fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Use pandas to_datetime fallback
    try:
        dt_val = pd.to_datetime(s, errors="coerce")
        if pd.notnull(dt_val):
            return dt_val.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None

def standardize_industry(val: Any) -> str:
    """Standardizes industry name against known B2B domains."""
    if pd.isnull(val) or val is None:
        return "General Business"

    s = str(val).strip()
    if not s or s.lower() in {"n/a", "none", "unknown", "null", "nan"}:
        return "General Business"

    s_lower = s.lower()
    for key, canonical in INDUSTRY_MAP.items():
        if key in s_lower or s_lower in key:
            return canonical

    return s.title()

def clean_and_normalize_records(
    df: pd.DataFrame,
    run_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """
    Cleans, normalizes, and validates each lead:
    - Trims whitespace & standardizes casing (Title Case names, lowercase emails)
    - Validates emails (syntax & domain sanity)
    - Normalizes phone numbers to E.164
    - Normalizes US states to 2-letter postal code
    - Standardizes dates to ISO-8601
    - Standardizes company sizes to numeric values
    - Standardizes industry categories
    - Drops rows missing both email and phone (records in rejected_rows)
    - Detects junk placeholder records
    - Records fine-grained changes in cleaning_logs

    Returns:
      (valid_leads, rejected_rows, cleaning_logs, stats)
    """
    valid_leads: List[Dict[str, Any]] = []
    rejected_rows: List[Dict[str, Any]] = []
    cleaning_logs: List[Dict[str, Any]] = []

    fields_fixed_count = 0
    junk_count = 0
    today_str = datetime.now().strftime("%Y-%m-%d")

    for idx, row in df.iterrows():
        row_num = idx + 1
        raw_dict = row.to_dict()

        # 1. Names
        raw_fn = str(row.get("first_name", "") or "").strip()
        raw_ln = str(row.get("last_name", "") or "").strip()

        fn = raw_fn.title() if raw_fn and raw_fn.lower() not in {"none", "nan", "null"} else None
        ln = raw_ln.title() if raw_ln and raw_ln.lower() not in {"none", "nan", "null"} else None

        if raw_fn and fn and raw_fn != fn:
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "first_name",
                "old_value": raw_fn, "new_value": fn, "reason": "Title-cased name formatting"
            })
            fields_fixed_count += 1

        if raw_ln and ln and raw_ln != ln:
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "last_name",
                "old_value": raw_ln, "new_value": ln, "reason": "Title-cased name formatting"
            })
            fields_fixed_count += 1

        # 2. Email Validation & Lowercasing
        raw_email = str(row.get("email", "") or "").strip()
        email = None
        if raw_email and raw_email.lower() not in {"none", "nan", "null", "n/a", "noemail"}:
            clean_em = raw_email.lower()
            # Validate syntax & domain
            if EMAIL_REGEX.match(clean_em):
                domain = clean_em.split("@")[-1]
                if domain not in DISALLOWED_EMAIL_DOMAINS and "." in domain:
                    email = clean_em
                    if raw_email != email:
                        cleaning_logs.append({
                            "run_id": run_id, "row_index": row_num, "field_name": "email",
                            "old_value": raw_email, "new_value": email, "reason": "Lowercased email formatting"
                        })
                        fields_fixed_count += 1

        # 3. Phone Normalization (E.164)
        raw_phone = str(row.get("phone", "") or "").strip()
        phone = normalize_phone(raw_phone)
        if raw_phone and phone and raw_phone != phone:
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "phone",
                "old_value": raw_phone, "new_value": phone, "reason": "Normalized to E.164 phone format"
            })
            fields_fixed_count += 1

        # CRITICAL FILTER: Drop rows missing BOTH valid email and phone
        if not email and not phone:
            raw_c = row.get("company")
            comp_str = str(raw_c).strip() if (pd.notnull(raw_c) and str(raw_c).lower() not in {"nan", "none", "null"}) else None
            rejected_rows.append({
                "row_number": row_num,
                "first_name": fn,
                "last_name": ln,
                "company": comp_str,
                "reason": "Missing both valid email and phone contact details"
            })
            continue

        # 4. Company Name Normalization
        raw_comp = str(row.get("company", "") or "").strip()
        comp = normalize_company(raw_comp) if raw_comp and raw_comp.lower() not in {"none", "nan", "null"} else None
        if raw_comp and comp and raw_comp != comp:
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "company",
                "old_value": raw_comp, "new_value": comp, "reason": "Standardized company casing"
            })
            fields_fixed_count += 1

        # 5. State Normalization
        raw_state = str(row.get("state", "") or "").strip()
        state = normalize_state(raw_state)
        if raw_state and state and raw_state != state and state != "UNKNOWN":
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "state",
                "old_value": raw_state, "new_value": state, "reason": "Standardized to 2-letter US State postal code"
            })
            fields_fixed_count += 1

        # 6. Dates (Last Activity & Created)
        raw_date = row.get("last_activity_date")
        act_date = parse_iso_date(raw_date) or today_str
        if raw_date and act_date and str(raw_date).strip() != act_date:
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "last_activity_date",
                "old_value": str(raw_date), "new_value": act_date, "reason": "Parsed into ISO-8601 date"
            })
            fields_fixed_count += 1

        raw_created = row.get("created_date")
        created_dt = parse_iso_date(raw_created) or today_str

        # 7. Company Size
        raw_cs = row.get("company_size")
        comp_size = parse_company_size_value(raw_cs)
        if raw_cs and str(raw_cs).strip() != str(comp_size):
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "company_size",
                "old_value": str(raw_cs), "new_value": str(comp_size), "reason": "Parsed numeric employee band"
            })
            fields_fixed_count += 1

        # 8. Industry
        raw_ind = row.get("industry")
        industry = standardize_industry(raw_ind)
        if raw_ind and str(raw_ind).strip() != industry:
            cleaning_logs.append({
                "run_id": run_id, "row_index": row_num, "field_name": "industry",
                "old_value": str(raw_ind), "new_value": industry, "reason": "Standardized industry domain"
            })
            fields_fixed_count += 1

        # 9. Engagement Score
        raw_eng = row.get("engagement_score")
        if pd.notnull(raw_eng) and str(raw_eng).strip() not in {"", "None", "nan"}:
            try:
                eng_score = float(str(raw_eng).replace("%", "").strip())
            except Exception:
                eng_score = None
        else:
            eng_score = None

        # 10. Junk Placeholder row detection
        is_junk, junk_reason = is_junk_lead(fn, ln, email, comp, phone)
        if is_junk:
            junk_count += 1

        valid_leads.append({
            "run_id": run_id,
            "row_index": row_num,
            "first_name": fn,
            "last_name": ln,
            "email": email,
            "phone": phone,
            "company": comp,
            "job_title": str(row.get("job_title", "") or "").strip() or None,
            "state": state,
            "city": str(row.get("city", "") or "").strip() or None,
            "country": str(row.get("country", "") or "").strip() or "USA",
            "industry": industry,
            "company_size": comp_size,
            "engagement_score": eng_score,
            "last_activity_date": act_date,
            "lead_source": str(row.get("lead_source", "") or "").strip() or "Direct Upload",
            "created_date": created_dt,
            "extra_fields": row.get("extra_fields"),
            "is_junk": is_junk,
            "junk_reason": junk_reason
        })

    stats = {
        "total_input_rows": len(df),
        "valid_clean_rows": len(valid_leads),
        "rejected_rows_count": len(rejected_rows),
        "fields_fixed_count": fields_fixed_count,
        "junk_rows_count": junk_count
    }

    return valid_leads, rejected_rows, cleaning_logs, stats
