from app.extensions import db
from app.models.base import TimestampMixin, iso, utcnow

LIFECYCLE_STAGES = ("subscriber", "lead", "mql", "sql", "opportunity", "customer", "evangelist", "other")
# Lifecycle stages that count as "leads" (pre-customer pipeline).
LEAD_STAGES = ("subscriber", "lead", "mql", "sql", "opportunity")
LEAD_CATEGORIES = ("hot", "warm", "cold")
LEAD_STATUSES = ("new", "open", "in_progress", "qualified", "unqualified", "excluded")

# Many-to-many: which data sources (manual entry, seed data, CSV imports...) a contact came from.
contact_sources = db.Table(
    "contact_sources",
    db.Column("contact_id", db.Integer, db.ForeignKey("contacts.contact_id", ondelete="CASCADE"), primary_key=True),
    db.Column("source_id", db.Integer, db.ForeignKey("data_sources.source_id", ondelete="CASCADE"), primary_key=True),
    db.Column("linked_at", db.DateTime, nullable=False, default=utcnow),
)


class Contact(TimestampMixin, db.Model):
    __tablename__ = "contacts"

    contact_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(32), index=True)
    job_title = db.Column(db.String(150))
    company_id = db.Column(
        db.Integer, db.ForeignKey("companies.company_id", ondelete="SET NULL"), nullable=True, index=True
    )
    lifecycle_stage = db.Column(db.String(20), nullable=False, default="lead")
    lead_source = db.Column(db.String(100), index=True)
    lead_score = db.Column(db.Integer, nullable=False, default=0)
    # Automatically calculated category (NULL when the contact is excluded from qualification).
    lead_category = db.Column(db.String(10), index=True)
    # Manual override chosen by a user; the automatic category above is preserved.
    lead_category_override = db.Column(db.String(10))
    lead_status = db.Column(db.String(20), nullable=False, default="new")
    last_activity_at = db.Column(db.DateTime, index=True)

    company = db.relationship("Company", back_populates="contacts")
    activities = db.relationship(
        "LeadActivity", back_populates="contact", cascade="all, delete-orphan",
        passive_deletes=True, order_by="desc(LeadActivity.activity_date)", lazy="dynamic",
    )
    sources = db.relationship("DataSource", secondary=contact_sources, lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint("owner_id", "email", name="uq_contact_owner_email"),
        db.Index("ix_contacts_owner_name", "owner_id", "last_name", "first_name"),
        db.Index("ix_contacts_owner_category", "owner_id", "lead_category"),
        db.CheckConstraint("lead_score >= 0 AND lead_score <= 100", name="lead_score_range"),
        db.CheckConstraint(
            "lead_category IS NULL OR lead_category IN ('hot','warm','cold')", name="lead_category_valid"),
        db.CheckConstraint(
            "lead_category_override IS NULL OR lead_category_override IN ('hot','warm','cold')",
            name="lead_override_valid"),
    )

    EDITABLE_FIELDS = (
        "first_name", "last_name", "email", "phone", "job_title", "company_id",
        "lifecycle_stage", "lead_source", "lead_status",
    )

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    @property
    def effective_category(self):
        return self.lead_category_override or self.lead_category

    @property
    def is_lead(self):
        return self.lifecycle_stage in LEAD_STAGES

    def snapshot(self):
        data = {f: getattr(self, f) for f in self.EDITABLE_FIELDS}
        data.update({
            "lead_score": self.lead_score,
            "lead_category": self.lead_category,
            "lead_category_override": self.lead_category_override,
        })
        return data

    def to_dict(self, detail=False):
        data = {
            "contact_id": self.contact_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "job_title": self.job_title,
            "company_id": self.company_id,
            "company": {"company_id": self.company.company_id, "company_name": self.company.company_name}
            if self.company else None,
            "lifecycle_stage": self.lifecycle_stage,
            "is_lead": self.is_lead,
            "lead_source": self.lead_source,
            "lead_score": self.lead_score,
            "lead_category": self.effective_category,
            "lead_category_auto": self.lead_category,
            "lead_category_override": self.lead_category_override,
            "lead_status": self.lead_status,
            "last_activity_at": iso(self.last_activity_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "sources": [{"source_id": s.source_id, "source_name": s.source_name, "source_type": s.source_type}
                        for s in self.sources],
        }
        return data
