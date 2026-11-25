"""
Geo, state, country, and phone normalization utilities for US, India, and international data.
"""
import re
from typing import Optional, Tuple
import idna
import phonenumbers
from phonenumbers import PhoneNumberFormat

INDIAN_STATES = {
    "ANDAMAN AND NICOBAR ISLANDS": "Andaman and Nicobar Islands",
    "ANDHRA PRADESH": "Andhra Pradesh",
    "ARUNACHAL PRADESH": "Arunachal Pradesh",
    "ASSAM": "Assam",
    "BIHAR": "Bihar",
    "CHANDIGARH": "Chandigarh",
    "CHHATTISGARH": "Chhattisgarh",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "Dadra and Nagar Haveli and Daman and Diu",
    "DELHI": "Delhi",
    "GOA": "Goa",
    "GUJARAT": "Gujarat",
    "HARYANA": "Haryana",
    "HIMACHAL PRADESH": "Himachal Pradesh",
    "JAMMU AND KASHMIR": "Jammu and Kashmir",
    "JHARKHAND": "Jharkhand",
    "KARNATAKA": "Karnataka",
    "KERALA": "Kerala",
    "LADAKH": "Ladakh",
    "LAKSHADWEEP": "Lakshadweep",
    "MADHYA PRADESH": "Madhya Pradesh",
    "MAHARASHTRA": "Maharashtra",
    "MANIPUR": "Manipur",
    "MEGHALAYA": "Meghalaya",
    "MIZORAM": "Mizoram",
    "NAGALAND": "Nagaland",
    "ODISHA": "Odisha",
    "ORISSA": "Odisha",
    "PUDUCHERRY": "Puducherry",
    "PONDICHERRY": "Puducherry",
    "PUNJAB": "Punjab",
    "RAJASTHAN": "Rajasthan",
    "SIKKIM": "Sikkim",
    "TAMIL NADU": "Tamil Nadu",
    "TELANGANA": "Telangana",
    "TRIPURA": "Tripura",
    "UTTAR PRADESH": "Uttar Pradesh",
    "UTTARAKHAND": "Uttarakhand",
    "WEST BENGAL": "West Bengal"
}

# India region mapping for rep routing
INDIA_TERRITORIES = {
    "NORTH": {
        "DELHI", "HARYANA", "PUNJAB", "HIMACHAL PRADESH", "JAMMU AND KASHMIR",
        "LADAKH", "UTTARAKHAND", "UTTAR PRADESH", "CHANDIGARH", "RAJASTHAN"
    },
    "SOUTH": {
        "KARNATAKA", "TAMIL NADU", "KERALA", "TELANGANA", "ANDHRA PRADESH",
        "PUDUCHERRY", "LAKSHADWEEP", "GOA"
    },
    "WEST": {
        "MAHARASHTRA", "GUJARAT", "MADHYA PRADESH", "CHHATTISGARH",
        "DADRA AND NAGAR HAVELI AND DAMAN AND DIU", "MUMBAI", "PUNE"
    },
    "EAST": {
        "WEST BENGAL", "BIHAR", "JHARKHAND", "ODISHA", "ASSAM", "SIKKIM",
        "TRIPURA", "MEGHALAYA", "MANIPUR", "NAGALAND", "MIZORAM", "ARUNACHAL PRADESH",
        "ANDAMAN AND NICOBAR ISLANDS"
    }
}

