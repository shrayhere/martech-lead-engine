"""Server-rendered page shells. Each page loads its data from the JSON API with fetch()."""
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models import LEAD_STAGES, LIFECYCLE_STAGES, Company, Contact
from app.utils.api import get_owned

bp = Blueprint("pages", __name__)

NAV = [
    ("overview", "Overview", "/"),
    ("contacts", "Contacts", "/contacts"),
    ("companies", "Companies", "/companies"),
    ("leads", "Leads", "/leads"),
    ("data", "Data Management", "/data"),
    ("imports", "Import & Sync", "/imports"),
    ("reports", "Reports & Analytics", "/reports"),
    ("settings", "Settings", "/settings"),
]


@bp.app_context_processor
def inject_globals():
    return {"NAV": NAV, "LIFECYCLE_STAGES": LIFECYCLE_STAGES, "LEAD_STAGES": LEAD_STAGES}


def _page(template, active, **ctx):
    return render_template(template, active=active, **ctx)


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("pages.overview"))
    return render_template("auth/login.html")


@bp.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("pages.overview"))
    return render_template("auth/register.html")


@bp.get("/")
@login_required
def overview():
    return _page("overview.html", "overview")


@bp.get("/contacts")
@login_required
def contacts():
    return _page("contacts.html", "contacts")


@bp.get("/contacts/<int:contact_id>")
@login_required
def contact_detail(contact_id):
    contact = get_owned(Contact, contact_id)
    return _page("contact_detail.html", "contacts", contact_id=contact.contact_id, title=contact.full_name)


@bp.get("/companies")
@login_required
def companies():
    return _page("companies.html", "companies")


@bp.get("/companies/<int:company_id>")
@login_required
def company_detail(company_id):
    company = get_owned(Company, company_id)
    return _page("company_detail.html", "companies", company_id=company.company_id, title=company.company_name)


@bp.get("/leads")
@login_required
def leads():
    return _page("leads.html", "leads")


@bp.get("/data")
@login_required
def data_management():
    return _page("data.html", "data")


@bp.get("/imports")
@login_required
def imports():
    return _page("imports.html", "imports")


@bp.get("/reports")
@login_required
def reports():
    return _page("reports.html", "reports")


@bp.get("/settings")
@login_required
def settings():
    from app.extensions import db
    dialect = db.engine.dialect.name
    backend = {"mysql": "MySQL", "sqlite": "SQLite (local development fallback)"}.get(dialect, dialect)
    return _page("settings.html", "settings", db_backend=backend)
