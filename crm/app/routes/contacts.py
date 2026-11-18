import re

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.orm import contains_eager

from app.extensions import db
from app.models import (LEAD_CATEGORIES, LEAD_STAGES, LIFECYCLE_STAGES, AuditLog, Company, Contact, DataSource,
                        DuplicateRecord, LeadActivity)
from app.models.base import iso
from app.services import crm, lead_scoring
from app.services.data_cleaner import clean_str, parse_date
from app.utils.api import (ApiError, audit, csv_response, diff, get_int_arg, get_owned, json_body, paginate,
                           parse_date_arg)

bp = Blueprint("contacts", __name__, url_prefix="/api")

effective_category = func.coalesce(Contact.lead_category_override, Contact.lead_category)
SORTS = {
    "name": (Contact.first_name, Contact.last_name),
    "score": (Contact.lead_score,),
    "created": (Contact.created_at,),
    "last_activity": (Contact.last_activity_at,),
    "company": (Company.company_name,),
    "updated": (Contact.updated_at,),
}


def _like(value):
    escaped = value.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_condition(term):
    term = term.strip()
    pattern = _like(term)
    full = func.lower(Contact.first_name + " " + func.coalesce(Contact.last_name, ""))
    conds = [
        full.like(pattern, escape="\\"),
        func.lower(func.coalesce(Contact.last_name, "")).like(pattern, escape="\\"),
        func.lower(func.coalesce(Contact.email, "")).like(pattern, escape="\\"),
        func.lower(func.coalesce(Company.company_name, "")).like(pattern, escape="\\"),
        func.lower(func.coalesce(Contact.job_title, "")).like(pattern, escape="\\"),
    ]
    digits = re.sub(r"\D", "", term)
    if len(digits) >= 3:
        conds.append(Contact.phone.like(f"%{digits}%"))
    return or_(*conds)


def contact_query(owner_id, args, leads_only=False):
    q = (Contact.query.outerjoin(Company, Contact.company_id == Company.company_id)
         .options(contains_eager(Contact.company))
         .filter(Contact.owner_id == owner_id))
    if leads_only or args.get("leads_only") in ("1", "true"):
        q = q.filter(Contact.lifecycle_stage.in_(LEAD_STAGES))
    term = (args.get("q") or "").strip()
    if term:
        q = q.filter(search_condition(term))
    category = args.get("category")
    if category:
        if category == "excluded":
            q = q.filter(Contact.lead_category.is_(None))
        elif category in LEAD_CATEGORIES:
            q = q.filter(effective_category == category)
        else:
            raise ApiError("Unknown lead category.", 400)
    if args.get("overridden") in ("1", "true"):
        q = q.filter(Contact.lead_category_override.isnot(None))
    if args.get("company_id"):
        try:
            q = q.filter(Contact.company_id == int(args["company_id"]))
        except ValueError:
            raise ApiError("company_id must be a number.", 400)
    if args.get("no_company") in ("1", "true"):
        q = q.filter(Contact.company_id.is_(None))
    if args.get("lifecycle_stage"):
        q = q.filter(Contact.lifecycle_stage == args["lifecycle_stage"])
    if args.get("lead_status"):
        q = q.filter(Contact.lead_status == args["lead_status"])
    if args.get("lead_source"):
        q = q.filter(Contact.lead_source == args["lead_source"])
    if args.get("source_id"):
        q = q.filter(Contact.sources.any(DataSource.source_id == int(args["source_id"])))
    score_min = get_int_arg("score_min", None, 0, 100)
    score_max = get_int_arg("score_max", None, 0, 100)
    if score_min is not None:
        q = q.filter(Contact.lead_score >= score_min)
    if score_max is not None:
        q = q.filter(Contact.lead_score <= score_max)
    for arg, col, end in (("created_from", Contact.created_at, False), ("created_to", Contact.created_at, True),
                          ("activity_from", Contact.last_activity_at, False),
                          ("activity_to", Contact.last_activity_at, True)):
        value = parse_date_arg(arg, end_of_day=end)
        if value:
            q = q.filter(col >= value) if not end else q.filter(col <= value)
    if args.get("inactive_days"):
        from datetime import timedelta
        from app.models.base import utcnow
        days = get_int_arg("inactive_days", 30, 1, 3650)
        cutoff = utcnow() - timedelta(days=days)
        q = q.filter(or_(Contact.last_activity_at.is_(None), Contact.last_activity_at < cutoff))

    sort = args.get("sort", "created")
    if sort not in SORTS:
        raise ApiError("Unknown sort field.", 400)
    desc = args.get("order", "desc" if sort in ("score", "created", "last_activity", "updated") else "asc") == "desc"
    cols = SORTS[sort]
    order = []
    for c in cols:
        order.append(c.is_(None))  # NULLs last on both MySQL and SQLite
        order.append(c.desc() if desc else c.asc())
    order.append(Contact.contact_id.desc())
    return q.order_by(*order)


def _list_item(c):
    return c.to_dict()


@bp.get("/contacts")
@login_required
def list_contacts():
    q = contact_query(current_user.user_id, request.args)
    return jsonify(paginate(q, _list_item))


