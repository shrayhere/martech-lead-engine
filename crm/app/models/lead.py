"""Lead scoring configuration. Leads themselves are Contacts in a pre-customer lifecycle stage."""
from app.extensions import db
from app.models.base import TimestampMixin

INACTIVITY_RULE = "no_recent_engagement"
INACTIVITY_DAYS = 30

# activity_type -> (label, default points)
DEFAULT_SCORING_RULES = {
    "demo_requested": ("Requested product demo", 40),
    "pricing_inquiry": ("Asked for pricing", 30),
    "meeting_scheduled": ("Scheduled meeting", 30),
    "form_submitted": ("Submitted contact form", 20),
    "brochure_downloaded": ("Downloaded brochure", 15),
    "email_clicked": ("Clicked marketing email", 15),
    "email_opened": ("Opened marketing email", 5),
    "website_visit": ("Visited product page", 10),
    "other_engagement": ("Other engagement", 0),
    INACTIVITY_RULE: ("No activity for 30 days", -15),
}


class ScoringRule(TimestampMixin, db.Model):
    __tablename__ = "scoring_rules"

    rule_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type = db.Column(db.String(40), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("owner_id", "activity_type", name="uq_scoring_rule_owner_type"),
        db.CheckConstraint("points >= -100 AND points <= 100", name="points_range"),
    )

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "activity_type": self.activity_type,
            "label": self.label,
            "points": self.points,
            "default_points": DEFAULT_SCORING_RULES.get(self.activity_type, (None, None))[1],
        }