# US State abbreviations
US_STATES_MAP = {
    "ALABAMA": "AL", "AL": "AL", "ALAF": "AL",
    "ALASKA": "AK", "AK": "AK",
    "ARIZONA": "AZ", "AZ": "AZ", "ARIZ": "AZ",
    "ARKANSAS": "AR", "AR": "AR",
    "CALIFORNIA": "CA", "CA": "CA", "CALIF": "CA", "CALIF.": "CA", "CALI": "CA",
    "COLORADO": "CO", "CO": "CO", "COLO": "CO",
    "CONNECTICUT": "CT", "CT": "CT", "CONN": "CT",
    "DELAWARE": "DE", "DE": "DE",
    "FLORIDA": "FL", "FL": "FL", "FLA": "FL",
    "GEORGIA": "GA", "GA": "GA",
    "HAWAII": "HI", "HI": "HI",
    "IDAHO": "ID", "ID": "ID",
    "ILLINOIS": "IL", "IL": "IL", "ILL": "IL",
    "INDIANA": "IN", "IN": "IN", "IND": "IN",
    "IOWA": "IA", "IA": "IA",
    "KANSAS": "KS", "KS": "KS", "KANS": "KS",
    "KENTUCKY": "KY", "KY": "KY",
    "LOUISIANA": "LA", "LA": "LA",
    "MAINE": "ME", "ME": "ME",
    "MARYLAND": "MD", "MD": "MD",
    "MASSACHUSETTS": "MA", "MA": "MA", "MASS": "MA",
    "MICHIGAN": "MI", "MI": "MI", "MICH": "MI",
    "MINNESOTA": "MN", "MN": "MN", "MINN": "MN",
    "MISSISSIPPI": "MS", "MS": "MS",
    "MISSOURI": "MO", "MO": "MO",
    "MONTANA": "MT", "MT": "MT",
    "NEBRASKA": "NE", "NE": "NE", "NEBR": "NE",
    "NEVADA": "NV", "NV": "NV",
    "NEW HAMPSHIRE": "NH", "NH": "NH",
    "NEW JERSEY": "NJ", "NJ": "NJ",
    "NEW MEXICO": "NM", "NM": "NM",
    "NEW YORK": "NY", "NY": "NY", "N.Y.": "NY",
    "NORTH CAROLINA": "NC", "NC": "NC",
    "NORTH DAKOTA": "ND", "ND": "ND",
    "OHIO": "OH", "OH": "OH",
    "OKLAHOMA": "OK", "OK": "OK", "OKLA": "OK",
    "OREGON": "OR", "OR": "OR", "ORE": "OR",
    "PENNSYLVANIA": "PA", "PA": "PA", "PENN": "PA",
    "RHODE ISLAND": "RI", "RI": "RI",
    "SOUTH CAROLINA": "SC", "SC": "SC",
    "SOUTH DAKOTA": "SD", "SD": "SD",
    "TENNESSEE": "TN", "TN": "TN", "TENN": "TN",
    "TEXAS": "TX", "TX": "TX", "TEX": "TX",
    "UTAH": "UT", "UT": "UT",
    "VERMONT": "VT", "VT": "VT",
    "VIRGINIA": "VA", "VA": "VA",
    "WASHINGTON": "WA", "WA": "WA", "WASH": "WA",
    "WEST VIRGINIA": "WV", "WV": "WV",
    "WISCONSIN": "WI", "WI": "WI", "WISC": "WI",
    "WYOMING": "WY", "WY": "WY",
    "DISTRICT OF COLUMBIA": "DC", "DC": "DC"
}

TLD_COUNTRY_MAP = {
    ".in": "India",
    ".co.in": "India",
    ".de": "Germany",
    ".uk": "United Kingdom",
    ".co.uk": "United Kingdom",
    ".ca": "Canada",
    ".au": "Australia",
    ".fr": "France",
    ".jp": "Japan",
    ".cn": "China",
    ".sg": "Singapore",
    ".ae": "United Arab Emirates",
}

DISPOSABLE_DOMAINS = {
    "mailinator.com", "example.com", "test.com", "fake.com", "sample.com",
    "bot.com", "none.com", "null.com", "asdf.com", "tempmail.com", "guerrillamail.com",
    "10minutemail.com", "trashmail.com", "sharklasers.com", "yopmail.com"
}

FAKE_NAMES = {
    "mickey mouse", "donald duck", "goofy", "minnie mouse", "daisy duck",
    "bugs bunny", "daffy duck", "batman", "superman", "spider man", "spiderman",
    "iron man", "ironman", "test user", "john doe", "jane doe", "asdf asdf",
    "qwerty qwerty", "fake person", "test lead", "sample lead", "spam lead",
    "dummy lead", "foo bar", "bar baz"
}

