"""Field-level normalisation and validation shared by manual entry and CSV imports."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[a-z0-9._%+\-']+@[a-z0-9.\-]+\.[a-z]{2,}$")
PLACEHOLDERS = {"", "n/a", "na", "none", "null", "nil", "-", "--", "?", "unknown", "nan", "#n/a"}

COMPANY_SUFFIXES = {
    "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation", "co", "company", "plc",
    "gmbh", "pvt", "private", "pte", "sa", "ag", "bv", "llp", "lp",
}
ACRONYM_MAX = 4

COUNTRY_ALIASES = {
    "us": "United States", "usa": "United States", "u.s.": "United States", "u.s.a.": "United States",
    "united states": "United States", "united states of america": "United States", "america": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "gb": "United Kingdom", "great britain": "United Kingdom",
    "england": "United Kingdom", "united kingdom": "United Kingdom",
    "in": "India", "ind": "India", "india": "India", "bharat": "India",
    "de": "Germany", "germany": "Germany", "deutschland": "Germany",
    "fr": "France", "france": "France",
    "ca": "Canada", "can": "Canada", "canada": "Canada",
    "au": "Australia", "aus": "Australia", "australia": "Australia",
    "sg": "Singapore", "singapore": "Singapore",
    "ae": "United Arab Emirates", "uae": "United Arab Emirates", "united arab emirates": "United Arab Emirates",
    "jp": "Japan", "japan": "Japan", "cn": "China", "china": "China",
    "nl": "Netherlands", "netherlands": "Netherlands", "holland": "Netherlands",
    "es": "Spain", "spain": "Spain", "it": "Italy", "italy": "Italy", "br": "Brazil", "brazil": "Brazil",
}
CITY_ALIASES = {
    "nyc": "New York", "new york city": "New York", "sf": "San Francisco", "bombay": "Mumbai",
    "bangalore": "Bengaluru", "blr": "Bengaluru", "madras": "Chennai", "calcutta": "Kolkata",
    "gurgaon": "Gurugram", "la": "Los Angeles", "dc": "Washington", "delhi": "New Delhi",
}

LIFECYCLE_ALIASES = {
    "subscriber": "subscriber", "lead": "lead", "new": "lead", "prospect": "lead",
    "mql": "mql", "marketing qualified lead": "mql", "marketing qualified": "mql",
    "sql": "sql", "sales qualified lead": "sql", "sales qualified": "sql",
    "opportunity": "opportunity", "opp": "opportunity", "customer": "customer", "client": "customer",
    "evangelist": "evangelist", "advocate": "evangelist", "other": "other",
}

ACTIVITY_ALIASES = {
    "demo_requested": "demo_requested", "demo": "demo_requested", "requested demo": "demo_requested",
    "demo request": "demo_requested", "product demo": "demo_requested",
    "pricing_inquiry": "pricing_inquiry", "pricing": "pricing_inquiry", "asked for pricing": "pricing_inquiry",
    "pricing inquiry": "pricing_inquiry", "pricing enquiry": "pricing_inquiry",
    "meeting_scheduled": "meeting_scheduled", "meeting": "meeting_scheduled", "scheduled meeting": "meeting_scheduled",
    "meeting scheduled": "meeting_scheduled",
    "form_submitted": "form_submitted", "form": "form_submitted", "contact form": "form_submitted",
    "form submitted": "form_submitted", "form submission": "form_submitted",
    "brochure_downloaded": "brochure_downloaded", "brochure": "brochure_downloaded",
    "brochure downloaded": "brochure_downloaded", "download": "brochure_downloaded",
    "email_clicked": "email_clicked", "email click": "email_clicked", "clicked email": "email_clicked",
    "email clicked": "email_clicked",
    "email_opened": "email_opened", "email open": "email_opened", "opened email": "email_opened",
    "email opened": "email_opened",
    "website_visit": "website_visit", "website visit": "website_visit", "visited product page": "website_visit",
    "page visit": "website_visit", "site visit": "website_visit", "web visit": "website_visit",
    "no_recent_engagement": "no_recent_engagement", "no recent engagement": "no_recent_engagement",
    "other_engagement": "other_engagement", "other": "other_engagement",
}

DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y",
                "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y", "%d %B %Y",
                "%B %d, %Y", "%d.%m.%Y")


def clean_str(value, max_len=None):
    """Trim whitespace, collapse internal runs, map placeholders to None."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if text.lower() in PLACEHOLDERS:
        return None
    if max_len:
        text = text[:max_len]
    return text


def normalize_email(value):
    text = clean_str(value)
    if not text:
        return None
    return text.lower().strip(" <>;,")


def is_valid_email(email):
    return bool(email) and len(email) <= 255 and bool(EMAIL_RE.match(email)) and ".." not in email


def normalize_phone(value, default_country_code="+1"):
    """Return (normalized, is_valid). Valid numbers become E.164-style '+<digits>'."""
    text = clean_str(value)
    if not text:
        return None, True
    text = re.split(r"\s*(?:ext\.?|x|#)\s*\d+$", text, flags=re.I)[0]
    has_plus = text.startswith("+") or text.startswith("00")
    digits = re.sub(r"\D", "", text)
    if text.startswith("00"):
        digits = digits[2:]
    if not digits:
        return text[:32], False
    cc = re.sub(r"\D", "", default_country_code or "")
    if has_plus:
        normalized = "+" + digits
    elif len(digits) == 10:
        normalized = "+" + cc + digits
    elif len(digits) == 11 and digits.startswith("0"):
        normalized = "+" + cc + digits[1:]
    elif cc and digits.startswith(cc) and len(digits) == len(cc) + 10:
        normalized = "+" + digits
    else:
        normalized = "+" + digits
    valid = 8 <= len(normalized) - 1 <= 15
    return (normalized if valid else text[:32]), valid


