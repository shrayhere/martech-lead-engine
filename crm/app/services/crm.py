"""Validation and persistence helpers for companies and contacts (used by API routes, imports and seeding)."""
from flask import current_app

from app.extensions import db
from app.models import LEAD_STATUSES, LIFECYCLE_STAGES, Company, Contact, DataSource
from app.services import data_cleaner as dc
from app.utils.api import ApiError


def _default_cc():
    try:
        return current_app.config.get("DEFAULT_COUNTRY_CODE", "+1")
    except RuntimeError:
        return "+1"


def clean_company_payload(data, partial=False):
    """Validate/normalise company fields. Raises ApiError(422) with per-field messages."""
    errors, out = {}, {}

    def has(f):
        return f in data

    if not partial or has("company_name"):
        name = dc.standardize_company_name(data.get("company_name"))
        if not name:
            errors["company_name"] = "Company name is required."
        else:
            out["company_name"] = name
    if has("industry"):
        out["industry"] = dc.normalize_industry(data.get("industry"))
    if has("website"):
        raw = dc.clean_str(data.get("website"))
        out["website"] = dc.normalize_website(raw)
        if raw and not out["website"]:
            errors["website"] = "Website must be a domain such as example.com."
    if has("company_email"):
        email = dc.normalize_email(data.get("company_email"))
        if email and not dc.is_valid_email(email):
            errors["company_email"] = "Invalid email address."
        out["company_email"] = email
    if has("phone"):
        phone, ok = dc.normalize_phone(data.get("phone"), _default_cc())
        if not ok:
            errors["phone"] = "Invalid phone number."
        out["phone"] = phone
    for f, n in (("address", 255),):
        if has(f):
            out[f] = dc.clean_str(data.get(f), n)
    if has("city"):
        out["city"] = dc.normalize_city(data.get("city"))
    if has("country"):
        out["country"] = dc.normalize_country(data.get("country"))
    if has("description"):
        out["description"] = dc.clean_str(data.get("description"))
    if has("employee_count"):
        try:
            out["employee_count"] = dc.parse_int(data.get("employee_count"))
        except ValueError as e:
            errors["employee_count"] = str(e)
    if has("annual_revenue"):
        try:
            out["annual_revenue"] = dc.parse_decimal(data.get("annual_revenue"))
        except ValueError as e:
            errors["annual_revenue"] = str(e)
    if errors:
        raise ApiError("Please correct the highlighted company fields.", 422, errors)
    return out


def clean_contact_payload(data, partial=False):
    errors, out = {}, {}

    def has(f):
        return f in data

    if not partial or has("first_name"):
        first = dc.normalize_person_name(data.get("first_name"))
        if not first:
            errors["first_name"] = "First name is required."
        out["first_name"] = first
    if has("last_name"):
        out["last_name"] = dc.normalize_person_name(data.get("last_name"))
    if has("email"):
        email = dc.normalize_email(data.get("email"))
        if email and not dc.is_valid_email(email):
            errors["email"] = "Invalid email address."
        out["email"] = email
    if has("phone"):
        phone, ok = dc.normalize_phone(data.get("phone"), _default_cc())
        if not ok:
            errors["phone"] = "Invalid phone number (expected 8-15 digits)."
        out["phone"] = phone
    if has("job_title"):
        out["job_title"] = dc.clean_str(data.get("job_title"), 150)
    if has("lead_source"):
        out["lead_source"] = dc.normalize_lead_source(data.get("lead_source"))
    if has("lifecycle_stage") or not partial:
        raw = data.get("lifecycle_stage") or "lead"
        stage = dc.normalize_lifecycle(raw)
        if not stage:
            errors["lifecycle_stage"] = f"Lifecycle stage must be one of: {', '.join(LIFECYCLE_STAGES)}."
        out["lifecycle_stage"] = stage
    if has("lead_status"):
        status = (dc.clean_str(data.get("lead_status")) or "").lower()
        if status not in LEAD_STATUSES or status == "excluded":
            errors["lead_status"] = "Invalid lead status."
        out["lead_status"] = status
    if has("company_id"):
        cid = data.get("company_id")
        if cid in (None, "", 0, "0"):
            out["company_id"] = None
        else:
            try:
                out["company_id"] = int(cid)
            except (TypeError, ValueError):
                errors["company_id"] = "Invalid company."
    if errors:
        raise ApiError("Please correct the highlighted contact fields.", 422, errors)
    return out


def find_company_by_name(owner_id, name):
    key = dc.company_key(name)
    if not key:
        return None
    return Company.query.filter_by(owner_id=owner_id, name_key=key).first()


def create_company(owner_id, fields):
    key = dc.company_key(fields["company_name"])
    if Company.query.filter_by(owner_id=owner_id, name_key=key).first():
        raise ApiError(f"A company named '{fields['company_name']}' already exists.", 409)
    company = Company(owner_id=owner_id, name_key=key, **fields)
    db.session.add(company)
    db.session.flush()
    return company


def ensure_unique_email(owner_id, email, exclude_id=None):
    if not email:
        return
    q = Contact.query.filter_by(owner_id=owner_id, email=email)
    if exclude_id:
        q = q.filter(Contact.contact_id != exclude_id)
    other = q.first()
    if other:
        raise ApiError(f"Another contact ({other.full_name}) already uses {email}.", 409,
                       {"email": "Email already exists.", "existing_contact_id": other.contact_id})


def get_source(owner_id, name, source_type, description=None):
    src = DataSource.query.filter_by(owner_id=owner_id, source_name=name).first()
    if not src:
        src = DataSource(owner_id=owner_id, source_name=name, source_type=source_type, description=description)
        db.session.add(src)
        db.session.flush()
    return src


def link_source(contact, source):
    if source not in contact.sources:
        contact.sources.append(source)
