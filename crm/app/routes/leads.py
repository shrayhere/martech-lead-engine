from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import LEAD_CATEGORIES, LEAD_STAGES, Contact
from app.routes.contacts import contact_detail, contact_query
from app.services import analytics
from app.utils.api import ApiError, audit, get_int_arg, get_owned, json_body, paginate

bp = Blueprint("leads", __name__, url_prefix="/api/leads")


@bp.get("")
@login_required
def list_leads():
    q = contact_query(current_user.user_id, request.args, leads_only=True)
    return jsonify(paginate(q, lambda c: c.to_dict()))


@bp.get("/pipeline")
@login_required
def pipeline():
    """Kanban board: top leads per category (by score) plus full column counts."""
    limit = get_int_arg("limit", 30, 1, 100)
    columns = {}
    for cat in LEAD_CATEGORIES:
        args = dict(request.args)
        args["category"] = cat
        args.setdefault("sort", "score")
        q = contact_query(current_user.user_id, args, leads_only=True)
        total = q.order_by(None).count()
        columns[cat] = {"total": total, "items": [c.to_dict() for c in q.limit(limit).all()]}
    return jsonify(columns=columns)


@bp.get("/analytics")
@login_required
def lead_analytics():
    data = analytics.lead_analytics(current_user.user_id)
    data["distribution"] = analytics.charts(current_user.user_id)["lead_distribution"]
    return jsonify(data)


@bp.get("/<int:contact_id>")
@login_required
def get_lead(contact_id):
    contact = get_owned(Contact, contact_id)
    return jsonify(contact_detail(contact))


@bp.put("/<int:contact_id>/category")
@login_required
def set_category(contact_id):
    """Manually override the category. Send {"category": null} to return to the automatic category."""
    contact = get_owned(Contact, contact_id)
    data = json_body()
    category = data.get("category")
    if category is not None and category not in LEAD_CATEGORIES:
        raise ApiError("Category must be hot, warm, cold or null (automatic).", 400)
    if contact.lead_category is None and category is not None:
        raise ApiError("This contact is excluded from qualification because it has no valid email or phone. "
                       "Fix the contact details first.", 422)
    old = {"lead_category_override": contact.lead_category_override, "auto_category": contact.lead_category,
           "effective": contact.effective_category}
    contact.lead_category_override = None if category in (None, contact.lead_category) else category
    new = {"lead_category_override": contact.lead_category_override, "auto_category": contact.lead_category,
           "effective": contact.effective_category, "reason": (data.get("reason") or "")[:255] or None}
    if old["lead_category_override"] != contact.lead_category_override:
        audit("contact", contact.contact_id, "category_override", old, new)
    db.session.commit()
    return jsonify(contact=contact.to_dict())


@bp.get("/sources")
@login_required
def sources():
    rows = db.session.query(Contact.lead_source).filter(
        Contact.owner_id == current_user.user_id, Contact.lead_source.isnot(None)).distinct().order_by(
        Contact.lead_source).all()
    return jsonify(items=[r[0] for r in rows])