def _resolve_company_input(data):
    """Handle company_id or new_company in contact payloads."""
    new_company = data.get("new_company")
    if new_company:
        if not isinstance(new_company, dict):
            raise ApiError("new_company must be an object.", 400)
        fields = crm.clean_company_payload(new_company)
        existing = crm.find_company_by_name(current_user.user_id, fields["company_name"])
        if existing:
            return existing.company_id, False
        company = crm.create_company(current_user.user_id, fields)
        audit("company", company.company_id, "create", None, company.snapshot())
        return company.company_id, True
    return None, False


def _check_company(company_id):
    if company_id is not None:
        get_owned(Company, company_id)


@bp.post("/contacts")
@login_required
def create_contact():
    data = json_body()
    fields = crm.clean_contact_payload(data)
    crm.ensure_unique_email(current_user.user_id, fields.get("email"))
    company_id, _ = _resolve_company_input(data)
    if company_id is not None:
        fields["company_id"] = company_id
    _check_company(fields.get("company_id"))
    fields.setdefault("lead_status", "new")
    if not fields.get("lead_status"):
        fields["lead_status"] = "new"
    contact = Contact(owner_id=current_user.user_id, **fields)
    db.session.add(contact)
    db.session.flush()
    crm.link_source(contact, crm.get_source(current_user.user_id, "Manual entry", "manual"))
    lead_scoring.recalculate_contact(contact)
    audit("contact", contact.contact_id, "create", None, contact.snapshot())
    db.session.commit()
    return jsonify(contact=contact.to_dict()), 201


def contact_detail(contact):
    points, labels = lead_scoring.get_rules(contact.owner_id)
    activities = contact.activities.limit(100).all()
    recent_types = [a.activity_type for a in activities[:5]]
    history = AuditLog.query.filter_by(entity_type="contact", entity_id=contact.contact_id).order_by(
        AuditLog.timestamp.desc()).limit(25).all()
    pending_dups = DuplicateRecord.query.filter(
        DuplicateRecord.resolution_status == "pending",
        or_(DuplicateRecord.original_contact_id == contact.contact_id,
            DuplicateRecord.duplicate_contact_id == contact.contact_id)).count()
    return {
        "contact": contact.to_dict(),
        "company": contact.company.to_dict({"contact_count": contact.company.contacts.count()})
        if contact.company else None,
        "activities": [a.to_dict(labels.get(a.activity_type)) for a in activities],
        "activity_count": contact.activities.count(),
        "score_breakdown": lead_scoring.score_breakdown(contact),
        "recommended_next_action": lead_scoring.recommended_next_action(contact, recent_types),
        "is_qualifiable": contact.lead_category is not None,
        "history": [h.to_dict() for h in history],
        "pending_duplicates": pending_dups,
    }


@bp.get("/contacts/<int:contact_id>")
@login_required
def get_contact(contact_id):
    contact = get_owned(Contact, contact_id)
    return jsonify(contact_detail(contact))


@bp.put("/contacts/<int:contact_id>")
@login_required
def update_contact(contact_id):
    contact = get_owned(Contact, contact_id)
    data = json_body()
    fields = crm.clean_contact_payload(data, partial=True)
    if "email" in fields:
        crm.ensure_unique_email(current_user.user_id, fields["email"], exclude_id=contact.contact_id)
    company_id, _ = _resolve_company_input(data)
    if company_id is not None:
        fields["company_id"] = company_id
    if "company_id" in fields:
        _check_company(fields["company_id"])
    before = contact.snapshot()
    for key, value in fields.items():
        setattr(contact, key, value)
    if "company_id" in fields:
        db.session.flush()
        db.session.expire(contact, ["company"])
    lead_scoring.recalculate_contact(contact)
    old, new = diff(before, contact.snapshot())
    if new:
        audit("contact", contact.contact_id, "update", old, new)
    db.session.commit()
    return jsonify(contact=contact.to_dict())


@bp.delete("/contacts/<int:contact_id>")
@login_required
def delete_contact(contact_id):
    contact = get_owned(Contact, contact_id)
    snap = contact.snapshot()
    db.session.delete(contact)
    audit("contact", contact_id, "delete", snap, None)
    db.session.commit()
    return jsonify(message="Contact deleted.", contact_id=contact_id)


