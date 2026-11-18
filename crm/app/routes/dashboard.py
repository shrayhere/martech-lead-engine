from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.models import Contact, ImportJob
from app.services import analytics
from app.utils.api import parse_date_arg

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _range():
    return analytics.resolve_range(request.args.get("range", "all"),
                                   parse_date_arg("start"), parse_date_arg("end", end_of_day=True))


@bp.get("/stats")
@login_required
def stats():
    start, end = _range()
    return jsonify(stats=analytics.stats(current_user.user_id, start, end),
                   range={"start": start.isoformat() if start else None, "end": end.isoformat() if end else None})


@bp.get("/charts")
@login_required
def charts():
    start, end = _range()
    return jsonify(analytics.charts(current_user.user_id, start, end))


@bp.get("/recent")
@login_required
def recent():
    hot = (Contact.query.filter(Contact.owner_id == current_user.user_id,
                                Contact.lead_category.isnot(None))
           .order_by(Contact.lead_score.desc(), Contact.last_activity_at.desc()).limit(6).all())
    newest = (Contact.query.filter_by(owner_id=current_user.user_id)
              .order_by(Contact.created_at.desc()).limit(6).all())
    imports = (ImportJob.query.filter_by(user_id=current_user.user_id)
               .order_by(ImportJob.upload_timestamp.desc()).limit(5).all())
    return jsonify(top_leads=[c.to_dict() for c in hot], newest_contacts=[c.to_dict() for c in newest],
                   recent_imports=[j.to_dict() for j in imports])
