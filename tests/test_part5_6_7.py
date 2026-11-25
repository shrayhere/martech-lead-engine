import pytest
from app.utils.geo_utils import (
    normalize_phone_intl,
    validate_email_intl,
    normalize_state_intl,
    detect_country,
    is_advanced_junk_lead,
    INDIAN_STATES
)
from app.services.smart_parser import check_missing_headers
from app.services.fast_dedup import merge_lead_records

def test_indian_phone_normalization():
    # Indian mobile number with dash
    p1 = normalize_phone_intl("98765-43212", default_country="IN")
    assert p1 == "+919876543212"

    # Indian mobile number with leading 0
    p2 = normalize_phone_intl("09876543211", default_country="IN")
    assert p2 == "+919876543211"

    # Dummy repeated number is rejected (None)
    p3 = normalize_phone_intl("1234567890", default_country="IN")
    assert p3 is None

    # US number with explicit +1
    p4 = normalize_phone_intl("+1 415 555 2671", default_country="IN")
    assert p4 == "+14155552671"

def test_state_and_country_detection():
    # Indian states stay full names
    state1, c1 = normalize_state_intl("Uttar Pradesh", country_hint="India")
    assert state1 == "Uttar Pradesh"
    assert c1 == "India"

    state2, c2 = normalize_state_intl("Gujarat", country_hint="India")
    assert state2 == "Gujarat"
    assert c2 == "India"

    # German state
    state3, c3 = normalize_state_intl("Bayern", country_hint="Germany")
    assert state3 == "Bayern"
    assert c3 == "Germany"

    # US state converts to 2-letter abbreviation
    state4, c4 = normalize_state_intl("California", country_hint="USA")
    assert state4 == "CA"
    assert c4 == "USA"

    # Detect country signals
    assert detect_country(None, phone_e164="+919876543210", email=None, state=None) == "India"
    assert detect_country(None, phone_e164=None, email="test@company.in", state=None) == "India"
    assert detect_country(None, phone_e164=None, email=None, state="Uttar Pradesh") == "India"
    assert detect_country(None, phone_e164=None, email="jose@company.de", state=None) == "Germany"

def test_international_email_and_junk_validation():
    # Internationalized email
    assert validate_email_intl("jose@münchen.de") == "jose@münchen.de"
    assert validate_email_intl("user@company.com") == "user@company.com"

    # Invalid email without domain TLD
    assert validate_email_intl("riya.sharma@gmail") is None

    # Junk names and disposable emails
    is_junk, reason, _ = is_advanced_junk_lead("Donald", "Duck", "dduck@example.com", "Acme", "1234567890")
    assert is_junk is True
    assert "Donald Duck" in reason or "celebrity" in reason.lower() or "disposable" in reason.lower()

    # Lead with phone but missing email -> needs review (not hot)
    is_j, r_reason, is_rev = is_advanced_junk_lead("Aarav", "Patel", "", "Acme", "+919876543210")
    assert is_j is False
    assert is_rev is True
    assert "email" in r_reason.lower()

def test_missing_headers_detection():
    # CSV with no header (row 1 is data)
    csv_no_header = b"aarav@company.com,9876543210,2026-05-01,VP Engineering\npooja@firm.in,9876543211,2026-05-02,Director"
    has_missing = check_missing_headers(csv_no_header)
    assert has_missing is True

    # CSV with valid header
    csv_valid = b"first_name,last_name,email,title\naarav,patel,aarav@company.com,VP Engineering"
    has_missing2 = check_missing_headers(csv_valid)
    assert has_missing2 is False

def test_duplicate_merge_keeps_newest():
    old_record = {
        "first_name": "Rohan",
        "last_name": "Sharma",
        "email": "rohan@tech.in",
        "company": "Tech Corp",
        "engagement_score": 40,
        "last_activity_date": "2026-01-10"
    }
    new_record = {
        "first_name": "Rohan",
        "last_name": "Sharma",
        "email": "rohan@tech.in",
        "company": "Tech Corp",
        "engagement_score": 85,
        "last_activity_date": "2026-10-15"
    }

    merged = merge_lead_records(old_record, new_record)
    assert merged["engagement_score"] == 85
    assert merged["last_activity_date"] == "2026-10-15"
