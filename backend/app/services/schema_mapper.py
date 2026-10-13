import re
import json
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from rapidfuzz import fuzz
from app.services.cleaning_service import US_STATES_MAP

CANONICAL_FIELDS = [
    "first_name",
    "last_name",
    "email",
    "phone",
    "company",
    "job_title",
    "industry",
    "company_size",
    "state",
    "city",
    "country",
    "lead_source",
    "last_activity_date",
    "engagement_score",
    "created_date"
]

CANONICAL_ALIASES = {
    "first_name": ["first_name", "fname", "first name", "given name", "forename", "first", "f_name", "first_nm"],
    "last_name": ["last_name", "lname", "last name", "surname", "family name", "last", "l_name", "last_nm"],
    "full_name": ["name", "full_name", "full name", "lead_name", "contact_name", "contact", "prospect_name", "person_name", "client_name"],
    "email": ["email", "email_address", "email address", "e-mail", "mail", "contact_email", "primary_email", "work_email", "business_email"],
    "phone": ["phone", "phone_number", "phone number", "mobile", "telephone", "cell", "contact_number", "tel", "cellphone", "direct_phone", "work_phone"],
    "company": ["company", "company_name", "company name", "organization", "org", "account", "business", "employer", "firm", "corp", "agency", "client_company"],
    "job_title": ["job_title", "job title", "title", "role", "position", "designation", "occupation", "job", "headline"],
    "industry": ["industry", "vertical", "segment", "sector", "business_type", "domain", "category", "market"],
    "company_size": ["company_size", "company size", "size", "employees", "employee_count", "headcount", "num_employees", "team_size", "staff", "head_count"],
    "state": ["state", "state_code", "state/province", "province", "region", "address_state", "location_state"],
    "city": ["city", "town", "municipality", "address_city", "location_city"],
    "country": ["country", "nation", "country_code", "address_country"],
    "lead_source": ["lead_source", "source", "channel", "origin", "campaign", "utm_source", "medium", "acquisition_source"],
    "last_activity_date": ["last_activity_date", "last activity date", "activity_date", "last_seen", "last_touch", "last_contact", "last_interaction", "updated_at"],
    "engagement_score": ["engagement_score", "engagement score", "engagement", "activity_score", "lead_score", "score", "rating", "clicks", "opens", "visits", "points"],
    "created_date": ["created_date", "created date", "created_at", "date_created", "signup_date", "date_added", "added_date", "timestamp", "date"]
}

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$")
PHONE_REGEX = re.compile(r"^\+?[\d\s().-]{7,20}$")
DATE_PATTERN = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$")
COMPANY_SIZE_PATTERN = re.compile(r"^\s*~?\s*\d+\s*(?:-\s*\d+|k\+?|\+)?\s*$", re.IGNORECASE)

KNOWN_INDUSTRIES = {
    "saas", "software", "fintech", "healthcare", "technology", "finance", "retail",
    "manufacturing", "education", "consulting", "cybersecurity", "cloud", "legal"
}

def sniff_content_type(values: List[str]) -> Optional[str]:
    """
    Inspects non-empty sample values from a column to determine if content fits a canonical schema field.
    """
    clean_vals = [str(v).strip() for v in values if pd.notnull(v) and str(v).strip() != "" and str(v).lower() != "nan"]
    if not clean_vals:
        return None

    sample_size = min(len(clean_vals), 30)
    sample = clean_vals[:sample_size]

    # Email sniffing
    email_matches = sum(1 for v in sample if EMAIL_REGEX.match(v))
    if email_matches / sample_size >= 0.5:
        return "email"

    # Phone sniffing
    phone_matches = sum(1 for v in sample if PHONE_REGEX.match(v) and sum(c.isdigit() for c in v) >= 7)
    if phone_matches / sample_size >= 0.5:
        return "phone"

    # State sniffing
    state_matches = sum(1 for v in sample if v.upper() in US_STATES_MAP)
    if state_matches / sample_size >= 0.5:
        return "state"

    # Date sniffing
    date_matches = sum(1 for v in sample if DATE_PATTERN.match(v))
    if date_matches / sample_size >= 0.5:
        return "last_activity_date"

    # Company size sniffing
    cs_matches = sum(1 for v in sample if COMPANY_SIZE_PATTERN.match(v))
    if cs_matches / sample_size >= 0.6:
        return "company_size"

    # Industry sniffing
    ind_matches = sum(1 for v in sample if any(ind in v.lower() for ind in KNOWN_INDUSTRIES))
    if ind_matches / sample_size >= 0.4:
        return "industry"

    return None

