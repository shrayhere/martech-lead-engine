"""CSV reading, validation, column detection/mapping and row-level cleaning.

Uploaded files are treated strictly as untrusted text: they are decoded, parsed as CSV and
never executed. Pandas is used to profile columns for the preview; the standard csv module
streams rows in chunks so every row keeps its exact line number for error reports.
"""
import csv
import io
import re
from datetime import timedelta

import pandas as pd

from app.models.base import utcnow
from app.services import data_cleaner as dc
from app.utils.api import ApiError

ALLOWED_EXTENSIONS = {".csv", ".txt"}
DELIMITERS = [",", ";", "\t", "|"]

# target field -> (label, group)
TARGET_FIELDS = {
    "full_name": ("Full name (split into first & last)", "Contact"),
    "first_name": ("First name", "Contact"),
    "last_name": ("Last name", "Contact"),
    "email": ("Email", "Contact"),
    "phone": ("Phone", "Contact"),
    "job_title": ("Job title", "Contact"),
    "lifecycle_stage": ("Lifecycle stage", "Contact"),
    "lead_source": ("Lead source", "Contact"),
    "company_name": ("Company name", "Company"),
    "industry": ("Industry", "Company"),
    "website": ("Website", "Company"),
    "company_email": ("Company email", "Company"),
    "company_phone": ("Company phone", "Company"),
    "address": ("Address", "Company"),
    "city": ("City", "Company"),
    "country": ("Country", "Company"),
    "employee_count": ("Employee count", "Company"),
    "annual_revenue": ("Annual revenue", "Company"),
    "company_description": ("Company description", "Company"),
    "activity_type": ("Activity type", "Activity"),
    "activity_date": ("Activity date", "Activity"),
    "activity_description": ("Activity description", "Activity"),
}

SYNONYMS = {
    "first_name": ["first name", "firstname", "fname", "given name", "first"],
    "last_name": ["last name", "lastname", "surname", "family name", "lname", "last"],
    "full_name": ["name", "full name", "fullname", "contact name", "contact", "person", "lead name"],
    "email": ["email", "e mail", "email address", "mail", "work email", "business email", "email id"],
    "phone": ["phone", "phone number", "mobile", "mobile number", "cell", "telephone", "tel",
              "contact number", "phone no", "mobile no", "whatsapp"],
    "job_title": ["job title", "title", "designation", "position", "role", "job"],
    "lifecycle_stage": ["lifecycle", "lifecycle stage", "stage", "lead stage"],
    "lead_source": ["lead source", "source", "channel", "utm source", "lead channel", "origin"],
    "company_name": ["company", "company name", "organization", "organisation", "account", "employer",
                     "business", "account name", "org"],
    "industry": ["industry", "sector", "vertical", "company industry"],
    "website": ["website", "web", "url", "domain", "company website", "site", "web site"],
    "company_email": ["company email", "office email", "general email"],
    "company_phone": ["company phone", "office phone", "main phone", "company phone number"],
    "address": ["address", "street", "street address", "company address", "address line 1"],
    "city": ["city", "town", "location city"],
    "country": ["country", "nation", "country name", "country code"],
    "employee_count": ["employees", "employee count", "company size", "headcount", "size",
                       "no of employees", "number of employees", "employee size"],
    "annual_revenue": ["revenue", "annual revenue", "arr", "turnover", "company revenue"],
    "company_description": ["description", "company description", "about", "about company"],
    "activity_type": ["activity", "activity type", "last activity", "engagement", "interaction",
                      "last action", "action"],
    "activity_date": ["activity date", "last activity date", "engagement date", "last activity at",
                      "date", "last engaged", "interaction date"],
    "activity_description": ["activity description", "notes", "note", "comments", "comment", "remarks"],
}


def _norm_header(h):
    return re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()


_LOOKUP = {s: field for field, syns in SYNONYMS.items() for s in syns}


def suggest_mapping(columns):
    mapping, used = {}, set()
    for col in columns:
        key = _norm_header(col)
        field = _LOOKUP.get(key) or _LOOKUP.get(key.replace(" ", ""))
        if not field and key.replace(" ", "_") in TARGET_FIELDS:
            field = key.replace(" ", "_")
        if field and field not in used:
            mapping[col] = field
            used.add(field)
        else:
            mapping[col] = ""
    return mapping