def phone_key(phone):
    """Last 10 digits — robust key for matching the same number written differently."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 7 else None


def _smart_case(word):
    if not word:
        return word
    letters = re.sub(r"[^A-Za-z]", "", word)
    if letters.isupper() and len(letters) <= ACRONYM_MAX:
        return word  # keep acronyms such as IBM, AWS
    if word.islower() or word.isupper():
        return "-".join(p[:1].upper() + p[1:].lower() for p in word.split("-"))
    return word  # mixed case already intentional (e.g. "HubSpot", "iPhone")


def standardize_company_name(value):
    text = clean_str(value, 200)
    if not text:
        return None
    text = re.sub(r"\s*,\s*", ", ", text)
    return " ".join(_smart_case(w) for w in text.split(" "))


def company_key(name):
    """Normalised identity for duplicate-company detection."""
    if not name:
        return None
    text = name.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [w for w in text.split() if w]
    while len(words) > 1 and words[-1] in COMPANY_SUFFIXES:
        words.pop()
    key = " ".join(words)
    return key[:200] or None


def normalize_country(value):
    text = clean_str(value, 100)
    if not text:
        return None
    return COUNTRY_ALIASES.get(text.lower().strip("."), " ".join(_smart_case(w) for w in text.split()))


def normalize_city(value):
    text = clean_str(value, 100)
    if not text:
        return None
    alias = CITY_ALIASES.get(text.lower())
    if alias:
        return alias
    return " ".join(w[:1].upper() + w[1:].lower() if (w.islower() or w.isupper()) else w for w in text.split())


def normalize_website(value):
    text = clean_str(value, 255)
    if not text:
        return None
    text = text.lower()
    text = re.sub(r"^https?://", "", text).rstrip("/")
    if "." not in text or " " in text:
        return None
    return "https://" + text


def normalize_person_name(value):
    text = clean_str(value, 100)
    if not text:
        return None
    if text.islower() or text.isupper():
        return " ".join("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")) for w in text.split())
    return text


def split_full_name(value):
    text = clean_str(value)
    if not text:
        return None, None
    if "," in text:  # "Sharma, Rahul"
        last, first = [p.strip() for p in text.split(",", 1)]
        return normalize_person_name(first), normalize_person_name(last)
    parts = text.split(" ")
    if len(parts) == 1:
        return normalize_person_name(parts[0]), None
    return normalize_person_name(" ".join(parts[:-1])), normalize_person_name(parts[-1])


def parse_date(value):
    text = clean_str(value)
    if not text:
        return None
    text = text.replace("Z", "")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date '{text}'")


def parse_int(value):
    text = clean_str(value)
    if not text:
        return None
    text = text.replace(",", "").replace("+", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([kKmM]?)$", text)
    if not m:
        # Ranges such as "51-200" -> lower bound
        r = re.match(r"^(\d+)\s*-\s*\d+$", text)
        if r:
            return int(r.group(1))
        raise ValueError(f"'{text}' is not a whole number")
    num = float(m.group(1)) * {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2).lower()]
    return int(num)


def parse_decimal(value):
    text = clean_str(value)
    if not text:
        return None
    text = re.sub(r"[,$€£₹\s]", "", text)
    mult = 1
    if text[-1:].lower() in ("k", "m", "b"):
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[text[-1].lower()]
        text = text[:-1]
    try:
        result = Decimal(text) * mult
    except InvalidOperation:
        raise ValueError(f"'{value}' is not a number")
    if result < 0:
        raise ValueError("Amount cannot be negative")
    return result.quantize(Decimal("0.01"))


def normalize_lifecycle(value):
    text = clean_str(value)
    if not text:
        return None
    return LIFECYCLE_ALIASES.get(text.lower())


def normalize_activity_type(value):
    text = clean_str(value)
    if not text:
        return None
    return ACTIVITY_ALIASES.get(text.lower().replace("-", " ").replace("_", " ")) or \
        ACTIVITY_ALIASES.get(text.lower())


def normalize_lead_source(value):
    text = clean_str(value, 100)
    if not text:
        return None
    return " ".join(_smart_case(w) for w in text.split())


INDUSTRY_ALIASES = {
    "saas": "SaaS", "software as a service": "SaaS", "it": "IT Services", "it services": "IT Services",
    "fintech": "Fintech", "fin tech": "Fintech", "edtech": "EdTech", "ed tech": "EdTech", "ai": "AI",
    "healthtech": "HealthTech", "martech": "MarTech", "b2b": "B2B", "ecommerce": "E-commerce", "e-commerce": "E-commerce",
}


def normalize_industry(value):
    text = clean_str(value, 100)
    if not text:
        return None
    return INDUSTRY_ALIASES.get(text.lower()) or " ".join(_smart_case(w) for w in text.split())
