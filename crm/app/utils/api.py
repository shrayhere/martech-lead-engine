"""Shared helpers for JSON API routes: errors, pagination, parsing and ownership checks."""
import csv
import io
import json
from datetime import datetime, timedelta

from flask import Response, abort, jsonify, request
from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


def error(message, status=400, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("Request body must be valid JSON.", 400)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.", 400)
    return data


def get_int_arg(name, default=None, minimum=None, maximum=None):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(f"Query parameter '{name}' must be an integer.", 400)
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def parse_date_arg(name, end_of_day=False):
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "")[:19])
    except ValueError:
        raise ApiError(f"Query parameter '{name}' must be a date (YYYY-MM-DD).", 400)
    if end_of_day and len(raw) <= 10:
        value = value + timedelta(days=1) - timedelta(microseconds=1)
    return value


def paginate(query, serializer, default_per_page=25):
    page = get_int_arg("page", 1, minimum=1)
    per_page = get_int_arg("per_page", default_per_page, minimum=1, maximum=100)
    total = query.order_by(None).count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "items": [serializer(i) for i in items],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }


def get_owned(model, pk, owner_attr="owner_id"):
    obj = db.session.get(model, pk)
    if obj is None or getattr(obj, owner_attr) != current_user.user_id:
        abort(404, description=f"{model.__name__} not found.")
    return obj


def audit(entity_type, entity_id, operation, old=None, new=None, user_id=None):
    entry = AuditLog(
        user_id=user_id if user_id is not None else (current_user.user_id if current_user.is_authenticated else None),
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        old_values=json.dumps(old, default=str) if old is not None else None,
        new_values=json.dumps(new, default=str) if new is not None else None,
    )
    db.session.add(entry)
    return entry


def diff(old, new):
    """Return ({field: old}, {field: new}) for changed fields only."""
    changed_old, changed_new = {}, {}
    for key, value in new.items():
        if old.get(key) != value:
            changed_old[key] = old.get(key)
            changed_new[key] = value
    return changed_old, changed_new


def csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