def validate_upload(filename, data, max_bytes):
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ApiError("Only .csv files are accepted.", 415)
    if not data or not data.strip():
        raise ApiError("The uploaded file is empty.", 400)
    if len(data) > max_bytes:
        raise ApiError(f"File is too large. Maximum upload size is {max_bytes // (1024 * 1024)} MB.", 413)
    if b"\x00" in data[:8192]:
        raise ApiError("The file appears to be binary, not a CSV text file.", 415)
    if data[:4] in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
        raise ApiError("This looks like an Excel workbook. Please export it as CSV first.", 415)


def decode(data):
    """Return (text, encoding, warning)."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc), ("utf-8" if enc == "utf-8-sig" else enc), None
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1"), "latin-1", "File is not valid UTF-8; decoded as Latin-1. Check special characters."


def detect_delimiter(text):
    sample = text[:20000]
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(DELIMITERS)).delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        counts = {d: first.count(d) for d in DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] else ","


def _unique_headers(raw):
    seen, out = {}, []
    for i, h in enumerate(raw):
        name = (h or "").strip().strip("﻿") or f"column_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def read_header(text, delimiter):
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for row in reader:
        if any(c.strip() for c in row):
            headers = _unique_headers(row)
            if len(headers) < 1:
                break
            return headers
    raise ApiError("The CSV file has no header row.", 400)


def profile(text, delimiter, columns, preview_rows=10):
    """Pandas-based preview: first rows + per-column fill rate and sample values."""
    try:
        df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False,
                         skip_blank_lines=True, engine="python", on_bad_lines="skip", nrows=5000,
                         header=0, names=columns)
    except Exception as exc:  # malformed beyond recovery
        raise ApiError(f"Could not parse the CSV file: {exc}", 400)
    df = df.fillna("")
    stats = []
    for col in columns:
        series = df[col].astype(str).str.strip() if col in df else pd.Series(dtype=str)
        filled = int((series != "").sum())
        stats.append({
            "column": col,
            "filled": filled,
            "fill_rate": round(filled / len(df) * 100, 1) if len(df) else 0,
            "unique": int(series[series != ""].nunique()),
            "samples": series[series != ""].head(3).tolist(),
        })
    preview = df.head(preview_rows).to_dict(orient="records")
    return preview, stats


def count_rows(text, delimiter):
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    next(reader, None)
    return sum(1 for row in reader if any(c.strip() for c in row))


def iter_chunks(text, delimiter, columns, chunk_size=1000):
    """Yield lists of (row_number, {column: value} | None, error) — row_number is the 1-based file line."""
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header_seen = False
    chunk = []
    for row in reader:
        if not header_seen:
            if any(c.strip() for c in row):
                header_seen = True
            continue
        line = reader.line_num
        if not any(c.strip() for c in row):
            continue
        if len(row) != len(columns):
            if len(row) > len(columns) and not any(c.strip() for c in row[len(columns):]):
                row = row[:len(columns)]
            else:
                chunk.append((line, dict(zip(columns, row)),
                              f"Malformed row: expected {len(columns)} fields but found {len(row)}."))
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
                continue
        chunk.append((line, dict(zip(columns, row)), None))
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def validate_mapping(mapping, columns):
    errors = {}
    unknown_cols = [c for c in mapping if c not in columns]
    if unknown_cols:
        errors["columns"] = f"Mapped columns not found in the file: {', '.join(unknown_cols)}"
    targets = [t for t in mapping.values() if t]
    bad = [t for t in targets if t not in TARGET_FIELDS]
    if bad:
        errors["fields"] = f"Unknown target fields: {', '.join(bad)}"
    dupes = sorted({t for t in targets if targets.count(t) > 1})
    if dupes:
        errors["duplicates"] = f"Each field can only be mapped once: {', '.join(dupes)}"
    if not ({"email", "phone"} & set(targets)):
        errors["identifier"] = "Map at least one identifier column: Email or Phone."
    if not ({"email", "first_name", "full_name", "last_name"} & set(targets)):
        errors["name"] = "Map a name column (Full name or First name) or Email."
    if "full_name" in targets and ("first_name" in targets or "last_name" in targets):
        errors["name_conflict"] = "Map either Full name or First/Last name, not both."
    if errors:
        raise ApiError("The column mapping is not valid.", 422, errors)
    return {c: t for c, t in mapping.items() if t}


def clean_record(raw_row, mapping, default_cc="+1", now=None):
    """Map a raw CSV row to cleaned contact/company/activity dicts. Returns dict with errors & warnings."""
    now = now or utcnow()
    v = {target: raw_row.get(col) for col, target in mapping.items()}
    errors, warnings = [], []

    first, last = dc.normalize_person_name(v.get("first_name")), dc.normalize_person_name(v.get("last_name"))
    if "full_name" in v:
        first, last = dc.split_full_name(v.get("full_name"))

    raw_email = dc.clean_str(v.get("email"))
    email = dc.normalize_email(raw_email)
    if email and not dc.is_valid_email(email):
        errors.append(f"Invalid email format: '{raw_email}'.")

    phone, phone_ok = dc.normalize_phone(v.get("phone"), default_cc)
    if not phone_ok:
        warnings.append(f"Phone '{dc.clean_str(v.get('phone'))}' could not be normalised; stored as provided.")

    if not email and not phone and not raw_email:
        errors.append("Missing contact identifier: an email address or phone number is required.")

    if not first:
        if email and dc.is_valid_email(email):
            first = dc.normalize_person_name(re.split(r"[._+\-]", email.split("@")[0])[0]) or email.split("@")[0]
            warnings.append("First name missing; derived from the email address.")
        else:
            errors.append("Missing name: provide a first name or full name.")

    stage = None
    if v.get("lifecycle_stage") not in (None, ""):
        stage = dc.normalize_lifecycle(v.get("lifecycle_stage"))
        if not stage:
            warnings.append(f"Unknown lifecycle stage '{dc.clean_str(v.get('lifecycle_stage'))}'; set to 'lead'.")

    contact = {
        "first_name": first,
        "last_name": last,
        "email": email,
        "phone": phone,
        "job_title": dc.clean_str(v.get("job_title"), 150),
        "lead_source": dc.normalize_lead_source(v.get("lead_source")),
        "lifecycle_stage": stage,
    }

    company = None
    company_name = dc.standardize_company_name(v.get("company_name"))
    company_fields_present = any(dc.clean_str(v.get(f)) for f in (
        "industry", "website", "company_email", "company_phone", "address", "city", "country",
        "employee_count", "annual_revenue", "company_description"))
    if company_name:
        company = {"company_name": company_name, "industry": dc.normalize_industry(v.get("industry"))}
        raw_site = dc.clean_str(v.get("website"))
        company["website"] = dc.normalize_website(raw_site)
        if raw_site and not company["website"]:
            warnings.append(f"Website '{raw_site}' is not a valid domain and was not imported.")
        cemail = dc.normalize_email(v.get("company_email"))
        if cemail and not dc.is_valid_email(cemail):
            warnings.append(f"Company email '{cemail}' is invalid and was not imported.")
            cemail = None
        company["company_email"] = cemail
        cphone, cphone_ok = dc.normalize_phone(v.get("company_phone"), default_cc)
        if not cphone_ok:
            warnings.append("Company phone could not be normalised; stored as provided.")
        company["phone"] = cphone
        company["address"] = dc.clean_str(v.get("address"), 255)
        company["city"] = dc.normalize_city(v.get("city"))
        company["country"] = dc.normalize_country(v.get("country"))
        company["description"] = dc.clean_str(v.get("company_description"))
        try:
            company["employee_count"] = dc.parse_int(v.get("employee_count"))
        except ValueError as e:
            company["employee_count"] = None
            warnings.append(f"Employee count ignored: {e}.")
        try:
            company["annual_revenue"] = dc.parse_decimal(v.get("annual_revenue"))
        except ValueError as e:
            company["annual_revenue"] = None
            warnings.append(f"Annual revenue ignored: {e}.")
    elif company_fields_present:
        warnings.append("Company details were provided without a company name and were not imported.")

    activity = None
    raw_type = dc.clean_str(v.get("activity_type"))
    raw_date = dc.clean_str(v.get("activity_date"))
    if raw_type or raw_date:
        a_type = dc.normalize_activity_type(raw_type) if raw_type else "other_engagement"
        if raw_type and not a_type:
            warnings.append(f"Unknown activity type '{raw_type}'; recorded as 'other engagement' (0 points).")
            a_type = "other_engagement"
        a_date = None
        if raw_date:
            try:
                a_date = dc.parse_date(raw_date)
            except ValueError:
                errors.append(f"Invalid activity date '{raw_date}'.")
        if a_date is None and not errors:
            a_date = now
            warnings.append("Activity date missing; the import time was used.")
        if a_date and a_date > now + timedelta(days=1):
            warnings.append("Activity date is in the future; the import time was used instead.")
            a_date = now
        desc = dc.clean_str(v.get("activity_description"))
        if raw_type and a_type == "other_engagement" and not desc:
            desc = f"Imported activity: {raw_type}"
        activity = {"activity_type": a_type, "activity_date": a_date, "activity_description": desc}

    return {"contact": contact, "company": company, "activity": activity, "errors": errors, "warnings": warnings}