@bp.post("/contacts/bulk")
@login_required
def bulk_contacts():
    data = json_body()
    ids = data.get("ids") or []
    action = data.get("action")
    value = data.get("value")
    if not isinstance(ids, list) or not ids or len(ids) > 1000:
        raise ApiError("Select between 1 and 1000 contacts.", 400)
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        raise ApiError("Contact ids must be numbers.", 400)
    contacts = Contact.query.filter(Contact.owner_id == current_user.user_id, Contact.contact_id.in_(ids)).all()
    if len(contacts) != len(set(ids)):
        raise ApiError("Some selected contacts were not found.", 404)
    if action == "set_category":
        if value not in LEAD_CATEGORIES:
            raise ApiError("Category must be hot, warm or cold.", 400)
        for c in contacts:
            if c.lead_category is None:
                continue
            old = c.lead_category_override
            c.lead_category_override = None if value == c.lead_category else value
            if old != c.lead_category_override:
                audit("contact", c.contact_id, "category_override",
                      {"lead_category_override": old, "auto": c.lead_category},
                      {"lead_category_override": c.lead_category_override, "auto": c.lead_category})
    elif action == "clear_override":
        for c in contacts:
            if c.lead_category_override:
                audit("contact", c.contact_id, "category_override",
                      {"lead_category_override": c.lead_category_override}, {"lead_category_override": None})
                c.lead_category_override = None
    elif action == "set_lifecycle":
        if value not in LIFECYCLE_STAGES:
            raise ApiError("Unknown lifecycle stage.", 400)
        for c in contacts:
            if c.lifecycle_stage != value:
                audit("contact", c.contact_id, "update", {"lifecycle_stage": c.lifecycle_stage},
                      {"lifecycle_stage": value})
                c.lifecycle_stage = value
    elif action == "delete":
        for c in contacts:
            audit("contact", c.contact_id, "delete", c.snapshot(), None)
            db.session.delete(c)
    else:
        raise ApiError("Unknown bulk action.", 400)
    db.session.commit()
    return jsonify(message=f"Updated {len(contacts)} contact(s).", count=len(contacts))


@bp.get("/contacts/export")
@login_required
def export_contacts():
    q = contact_query(current_user.user_id, request.args)
    header = ["contact_id", "first_name", "last_name", "email", "phone", "job_title", "company", "industry",
              "lifecycle_stage", "lead_source", "lead_score", "lead_category", "auto_category", "lead_status",
              "last_activity_at", "created_at"]

    def rows():
        for c in q.yield_per(500):
            yield [c.contact_id, c.first_name, c.last_name, c.email, c.phone, c.job_title,
                   c.company.company_name if c.company else None, c.company.industry if c.company else None,
                   c.lifecycle_stage, c.lead_source, c.lead_score, c.effective_category or "excluded",
                   c.lead_category, c.lead_status, iso(c.last_activity_at), iso(c.created_at)]
    return csv_response("martech_contacts.csv", header, rows())


# ---------------------------------------------------------------- activities

def _clean_activity(data, partial=False):
    points, labels = lead_scoring.get_rules(current_user.user_id)
    out, errors = {}, {}
    if not partial or "activity_type" in data:
        t = (data.get("activity_type") or "").strip()
        if t not in points:
            errors["activity_type"] = "Choose a valid activity type."
        out["activity_type"] = t
    if not partial or "activity_date" in data:
        raw = data.get("activity_date")
        if raw:
            try:
                out["activity_date"] = parse_date(raw)
            except ValueError:
                errors["activity_date"] = "Invalid date."
        elif not partial:
            from app.models.base import utcnow
            out["activity_date"] = utcnow()
    if "activity_description" in data:
        out["activity_description"] = clean_str(data.get("activity_description"))
    if errors:
        raise ApiError("Please correct the activity fields.", 422, errors)
    return out


@bp.post("/contacts/<int:contact_id>/activities")
@login_required
def add_activity(contact_id):
    contact = get_owned(Contact, contact_id)
    fields = _clean_activity(json_body())
    activity = LeadActivity(contact_id=contact.contact_id, **fields)
    db.session.add(activity)
    before = {"lead_score": contact.lead_score, "lead_category": contact.lead_category}
    lead_scoring.recalculate_contact(contact)
    audit("activity", activity.activity_id, "create", None, {"contact_id": contact_id, **fields})
    if before["lead_score"] != contact.lead_score or before["lead_category"] != contact.lead_category:
        audit("contact", contact_id, "rescore", before,
              {"lead_score": contact.lead_score, "lead_category": contact.lead_category})
    db.session.commit()
    return jsonify(activity=activity.to_dict(), contact=contact.to_dict()), 201


def _owned_activity(activity_id):
    activity = db.session.get(LeadActivity, activity_id)
    if not activity or activity.contact.owner_id != current_user.user_id:
        raise ApiError("Activity not found.", 404)
    return activity


@bp.put("/activities/<int:activity_id>")
@login_required
def update_activity(activity_id):
    activity = _owned_activity(activity_id)
    fields = _clean_activity(json_body(), partial=True)
    before = activity.to_dict()
    for k, v in fields.items():
        setattr(activity, k, v)
    lead_scoring.recalculate_contact(activity.contact)
    audit("activity", activity_id, "update", before, activity.to_dict())
    db.session.commit()
    return jsonify(activity=activity.to_dict(), contact=activity.contact.to_dict())


@bp.delete("/activities/<int:activity_id>")
@login_required
def delete_activity(activity_id):
    activity = _owned_activity(activity_id)
    contact = activity.contact
    snap = activity.to_dict()
    db.session.delete(activity)
    db.session.flush()
    lead_scoring.recalculate_contact(contact)
    audit("activity", activity_id, "delete", snap, None)
    db.session.commit()
    return jsonify(message="Activity deleted.", contact=contact.to_dict())