KEYBOARD_MASH_PATTERNS = [
    r"^[asdfghjkl]{4,}$",
    r"^[qwertyuiop]{5,}$",
    r"^[zxcvbnm]{4,}$",
    r"^[1234567890]{5,}$"
]

REPEATED_OR_INVALID_PHONES = {
    "1234567890", "0000000000", "1111111111", "2222222222", "3333333333",
    "4444444444", "5555555555", "6666666666", "7777777777", "8888888888",
    "9999999999", "123456789", "0123456789", "9876543210"
}


def normalize_phone_intl(phone_raw: Optional[str], default_country: str = "IN") -> Optional[str]:
    """
    Standardizes international and national phone numbers to E.164.
    Defaults to India ('IN') if no country code is present.
    Rejects repeated digits or dummy patterns (e.g. 1234567890, 0000000000).
    """
    if not phone_raw or not str(phone_raw).strip():
        return None

    clean = str(phone_raw).strip()
    digits = re.sub(r"\D", "", clean)
    if digits in REPEATED_OR_INVALID_PHONES or len(digits) < 7:
        return None

    try:
        if clean.startswith("+"):
            parsed = phonenumbers.parse(clean, None)
        else:
            parsed = phonenumbers.parse(clean, default_country)

        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    except Exception:
        pass

    return None


def validate_email_intl(email_raw: Optional[str]) -> Optional[str]:
    """
    Validates email format, including internationalized domain names (e.g. jose@münchen.de).
    Rejects invalid syntax like 'user@gmail' without valid TLD.
    Returns cleaned lowercase email or None.
    """
    if not email_raw or not str(email_raw).strip() or "@" not in str(email_raw):
        return None

    clean = str(email_raw).strip().lower()
    parts = clean.split("@")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None

    user, domain = parts
    try:
        ascii_domain = idna.encode(domain).decode("ascii")
    except Exception:
        return None

    ascii_email = f"{user}@{ascii_domain}"
    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", ascii_email):
        return None

    if "." not in ascii_domain:
        return None

    tld = ascii_domain.split(".")[-1]
    if len(tld) < 2 or not tld.isalpha():
        return None

    return clean


