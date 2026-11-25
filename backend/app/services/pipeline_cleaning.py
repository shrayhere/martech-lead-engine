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
from app.utils.geo_utils import (
    normalize_phone_intl,
    validate_email_intl,
    normalize_state_intl,
    detect_country,
    is_advanced_junk_lead
)

INDUSTRY_MAP = {
    'saas': 'SaaS',
    'software': 'Software',
    'software development': 'Software',
    'tech': 'Enterprise Technology',
    'technology': 'Enterprise Technology',
    'enterprise tech': 'Enterprise Technology',
    'enterprise technology': 'Enterprise Technology',
    'fintech': 'Fintech',
    'finance': 'Fintech',
    'financial services': 'Fintech',
    'banking': 'Fintech',
    'healthcare': 'Healthcare IT',
    'healthcare it': 'Healthcare IT',
    'health': 'Healthcare IT',
    'hospital': 'Healthcare IT',
    'biotech': 'Healthcare IT',
    'cybersecurity': 'Cybersecurity',
    'security': 'Cybersecurity',
    'infosec': 'Cybersecurity',
    'cloud': 'Cloud Computing',
    'cloud computing': 'Cloud Computing',
    'marketing': 'Digital Marketing',
    'ecommerce': 'E-Commerce',
    'e-commerce': 'E-Commerce',
    'retail': 'Retail',
    'manufacturing': 'Manufacturing',
    'consulting': 'Consulting & Services'
}

def parse_company_size_value(val: Any) -> Optional[int]:
    if pd.isnull(val) or val is None:
        return None
    s = str(val).strip().lower().replace(',', '').replace('employees', '').replace('people', '')
    if not s or s in {'n/a', 'none', 'unknown', 'null', 'nan'}:
        return None
    if s.startswith('-'):
        return None
    m_range = re.match(r'^(\d+)\s*[-–—to]\s*(\d+)$', s)
    if m_range:
        low, high = int(m_range.group(1)), int(m_range.group(2))
        avg = int((low + high) / 2)
        return avg if avg > 0 else None
    m_k = re.match(r'^[~<>]?\s*(\d+(?:\.\d+)?)\s*k\+?$', s)
    if m_k:
        res = int(float(m_k.group(1)) * 1000)
        return res if res > 0 else None
    m_approx = re.match(r'^[~<>+]?\s*(\d+)\s*\+?$', s)
    if m_approx:
        res = int(m_approx.group(1))
        return res if res > 0 else None
    digits = re.sub(r'[^\d]', '', s)
    if digits:
        try:
            res = int(digits)
            return res if res > 0 else None
        except Exception:
            pass
    return None

def parse_iso_date(val: Any) -> Optional[str]:
    if pd.isnull(val) or val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in {'n/a', 'none', 'unknown', 'null', 'nan'}:
        return None
    dt = None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', '%m-%d-%Y', '%d.%m.%Y', '%Y.%m.%d'):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            pass
    if dt is None:
        try:
            dt_val = pd.to_datetime(s, errors='coerce')
            if pd.notnull(dt_val):
                dt = dt_val.to_pydatetime()
        except Exception:
            pass
    if dt is None or dt > datetime.now():
        return None
    return dt.strftime('%Y-%m-%d')

def standardize_industry(val: Any) -> str:
    if pd.isnull(val) or val is None:
        return 'General Business'
    s = str(val).strip()
    if not s or s.lower() in {'n/a', 'none', 'unknown', 'null', 'nan'}:
        return 'General Business'
    s_lower = s.lower()
    for key, canonical in INDUSTRY_MAP.items():
        if key in s_lower or s_lower in key:
            return canonical
    return s.title()

