from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import case, func, or_

from app.extensions import db
from app.models import LEAD_STAGES, Company, Contact
from app.models.base import iso
from app.routes.contacts import _like
from app.services import crm
from app.services.data_cleaner import company_key
from app.utils.api import ApiError, audit, csv_response, diff, get_owned, json_body, paginate

bp = Blueprint("companies", __name__, url_prefix="/api")

effective_category = func.coalesce(Contact.lead_category_override, Contact.lead_category)
is_lead = Contact.lifecycle_stage.in_(LEAD_STAGES)


def _counts_subquery():
    return (db.session.query(
        Contact.company_id.label("company_id"),
        func.count(Contact.contact_id).label("contact_count"),
        func.sum(case((is_lead, 1), else_=0)).label("lead_count"),
        func.sum(case(((effective_category == "hot") & is_lead, 1), else_=0)).label("hot"),
        func.sum(case(((effective_category == "warm") & is_lead, 1), else_=0)).label("warm"),
        func.sum(case(((effective_category == "cold") & is_lead, 1), else_=0)).label("cold"),
        func.max(Contact.last_activity_at).label("last_activity_at"),
    ).filter(Contact.owner_id == current_user.user_id, Contact.company_id.isnot(None))
        .group_by(Contact.company_id).subquery())


SORTS = {"name": Company.company_name, "created": Company.created_at, "industry": Company.industry}


def company_query(args):
    counts = _counts_subquery()
    q = (db.session.query(Company, counts.c.contact_count, counts.c.lead_count, counts.c.hot, counts.c.warm,
                          counts.c.cold, counts.c.last_activity_at)
         .outerjoin(counts, counts.c.company_id == Company.company_id)
         .filter(Company.owner_id == current_user.user_id))
    term = (args.get("q") or "").strip()
    if term:
        p = _like(term)
        q = q.filter(or_(func.lower(Company.company_name).like(p, escape="\\"),
                         func.lower(func.coalesce(Company.website, "")).like(p, escape="\\"),
                         func.lower(func.coalesce(Company.city, "")).like(p, escape="\\")))
    if args.get("industry"):
        q = q.filter(Company.industry == args["industry"])
    if args.get("country"):
        q = q.filter(Company.country == args["country"])
    if args.get("has_contacts") == "0":
        q = q.filter(counts.c.contact_count.is_(None))
    elif args.get("has_contacts") == "1":
        q = q.filter(counts.c.contact_count > 0)
    sort = args.get("sort", "name")
    if sort == "contacts":
        col = func.coalesce(counts.c.contact_count, 0)
    elif sort == "hot":
        col = func.coalesce(counts.c.hot, 0)
    elif sort in SORTS:
        col = SORTS[sort]
    else:
        raise ApiError("Unknown sort field.", 400)
    desc = args.get("order", "asc" if sort in ("name", "industry") else "desc") == "desc"
    return q.order_by(col.desc() if desc else col.asc(), Company.company_id.desc())


def _row(row):
    company, contacts, leads, hot, warm, cold, last = row
    return company.to_dict({
        "contact_count": int(contacts or 0), "lead_count": int(leads or 0),
        "distribution": {"hot": int(hot or 0), "warm": int(warm or 0), "cold": int(cold or 0)},
        "last_activity_at": iso(last) if hasattr(last, "isoformat") else last,
    })


@bp.get("/companies")
@login_required
def list_companies():
    return jsonify(paginate(company_query(request.args), _row))


@bp.get("/companies/options")
@login_required
def company_options():
    """Lightweight searchable list for dropdowns (max 20 results)."""
    term = (request.args.get("q") or "").strip()
    q = Company.query.filter_by(owner_id=current_user.user_id)
    if term:
        q = q.filter(func.lower(Company.company_name).like(_like(term), escape="\\"))
    items = q.order_by(Company.company_name).limit(20).all()
    return jsonify(items=[{"company_id": c.company_id, "company_name": c.company_name, "industry": c.industry}
                          for c in items])


@bp.post("/companies")
@login_required
def create_company():
    fields = crm.clean_company_payload(json_body())
    company = crm.create_company(current_user.user_id, fields)
    audit("company", company.company_id, "create", None, company.snapshot())
    db.session.commit()
    return jsonify(company=company.to_dict({"contact_count": 0})), 201


@bp.get("/companies/<int:company_id>")
@login_required
def get_company(company_id):
    company = get_owned(Company, company_id)
    row = company_query({}).filter(Company.company_id == company_id).first()
    contacts = (Contact.query.filter_by(company_id=company_id, owner_id=current_user.user_id)
                .order_by(Contact.lead_score.desc(), Contact.first_name).limit(200).all())
    return jsonify(company=_row(row), contacts=[c.to_dict() for c in contacts])


@bp.put("/companies/<int:company_id>")
@login_required
def update_company(company_id):
    company = get_owned(Company, company_id)
    fields = crm.clean_company_payload(json_body(), partial=True)
    if "company_name" in fields:
        key = company_key(fields["company_name"])
        clash = Company.query.filter(Company.owner_id == current_user.user_id, Company.name_key == key,
                                     Company.company_id != company_id).first()
        if clash:
            raise ApiError(f"Another company named '{clash.company_name}' already exists.", 409)
        company.name_key = key
    before = company.snapshot()
    for k, v in fields.items():
        setattr(company, k, v)
    old, new = diff(before, company.snapshot())
    if new:
        audit("company", company_id, "update", old, new)
    db.session.commit()
    return jsonify(company=company.to_dict())


@bp.delete("/companies/<int:company_id>")
@login_required
def delete_company(company_id):
    company = get_owned(Company, company_id)
    detached = company.contacts.count()
    snap = company.snapshot()
    db.session.delete(company)  # contacts.company_id -> NULL (ON DELETE SET NULL)
    audit("company", company_id, "delete", snap, {"contacts_unassigned": detached})
    db.session.commit()
    return jsonify(message="Company deleted.", contacts_unassigned=detached)


@bp.get("/companies/export")
@login_required
def export_companies():
    q = company_query(request.args)
    header = ["company_id", "company_name", "industry", "website", "company_email", "phone", "address", "city",
              "country", "employee_count", "annual_revenue", "contacts", "leads", "hot", "warm", "cold",
              "created_at"]

    def rows():
        for company, contacts, leads, hot, warm, cold, _ in q.yield_per(500):
            yield [company.company_id, company.company_name, company.industry, company.website,
                   company.company_email, company.phone, company.address, company.city, company.country,
                   company.employee_count, company.annual_revenue, contacts or 0, leads or 0, hot or 0, warm or 0,
                   cold or 0, iso(company.created_at)]
    return csv_response("martech_companies.csv", header, rows())


@bp.get("/companies/facets")
@login_required
def company_facets():
    industries = [r[0] for r in db.session.query(Company.industry).filter(
        Company.owner_id == current_user.user_id, Company.industry.isnot(None)).distinct().order_by(Company.industry)]
    countries = [r[0] for r in db.session.query(Company.country).filter(
        Company.owner_id == current_user.user_id, Company.country.isnot(None)).distinct().order_by(Company.country)]
    return jsonify(industries=industries, countries=countries)