def normalize_state_intl(state_raw: Optional[str], country_hint: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """
    Normalizes state names:
    - US states -> 2-letter code (e.g. California -> CA)
    - Indian states -> Proper full name (e.g. Uttar Pradesh -> Uttar Pradesh)
    - International states/provinces -> Kept as clean full names (e.g. Bayern -> Bayern)
    Returns: (normalized_state, detected_country)
    """
    if not state_raw or not str(state_raw).strip():
        return "UNKNOWN", country_hint

    raw = str(state_raw).strip()
    clean_upper = raw.upper().replace(".", "").strip()

    # 1. Check Indian States first (avoid 'Uttar Pradesh' -> 'UT' or 'Gujarat' -> 'GU')
    if clean_upper in INDIAN_STATES:
        return INDIAN_STATES[clean_upper], "India"

    for ind_k, ind_name in INDIAN_STATES.items():
        if ind_k in clean_upper or clean_upper in ind_k:
            return ind_name, "India"

    # 2. Check US States only if country hint is US or not explicitly foreign
    if country_hint in (None, "USA", "United States", "US"):
        if clean_upper in US_STATES_MAP:
            return US_STATES_MAP[clean_upper], "USA"

    # 3. Known German / European states (e.g. Bayern)
    if clean_upper in {"BAYERN", "BAVARIA", "BERLIN", "HESSE", "HESSEN", "SAXONY"}:
        return raw.title(), "Germany"

    # 4. If country is explicitly not USA, keep full name
    if country_hint and country_hint not in ("USA", "United States", "US"):
        return raw.title(), country_hint

    # 5. Fallback US check
    if clean_upper in US_STATES_MAP:
        return US_STATES_MAP[clean_upper], "USA"

    # Return trimmed title case
    return raw.title(), country_hint


def detect_country(
    country_col: Optional[str],
    phone_e164: Optional[str],
    email: Optional[str],
    state: Optional[str],
    default_country: str = "India"
) -> str:
    """
    Infers country from available signals:
    1. Direct country column value
    2. Phone E.164 country code (+91 -> India, +1 -> USA, +49 -> Germany, etc.)
    3. Email TLD (.in -> India, .de -> Germany, .cn -> China)
    4. State name (Indian states -> India, US 2-letter codes -> USA)
    5. Fallback to default_country
    """
    if country_col and str(country_col).strip() and str(country_col).lower() not in {"nan", "none", "unknown"}:
        c_str = str(country_col).strip()
        c_upper = c_str.upper()
        if c_upper in {"IN", "IND", "INDIA"}:
            return "India"
        if c_upper in {"US", "USA", "UNITED STATES"}:
            return "USA"
        if c_upper in {"DE", "GERMANY", "DEUTSCHLAND"}:
            return "Germany"
        return c_str.title()

    if phone_e164 and phone_e164.startswith("+"):
        if phone_e164.startswith("+91"):
            return "India"
        if phone_e164.startswith("+1"):
            return "USA"
        if phone_e164.startswith("+49"):
            return "Germany"
        if phone_e164.startswith("+44"):
            return "United Kingdom"
        if phone_e164.startswith("+86"):
            return "China"
        if phone_e164.startswith("+65"):
            return "Singapore"
        if phone_e164.startswith("+971"):
            return "United Arab Emirates"

    if email and "@" in email:
        domain = email.split("@")[-1].lower()
        for tld, c_name in TLD_COUNTRY_MAP.items():
            if domain.endswith(tld):
                return c_name

    if state:
        st_upper = state.strip().upper()
        if st_upper in INDIAN_STATES or any(st_upper == k for k in INDIAN_STATES):
            return "India"
        if st_upper in US_STATES_MAP:
            return "USA"

    return default_country


def is_advanced_junk_lead(
    first_name: Optional[str],
    last_name: Optional[str],
    email: Optional[str],
    company: Optional[str],
    phone: Optional[str]
) -> Tuple[bool, Optional[str], bool]:
    """
    Flags junk and borderline cases:
    Returns: (is_junk, reason, needs_review)
    - If True, reason, False: definitive junk (disposable email, fake cartoon names, test numbers).
    - If False, reason, True: borderline case (e.g. no email but valid phone) sent to Review queue.
    """
    fn = (first_name or "").strip().lower()
    ln = (last_name or "").strip().lower()
    full_name = f"{fn} {ln}".strip()
    em = (email or "").strip().lower()
    comp = (company or "").strip().lower()
    ph = (phone or "").strip()

    # 1. Missing both email and phone
    if not em and not ph:
        return True, "Missing both email and phone contact details", False

    # 2. Fake cartoon or celebrity names
    if full_name in FAKE_NAMES or fn in {"mickey", "donald", "batman", "superman"}:
        return True, f"Fictional / placeholder celebrity name detected ('{full_name}')", False

    # 3. Disposable email domains
    if em and "@" in em:
        domain = em.split("@")[-1].lower()
        if domain in DISPOSABLE_DOMAINS:
            return True, f"Disposable or test email domain ('{domain}')", False

    # 4. Keyboard mash
    for pat in KEYBOARD_MASH_PATTERNS:
        if (fn and re.match(pat, fn)) or (ln and re.match(pat, ln)) or (comp and re.match(pat, comp)):
            return True, "Keyboard mash detected in name or company", False

    # 5. Invalid repeated phone numbers
    digits = re.sub(r"\D", "", ph)
    if digits in REPEATED_OR_INVALID_PHONES:
        return True, f"Dummy or sequential phone number ('{ph}')", False

    # 6. Placeholder company names
    if comp in {"test", "n/a", "na", "asdf", "none", "null", "dummy", "test company", "asdf inc", "xyz"}:
        return True, f"Placeholder company name ('{comp}')", False

    # 7. Borderline case: Phone only, NO valid email -> goes to Review queue
    if ph and not em:
        return False, "Lead has phone number but missing valid email address", True

    return False, None, False
