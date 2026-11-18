import re

from flask import Blueprint, jsonify
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User
from app.services import crm, lead_scoring
from app.services.data_cleaner import is_valid_email, normalize_email
from app.utils.api import ApiError, audit, json_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _validate_password(password):
    if not isinstance(password, str) or len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    if len(password) > 128:
        return "Password is too long."
    return None


def bootstrap_user(user):
    """Per-user defaults: scoring rules and the manual-entry data source."""
    lead_scoring.ensure_default_rules(user.user_id)
    crm.get_source(user.user_id, "Manual entry", "manual", "Records created by users in the CRM.")


@bp.post("/register")
def register():
    data = json_body()
    errors = {}
    full_name = (data.get("full_name") or "").strip()
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    if len(full_name) < 2:
        errors["full_name"] = "Please enter your full name."
    if not is_valid_email(email):
        errors["email"] = "Please enter a valid email address."
    pw_error = _validate_password(password)
    if pw_error:
        errors["password"] = pw_error
    if errors:
        raise ApiError("Please correct the highlighted fields.", 422, errors)
    if User.query.filter_by(email=email).first():
        raise ApiError("An account with this email already exists.", 409, {"email": "Email already registered."})
    role = "admin" if User.query.count() == 0 else "member"
    user = User(full_name=full_name[:120], email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    bootstrap_user(user)
    audit("user", user.user_id, "register", None, {"email": email}, user_id=user.user_id)
    db.session.commit()
    login_user(user)
    return jsonify(user=user.to_dict()), 201


@bp.post("/login")
def login():
    data = json_body()
    email = normalize_email(data.get("email"))
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first() if email else None
    if not user or not user.check_password(password):
        raise ApiError("Invalid email or password.", 401)
    login_user(user, remember=bool(data.get("remember")))
    # Time-based rules (30-day inactivity penalty) change scores without new events: refresh on login.
    lead_scoring.recalculate_owner(user.user_id)
    db.session.commit()
    return jsonify(user=user.to_dict())


@bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
    return jsonify(message="Logged out.")


@bp.get("/me")
@login_required
def me():
    return jsonify(user=current_user.to_dict())


@bp.put("/profile")
@login_required
def update_profile():
    data = json_body()
    errors = {}
    if "full_name" in data:
        name = (data.get("full_name") or "").strip()
        if len(name) < 2:
            errors["full_name"] = "Please enter your full name."
        else:
            current_user.full_name = name[:120]
    if data.get("new_password"):
        if not current_user.check_password(data.get("current_password") or ""):
            errors["current_password"] = "Current password is incorrect."
        else:
            pw_error = _validate_password(data["new_password"])
            if pw_error:
                errors["new_password"] = pw_error
            else:
                current_user.set_password(data["new_password"])
    if errors:
        db.session.rollback()
        raise ApiError("Please correct the highlighted fields.", 422, errors)
    audit("user", current_user.user_id, "update_profile", None, {"full_name": current_user.full_name})
    db.session.commit()
    return jsonify(user=current_user.to_dict())
