from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from app.extensions import db
from app.models import AuditLog, Company, Contact, DataSource, DuplicateRecord, ImportJob, LEAD_STAGES
from app.models.base import iso, utcnow
from app.routes.contacts import _like, search_condition
from app.services import duplicate_detector
from app.utils.api import ApiError, get_owned, json_body, paginate

bp = Blueprint("data", __name__, url_prefix="/api")


# ---------------------------------------------------------------- duplicates

@bp.get("/duplicates")
@login_required
def list_duplicates():
    status = request.args.get("status", "pending")
    q = DuplicateRecord.query.filter_by(owner_id=current_user.user_id)
    if status != "all":
        q = q.filter(DuplicateRecord.resolution_status == status)
    if request.args.get("import_id"):
        q = q.filter(DuplicateRecord.import_id == int(request.args["import_id"]))
    q = q.order_by(DuplicateRecord.confidence_score.desc(), DuplicateRecord.detected_at.desc())
    return jsonify(paginate(q, duplicate_detector.serialize, default_per_page=10))


@bp.post("/duplicates/scan")
@login_required
def scan_duplicates():
    created = duplicate_detector.scan_existing(current_user.user_id)
    db.session.commit()
    return jsonify(message=f"Scan complete: {created} new possible duplicate(s) found.", created=created)


@bp.post("/duplicates/<int:duplicate_id>/resolve")
@login_required
def resolve_duplicate(duplicate_id):
    dup = get_owned(DuplicateRecord, duplicate_id)
    action = json_body().get("action")
    result = duplicate_detector.resolve(dup, action, current_user.user_id)
    db.session.commit()
    return jsonify(result=result, duplicate=dup.to_dict())


@bp.get("/duplicates/export")
@login_required
def export_duplicates():
    from app.utils.api import csv_response
    q = DuplicateRecord.query.filter_by(owner_id=current_user.user_id).order_by(DuplicateRecord.detected_at.desc())
    header = ["duplicate_id", "status", "reason", "confidence", "existing_contact_id", "existing_name",
              "existing_email", "incoming_name", "incoming_email", "incoming_phone", "import_id", "detected_at"]

    def rows():
        for d in q:
            inc, _, _ = duplicate_detector._incoming_fields(d)
            yield [d.duplicate_id, d.resolution_status, d.matching_reason, d.confidence_score,
                   d.original_contact_id, d.original_contact.full_name, d.original_contact.email,
                   " ".join(p for p in (inc.get("first_name"), inc.get("last_name")) if p), inc.get("email"),
                   inc.get("phone"), d.import_id, iso(d.detected_at)]
    return csv_response("martech_duplicates.csv", header, rows())


# ---------------------------------------------------------------- data quality

@bp.get("/data-quality")
@login_required
def data_quality():
    owner = Contact.owner_id == current_user.user_id
    total = Contact.query.filter(owner).count()
    cutoff = utcnow() - timedelta(days=30)

    def count(*conds):
        return Contact.query.filter(owner, *conds).count()

    checks = [
        {"key": "no_company", "label": "Contacts without a company", "count": count(Contact.company_id.is_(None)),
         "link": "/contacts?no_company=1"},
        {"key": "excluded", "label": "Excluded: no valid email or phone", "count": count(Contact.lead_category.is_(None)),
         "link": "/contacts?category=excluded"},
        {"key": "no_email", "label": "Contacts missing an email", "count": count(Contact.email.is_(None)),
         "link": None},
        {"key": "no_phone", "label": "Contacts missing a phone number", "count": count(Contact.phone.is_(None)),
         "link": None},
        {"key": "inactive", "label": "Leads with no activity in 30 days",
         "count": count(Contact.lifecycle_stage.in_(LEAD_STAGES),
                        or_(Contact.last_activity_at.is_(None), Contact.last_activity_at < cutoff)),
         "link": "/contacts?inactive_days=30"},
        {"key": "overridden", "label": "Leads with a manual category override",
         "count": count(Contact.lead_category_override.isnot(None)), "link": "/leads?overridden=1"},
    ]
    empty_companies = db.session.query(func.count(Company.company_id)).filter(
        Company.owner_id == current_user.user_id,
        ~Company.contacts.any()).scalar()
    checks.append({"key": "empty_companies", "label": "Companies with no contacts", "count": empty_companies,
                   "link": "/companies?has_contacts=0"})
    pending = DuplicateRecord.query.filter_by(owner_id=current_user.user_id, resolution_status="pending").count()
    filled = db.session.query(
        func.count(Contact.email), func.count(Contact.phone), func.count(Contact.company_id),
        func.count(Contact.job_title), func.count(Contact.lead_source)).filter(owner).one()
    completeness = {k: (round(v / total * 100, 1) if total else 0)
                    for k, v in zip(("email", "phone", "company", "job_title", "lead_source"), filled)}
    from app.models import contact_sources
    src_rows = db.session.query(DataSource, func.count(contact_sources.c.contact_id)).outerjoin(
        contact_sources, contact_sources.c.source_id == DataSource.source_id).filter(
        DataSource.owner_id == current_user.user_id).group_by(DataSource.source_id).order_by(DataSource.source_name).all()
    return jsonify(total_contacts=total, checks=checks, pending_duplicates=pending, completeness=completeness,
                   sources=[{**s.to_dict(), "contacts": n} for s, n in src_rows])


