from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base

class RawLead(Base):
    __tablename__ = "raw_leads"

    id = Column(Integer, primary_key=True, index=True)
    upload_batch_id = Column(String, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    state = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(Integer, nullable=True)
    engagement_score = Column(Float, nullable=True)
    last_activity_date = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CleanLead(Base):
    __tablename__ = "clean_leads"

    id = Column(Integer, primary_key=True, index=True)
    raw_lead_id = Column(Integer, ForeignKey("raw_leads.id"), nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    state = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(Integer, nullable=True)
    engagement_score = Column(Float, nullable=True)
    last_activity_date = Column(String, nullable=True)
    
    is_junk = Column(Boolean, default=False)
    junk_reason = Column(String, nullable=True)
    duplicate_cluster_id = Column(String, nullable=True)
    
    rule_score = Column(Float, nullable=True)
    ml_score = Column(Float, nullable=True)
    active_score = Column(Float, nullable=True)
    score_band = Column(String, nullable=True) # Hot, Warm, Cold
    score_breakdown = Column(Text, nullable=True) # JSON stored signal scores
    
    assigned_rep_id = Column(Integer, ForeignKey("reps.id"), nullable=True)
    assignment_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MergedLeadLog(Base):
    __tablename__ = "merged_leads_log"

    id = Column(Integer, primary_key=True, index=True)
    winner_lead_id = Column(Integer, nullable=False)
    archived_raw_lead_id = Column(Integer, nullable=False)
    archived_lead_name = Column(String, nullable=True)
    archived_company = Column(String, nullable=True)
    archived_email = Column(String, nullable=True)
    similarity_score = Column(Float, nullable=False)
    merge_reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Rep(Base):
    __tablename__ = "reps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    territory = Column(String, nullable=False) # State or Region e.g. "CA, NY, WA" or "West"
    industry_specialty = Column(String, nullable=False) # e.g. "SaaS", "Healthcare"
    assigned_lead_count = Column(Integer, default=0)

class AssignmentLog(Base):
    __tablename__ = "assignment_log"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("clean_leads.id"))
    rep_id = Column(Integer, ForeignKey("reps.id"))
    rule_matched = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
