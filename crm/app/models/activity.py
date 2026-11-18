from app.extensions import db
from app.models.base import iso, utcnow


class LeadActivity(db.Model):
    __tablename__ = "lead_activities"

    activity_id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.contact_id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type = db.Column(db.String(40), nullable=False, index=True)
    activity_description = db.Column(db.Text)
    # Points applied by the scoring engine (kept in sync with the owner's scoring rules).
    activity_score = db.Column(db.Integer, nullable=False, default=0)
    activity_date = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    contact = db.relationship("Contact", back_populates="activities")

    __table_args__ = (
        db.Index("ix_activities_contact_date", "contact_id", "activity_date"),
    )

    def to_dict(self, label=None):
        return {
            "activity_id": self.activity_id,
            "contact_id": self.contact_id,
            "activity_type": self.activity_type,
            "activity_label": label or self.activity_type.replace("_", " ").capitalize(),
            "activity_description": self.activity_description,
            "activity_score": self.activity_score,
            "activity_date": iso(self.activity_date),
            "created_at": iso(self.created_at),
        }
