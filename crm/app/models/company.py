from app.extensions import db
from app.models.base import TimestampMixin, iso


class Company(TimestampMixin, db.Model):
    __tablename__ = "companies"

    company_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_name = db.Column(db.String(200), nullable=False)
    # Normalised key ("acme" for "ACME Corp.", "Acme Corporation") used to prevent duplicate companies.
    name_key = db.Column(db.String(200), nullable=False)
    industry = db.Column(db.String(100), index=True)
    website = db.Column(db.String(255))
    company_email = db.Column(db.String(255))
    phone = db.Column(db.String(32))
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    employee_count = db.Column(db.Integer)
    annual_revenue = db.Column(db.Numeric(15, 2))
    description = db.Column(db.Text)

    contacts = db.relationship("Contact", back_populates="company", passive_deletes=True, lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("owner_id", "name_key", name="uq_company_owner_name_key"),
        db.Index("ix_companies_owner_name", "owner_id", "company_name"),
        db.CheckConstraint("employee_count IS NULL OR employee_count >= 0", name="employee_count_nonneg"),
        db.CheckConstraint("annual_revenue IS NULL OR annual_revenue >= 0", name="annual_revenue_nonneg"),
    )

    EDITABLE_FIELDS = (
        "company_name", "industry", "website", "company_email", "phone", "address",
        "city", "country", "employee_count", "annual_revenue", "description",
    )

    def to_dict(self, extra=None):
        data = {
            "company_id": self.company_id,
            "company_name": self.company_name,
            "industry": self.industry,
            "website": self.website,
            "company_email": self.company_email,
            "phone": self.phone,
            "address": self.address,
            "city": self.city,
            "country": self.country,
            "employee_count": self.employee_count,
            "annual_revenue": float(self.annual_revenue) if self.annual_revenue is not None else None,
            "description": self.description,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if extra:
            data.update(extra)
        return data

    def snapshot(self):
        return {f: (float(v) if f == "annual_revenue" and v is not None else v)
                for f in self.EDITABLE_FIELDS for v in [getattr(self, f)]}