def detect_column_mapping(
    df: pd.DataFrame,
    mapping_override: Optional[Dict[str, str]] = None
) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, str], List[str]]:
    """
    3-Tier Schema Abstraction:
      1. Exact and Alias matching (Confidence = 1.0)
      2. Fuzzy Header matching via RapidFuzz (Confidence = 0.70 - 0.95)
      3. Content Sniffing on sample values (Confidence = 0.75 - 0.85)

    Returns:
      (canonical_to_csv_map, confidence_map, mapping_tier_map, unmapped_csv_cols)
    """
    mapping_override = mapping_override or {}
    raw_columns = list(df.columns)
    available_cols = set(raw_columns)

    canonical_map: Dict[str, str] = {}
    confidence_map: Dict[str, float] = {}
    tier_map: Dict[str, str] = {}

    # Apply manual overrides first if specified
    for canon_field, user_col in mapping_override.items():
        if user_col in available_cols:
            canonical_map[canon_field] = user_col
            confidence_map[canon_field] = 1.0
            tier_map[canon_field] = "Manual Override"
            available_cols.discard(user_col)

    # Helper to check canonical assignment
    all_targets = list(CANONICAL_ALIASES.keys())  # includes full_name

    # TIER 1: Exact and Alias matching
    for target in all_targets:
        if target in canonical_map:
            continue
        aliases = CANONICAL_ALIASES[target]
        for col in list(available_cols):
            clean_col = col.strip().lower().replace("_", " ").replace("-", " ")
            for alias in aliases:
                clean_alias = alias.lower().replace("_", " ").replace("-", " ")
                if clean_col == clean_alias:
                    canonical_map[target] = col
                    confidence_map[target] = 1.0
                    tier_map[target] = "Exact Alias Match"
                    available_cols.discard(col)
                    break
            if target in canonical_map:
                break

    # TIER 2: Fuzzy Header Matching with RapidFuzz
    for target in all_targets:
        if target in canonical_map:
            continue
        aliases = CANONICAL_ALIASES[target]
        best_score = 0
        best_col = None

        for col in list(available_cols):
            col_normalized = col.strip().lower()
            for alias in aliases:
                # token_sort_ratio handles word orders like "name lead" vs "lead name"
                score = fuzz.token_sort_ratio(col_normalized, alias.lower())
                if score > best_score:
                    best_score = score
                    best_col = col

        if best_col and best_score >= 78.0:
            canonical_map[target] = best_col
            confidence_map[target] = round(best_score / 100.0, 2)
            tier_map[target] = f"Fuzzy Match ({best_score:.0f}%)"
            available_cols.discard(best_col)

    # TIER 3: Content Sniffing on remaining unmapped columns
    if available_cols:
        sample_dict = {c: df[c].dropna().head(40).tolist() for c in available_cols}
        for col, samples in sample_dict.items():
            if not samples:
                continue
            sniffed_field = sniff_content_type(samples)
            if sniffed_field and sniffed_field not in canonical_map:
                canonical_map[sniffed_field] = col
                confidence_map[sniffed_field] = 0.80
                tier_map[sniffed_field] = "Content Sniffing"
                available_cols.discard(col)

    unmapped_csv_cols = [c for c in raw_columns if c in available_cols]
    return canonical_map, confidence_map, tier_map, unmapped_csv_cols

def apply_schema_mapping(
    df: pd.DataFrame,
    mapping_override: Optional[Dict[str, str]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Applies column mappings to construct canonical DataFrame:
    - Extracts canonical columns.
    - Performs full name splitting into first_name and last_name if needed.
    - Preserves ALL unmapped columns into a JSON-serialized 'extra_fields' column.
    """
    canonical_map, confidence_map, tier_map, unmapped_cols = detect_column_mapping(
        df, mapping_override
    )

    n_rows = len(df)
    mapped_data = {}

    for field in CANONICAL_FIELDS:
        csv_col = canonical_map.get(field)
        if csv_col and csv_col in df.columns:
            mapped_data[field] = df[csv_col].values
        else:
            mapped_data[field] = [None] * n_rows

    result_df = pd.DataFrame(mapped_data, index=df.index)

    # Handle Full Name Splitting if first_name or last_name is missing
    full_name_col = canonical_map.get("full_name")
    split_count = 0
    if full_name_col and full_name_col in df.columns:
        fn_series = result_df["first_name"]
        ln_series = result_df["last_name"]
        needs_fn = fn_series.isnull().all() or (fn_series.astype(str).str.strip().isin(["", "None", "nan"]).sum() > (n_rows * 0.7))
        needs_ln = ln_series.isnull().all() or (ln_series.astype(str).str.strip().isin(["", "None", "nan"]).sum() > (n_rows * 0.7))

        if needs_fn or needs_ln:
            first_names = []
            last_names = []
            for val in df[full_name_col]:
                if pd.notnull(val) and str(val).strip() and str(val).strip().lower() != "nan":
                    parts = str(val).strip().split(maxsplit=1)
                    first_names.append(parts[0])
                    last_names.append(parts[1] if len(parts) > 1 else "")
                    split_count += 1
                else:
                    first_names.append(None)
                    last_names.append(None)

            if needs_fn:
                result_df["first_name"] = first_names
                confidence_map["first_name"] = confidence_map.get("full_name", 0.95)
                tier_map["first_name"] = f"Split from '{full_name_col}'"
                canonical_map["first_name"] = f"{full_name_col} (Split)"

            if needs_ln:
                result_df["last_name"] = last_names
                confidence_map["last_name"] = confidence_map.get("full_name", 0.95)
                tier_map["last_name"] = f"Split from '{full_name_col}'"
                canonical_map["last_name"] = f"{full_name_col} (Split)"

    # Store all unmapped columns into extra_fields JSON column (NEVER DROP DATA)
    if unmapped_cols:
        extra_df = df[unmapped_cols]
        extra_records = extra_df.to_dict(orient="records")
        result_df["extra_fields"] = [
            json.dumps({k: v for k, v in row.items() if pd.notnull(v) and str(v).strip() != ""})
            for row in extra_records
        ]
    else:
        result_df["extra_fields"] = [None] * n_rows

    mapping_summary = {
        "canonical_to_source": canonical_map,
        "confidence_scores": confidence_map,
        "detection_tiers": tier_map,
        "unmapped_columns": unmapped_cols,
        "full_names_split": split_count
    }

    return result_df, mapping_summary