def clean_and_normalize_records(
    df: pd.DataFrame,
    run_id: str,
    default_country: str = 'India'
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    valid_leads: List[Dict[str, Any]] = []
    rejected_rows: List[Dict[str, Any]] = []
    cleaning_logs: List[Dict[str, Any]] = []

    fields_fixed_count = 0
    junk_count = 0
    today_str = datetime.now().strftime('%Y-%m-%d')

    for idx, row in df.iterrows():
        row_num = idx + 1

        raw_fn = str(row.get('first_name', '') or '').strip()
        raw_ln = str(row.get('last_name', '') or '').strip()

        fn = raw_fn.title() if raw_fn and raw_fn.lower() not in {'none', 'nan', 'null'} else None
        ln = raw_ln.title() if raw_ln and raw_ln.lower() not in {'none', 'nan', 'null'} else None

        if raw_fn and fn and raw_fn != fn:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'first_name',
                'old_value': raw_fn, 'new_value': fn, 'reason': 'Title-cased name formatting'
            })
            fields_fixed_count += 1

        if raw_ln and ln and raw_ln != ln:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'last_name',
                'old_value': raw_ln, 'new_value': ln, 'reason': 'Title-cased name formatting'
            })
            fields_fixed_count += 1

        # 2. Email Validation with International Support (idna)
        raw_email = str(row.get('email', '') or '').strip()
        email = validate_email_intl(raw_email)
        if raw_email and raw_email.lower() not in {'none', 'nan', 'null', 'n/a', 'noemail'} and raw_email != email:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'email',
                'old_value': raw_email, 'new_value': email or 'Invalid email removed',
                'reason': 'Validated internationalized email format'
            })
            fields_fixed_count += 1

        # 3. Phone Normalization (E.164 with default country support)
        raw_phone = str(row.get('phone', '') or '').strip()
        phone = normalize_phone_intl(raw_phone, default_country=default_country)
        if raw_phone and phone and raw_phone != phone:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'phone',
                'old_value': raw_phone, 'new_value': phone, 'reason': f'Normalized to E.164 phone format ({default_country})'
            })
            fields_fixed_count += 1

        # CRITICAL FILTER: Drop rows missing BOTH valid email AND valid phone
        if not email and not phone:
            raw_c = row.get('company')
            comp_str = str(raw_c).strip() if (pd.notnull(raw_c) and str(raw_c).lower() not in {'nan', 'none', 'null'}) else None
            rejected_rows.append({
                'row_number': row_num,
                'first_name': fn,
                'last_name': ln,
                'company': comp_str,
                'reason': 'Missing both valid email and phone contact details'
            })
            continue

        # 4. Company Name Normalization
        raw_comp = str(row.get('company', '') or '').strip()
        comp = normalize_company(raw_comp) if raw_comp and raw_comp.lower() not in {'none', 'nan', 'null'} else None
        if raw_comp and comp and raw_comp != comp:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'company',
                'old_value': raw_comp, 'new_value': comp, 'reason': 'Standardized company casing'
            })
            fields_fixed_count += 1

        # 5. Country Detection & State Normalization
        raw_country = row.get('country')
        raw_state = str(row.get('state', '') or '').strip()
        state, state_country = normalize_state_intl(raw_state)
        country = detect_country(
            country_col=raw_country,
            phone_e164=phone,
            email=email,
            state=raw_state,
            default_country=default_country
        )
        # If country is India and state was detected, re-normalize
        if country == 'India' and state == 'UNKNOWN' and raw_state:
            state, _ = normalize_state_intl(raw_state, 'India')

        if raw_state and state and raw_state != state and state != 'UNKNOWN':
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'state',
                'old_value': raw_state, 'new_value': state, 'reason': 'Standardized state name'
            })
            fields_fixed_count += 1

        # 6. Dates
        raw_date = row.get('last_activity_date')
        act_date = parse_iso_date(raw_date)
        if raw_date and act_date and str(raw_date).strip() != act_date:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'last_activity_date',
                'old_value': str(raw_date), 'new_value': act_date, 'reason': 'Parsed into ISO-8601 date'
            })
            fields_fixed_count += 1

        raw_created = row.get('created_date')
        created_dt = parse_iso_date(raw_created) or today_str

        # 7. Company Size
        raw_cs = row.get('company_size')
        comp_size = parse_company_size_value(raw_cs)
        if raw_cs and str(raw_cs).strip() != str(comp_size):
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'company_size',
                'old_value': str(raw_cs), 'new_value': str(comp_size) if comp_size else 'None', 'reason': 'Parsed numeric employee band'
            })
            fields_fixed_count += 1

        # 8. Industry
        raw_ind = row.get('industry')
        industry = standardize_industry(raw_ind)
        if raw_ind and str(raw_ind).strip() != industry:
            cleaning_logs.append({
                'run_id': run_id, 'row_index': row_num, 'field_name': 'industry',
                'old_value': str(raw_ind), 'new_value': industry, 'reason': 'Standardized industry domain'
            })
            fields_fixed_count += 1

        # 9. Engagement Score
        raw_eng = row.get('engagement_score')
        if pd.notnull(raw_eng) and str(raw_eng).strip() not in {'', 'None', 'nan'}:
            try:
                eng_val = float(str(raw_eng).replace('%', '').strip())
                if 0.0 <= eng_val <= 100.0:
                    eng_score = eng_val
                else:
                    eng_score = None
            except Exception:
                eng_score = None
        else:
            eng_score = None

        # 10. Junk & Borderline Review Detection
        is_junk, junk_reason, needs_review = is_advanced_junk_lead(fn, ln, email, comp, phone)
        if is_junk:
            junk_count += 1

        valid_leads.append({
            'run_id': run_id,
            'row_index': row_num,
            'first_name': fn,
            'last_name': ln,
            'email': email,
            'phone': phone,
            'company': comp,
            'job_title': str(row.get('job_title', '') or '').strip() or None,
            'state': state,
            'city': str(row.get('city', '') or '').strip() or None,
            'country': country,
            'industry': industry,
            'company_size': comp_size,
            'engagement_score': eng_score,
            'last_activity_date': act_date,
            'lead_source': str(row.get('lead_source', '') or '').strip() or 'Direct Upload',
            'created_date': created_dt,
            'extra_fields': row.get('extra_fields'),
            'is_junk': is_junk,
            'junk_reason': junk_reason,
            'needs_review': needs_review,
            'review_reason': junk_reason if needs_review else None
        })

    stats = {
        'total_rows_in': len(df),
        'valid_leads_count': len(valid_leads),
        'rejected_rows_count': len(rejected_rows),
        'fields_fixed_count': fields_fixed_count,
        'junk_rows_count': junk_count
    }

    return valid_leads, rejected_rows, cleaning_logs, stats
