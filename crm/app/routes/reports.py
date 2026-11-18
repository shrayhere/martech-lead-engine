from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Company, Contact, ImportJob, LeadActivity
from app.models.base import iso
from app.services import analytics
from app.utils.api import csv_response, parse_date_arg

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/summary")
@login_required
def summary():
    start, end = analytics.resolve_range(request.args.get("range", "all"), parse_date_arg("start"),
                                         parse_date_arg("end", end_of_day=True))
    owner = current_user.user_id
    activity_rows = db.session.query(LeadActivity.activity_type, func.count(LeadActivity.activity_id),
                                     func.sum(LeadActivity.activity_score)).join(Contact).filter(
        Contact.owner_id == owner, analytics._in_range(LeadActivity.activity_date, start, end)).group_by(
        LeadActivity.activity_type).order_by(func.count(LeadActivity.activity_id).desc()).all()
    industries = db.session.query(func.coalesce(Company.industry, "Unspecified"), func.count(Contact.contact_id),
                                  func.avg(Contact.lead_score)).join(
        Contact, Contact.company_id == Company.company_id).filter(
        Company.owner_id == owner, analytics._in_range(Contact.created_at, start, end)).group_by(
        func.coalesce(Company.industry, "Unspecified")).order_by(func.count(Contact.contact_id).desc()).all()
    return jsonify(
        stats=analytics.stats(owner, start, end),
        charts=analytics.charts(owner, start, end),
        leads=analytics.lead_analytics(owner),
        activities=[{"activity_type": t, "count": n, "points": int(p or 0)} for t, n, p in activity_rows],
        industries=[{"industry": i, "contacts": n, "average_score": round(float(a or 0), 1)}
                    for i, n, a in industries],
    )


@bp.get("/imports.csv")
@login_required
def export_imports():
    jobs = ImportJob.query.filter_by(user_id=current_user.user_id).order_by(ImportJob.upload_timestamp.desc())
    header = ["import_id", "file", "uploaded_at", "mode", "status", "total", "inserted", "updated", "duplicates",
              "skipped", "failed", "duration_ms"]
    return csv_response("martech_imports.csv", header, (
        [j.import_id, j.original_filename, iso(j.upload_timestamp), j.sync_mode, j.import_status, j.total_rows,
         j.inserted_rows, j.updated_rows, j.duplicate_rows, j.skipped_rows, j.failed_rows, j.duration_ms]
        for j in jobs))


@bp.get("/activities.csv")
@login_required
def export_activities():
    q = (db.session.query(LeadActivity, Contact).join(Contact)
         .filter(Contact.owner_id == current_user.user_id).order_by(LeadActivity.activity_date.desc()))
    header = ["activity_id", "contact_id", "contact_name", "email", "activity_type", "description", "points",
              "activity_date"]
    return csv_response("martech_activities.csv", header, (
        [a.activity_id, c.contact_id, c.full_name, c.email, a.activity_type, a.activity_description,
         a.activity_score, iso(a.activity_date)] for a, c in q.yield_per(500)))
