from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models import DEFAULT_SCORING_RULES, ScoringRule
from app.services import lead_scoring
from app.utils.api import ApiError, audit, json_body

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@bp.get("/scoring-rules")
@login_required
def get_rules():
    lead_scoring.ensure_default_rules(current_user.user_id)
    db.session.commit()
    rules = ScoringRule.query.filter_by(owner_id=current_user.user_id).order_by(ScoringRule.points.desc()).all()
    return jsonify(rules=[r.to_dict() for r in rules],
                   bands={"hot": [lead_scoring.HOT_MIN, 100], "warm": [lead_scoring.WARM_MIN, lead_scoring.HOT_MIN - 1],
                          "cold": [0, lead_scoring.WARM_MIN - 1]})


@bp.put("/scoring-rules")
@login_required
def update_rules():
    data = json_body()
    updates = data.get("rules")
    if data.get("reset"):
        updates = [{"activity_type": k, "points": v[1]} for k, v in DEFAULT_SCORING_RULES.items()]
    if not isinstance(updates, list) or not updates:
        raise ApiError("Provide a list of rules.", 400)
    rules = {r.activity_type: r for r in ScoringRule.query.filter_by(owner_id=current_user.user_id)}
    old, new = {}, {}
    errors = {}
    for item in updates:
        t = item.get("activity_type")
        if t not in rules:
            errors[str(t)] = "Unknown activity type."
            continue
        try:
            points = int(item.get("points"))
        except (TypeError, ValueError):
            errors[t] = "Points must be a whole number."
            continue
        if not -100 <= points <= 100:
            errors[t] = "Points must be between -100 and 100."
            continue
        if rules[t].points != points:
            old[t], new[t] = rules[t].points, points
            rules[t].points = points
    if errors:
        db.session.rollback()
        raise ApiError("Some rules are invalid.", 422, errors)
    if new:
        lead_scoring.recalculate_owner(current_user.user_id)
        audit("scoring_rules", None, "update", old, new)
    db.session.commit()
    return jsonify(message=f"Saved. {len(new)} rule(s) changed; all lead scores were recalculated."
                   if new else "No changes.", changed=len(new))
