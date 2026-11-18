import json

from app.extensions import db
from app.models.base import iso, utcnow


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    audit_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(db.Integer)
    operation = db.Column(db.String(40), nullable=False)
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    __table_args__ = (
        db.Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    def to_dict(self):
        return {
            "audit_id": self.audit_id,
            "user_id": self.user_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "operation": self.operation,
            "old_values": json.loads(self.old_values) if self.old_values else None,
            "new_values": json.loads(self.new_values) if self.new_values else None,
            "timestamp": iso(self.timestamp),
        }


class DuplicateRecord(db.Model):
    __tablename__ = "duplicate_records"

    duplicate_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.contact_id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Set when two stored contacts look alike; NULL when the duplicate is an incoming CSV row
    # (or after the duplicate contact was merged away — its data is then kept in incoming_data).
    duplicate_contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.contact_id", ondelete="SET NULL"), nullable=True, index=True
    )
    import_id = db.Column(
        db.Integer, db.ForeignKey("csv_import_jobs.import_id", ondelete="SET NULL"), nullable=True, index=True
    )
    incoming_data = db.Column(db.Text)  # JSON of the cleaned incoming record
    matching_reason = db.Column(db.String(255), nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    resolution_status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    detected_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    original_contact = db.relationship("Contact", foreign_keys=[original_contact_id])
    duplicate_contact = db.relationship("Contact", foreign_keys=[duplicate_contact_id])

    __table_args__ = (
        db.CheckConstraint(
            "resolution_status IN ('pending','kept_existing','updated_existing','merged','not_duplicate')",
            name="resolution_status_valid"),
        db.CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="confidence_range"),
    )

    @property
    def incoming(self):
        return json.loads(self.incoming_data) if self.incoming_data else None

    def to_dict(self):
        return {
            "duplicate_id": self.duplicate_id,
            "original_contact_id": self.original_contact_id,
            "duplicate_contact_id": self.duplicate_contact_id,
            "import_id": self.import_id,
            "matching_reason": self.matching_reason,
            "confidence_score": self.confidence_score,
            "resolution_status": self.resolution_status,
            "detected_at": iso(self.detected_at),
            "resolved_at": iso(self.resolved_at),
        }
