from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    """Naive UTC timestamp (stored without tzinfo for MySQL/SQLite portability)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


def iso(dt):
    return dt.isoformat() + "Z" if dt else None