# ---------------------------------------------------------------- global search

@bp.get("/search")
@login_required
def global_search():
    term = (request.args.get("q") or "").strip()
    if len(term) < 2:
        return jsonify(contacts=[], companies=[], leads=[])
    contacts = (Contact.query.outerjoin(Company, Contact.company_id == Company.company_id)
                .filter(Contact.owner_id == current_user.user_id, search_condition(term))
                .order_by(Contact.lead_score.desc()).limit(6).all())
    companies = (Company.query.filter(Company.owner_id == current_user.user_id,
                                      or_(func.lower(Company.company_name).like(_like(term), escape="\\"),
                                          func.lower(func.coalesce(Company.website, "")).like(_like(term), escape="\\")))
                 .order_by(Company.company_name).limit(5).all())
    leads = [c for c in contacts if c.is_lead and c.effective_category]
    return jsonify(
        contacts=[{"contact_id": c.contact_id, "name": c.full_name, "email": c.email, "phone": c.phone,
                   "company": c.company.company_name if c.company else None} for c in contacts],
        companies=[{"company_id": c.company_id, "company_name": c.company_name, "industry": c.industry}
                   for c in companies],
        leads=[{"contact_id": c.contact_id, "name": c.full_name, "category": c.effective_category,
                "score": c.lead_score} for c in leads],
    )


# ---------------------------------------------------------------- notifications

@bp.get("/notifications")
@login_required
def notifications():
    since = utcnow() - timedelta(days=14)
    items = []
    for job in ImportJob.query.filter(ImportJob.user_id == current_user.user_id,
                                      ImportJob.completed_at.isnot(None),
                                      ImportJob.completed_at >= since).order_by(ImportJob.completed_at.desc()).limit(10):
        if job.import_status == "completed":
            items.append({"type": "import", "title": f"Import completed: {job.original_filename}",
                          "body": f"{job.inserted_rows} new, {job.updated_rows} updated, {job.failed_rows} failed, "
                                  f"{job.duplicate_rows} duplicates.",
                          "link": f"/imports?report={job.import_id}", "at": iso(job.completed_at)})
        else:
            items.append({"type": "error", "title": f"Import rolled back: {job.original_filename}",
                          "body": job.error_message or "", "link": f"/imports?report={job.import_id}",
                          "at": iso(job.completed_at)})
    pending_q = DuplicateRecord.query.filter_by(owner_id=current_user.user_id, resolution_status="pending")
    pending = pending_q.count()
    if pending:
        latest = db.session.query(func.max(DuplicateRecord.detected_at)).filter(
            DuplicateRecord.owner_id == current_user.user_id, DuplicateRecord.resolution_status == "pending").scalar()
        items.append({"type": "duplicates", "title": f"{pending} possible duplicate(s) need review",
                      "body": "Review them in Data Management.", "link": "/data", "at": iso(latest)})
    for log in AuditLog.query.filter(AuditLog.user_id == current_user.user_id, AuditLog.operation == "rescore",
                                     AuditLog.timestamp >= since).order_by(AuditLog.timestamp.desc()).limit(5):
        new = log.to_dict()["new_values"] or {}
        if new.get("lead_category") == "hot":
            items.append({"type": "hot", "title": "A lead became Hot", "body": f"Lead score is now {new.get('lead_score')}.",
                          "link": f"/contacts/{log.entity_id}", "at": iso(log.timestamp)})
    items.sort(key=lambda i: i["at"] or "", reverse=True)
    seen = current_user.notifications_seen_at
    unread = sum(1 for i in items if not seen or (i["at"] and i["at"] > iso(seen)))
    return jsonify(items=items[:15], unread=unread)


@bp.post("/notifications/read")
@login_required
def mark_read():
    current_user.notifications_seen_at = utcnow()
    db.session.commit()
    return jsonify(unread=0)


@bp.get("/activity-log")
@login_required
def activity_log():
    q = AuditLog.query.filter_by(user_id=current_user.user_id).order_by(AuditLog.timestamp.desc())
    if request.args.get("entity_type"):
        q = q.filter(AuditLog.entity_type == request.args["entity_type"])
    return jsonify(paginate(q, lambda a: a.to_dict(), default_per_page=20))
