from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base

class RawLead(Base):
    __tablename__ = "raw_leads"

    id = Column(Integer, primary_key=True, index=True)
    upload_batch_id = Column(String, index=True)
    run_id = Column(String, index=True, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(Integer, nullable=True)
    engagement_score = Column(Float, nullable=True)
    last_activity_date = Column(String, nullable=True)
    lead_source = Column(String, nullable=True)
    created_date = Column(String, nullable=True)
    extra_fields = Column(Text, nullable=True)  # JSON dictionary of unmapped columns
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CleanLead(Base):
    __tablename__ = "clean_leads"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True, nullable=True)
    raw_lead_id = Column(Integer, ForeignKey("raw_leads.id"), nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(Integer, nullable=True)
    engagement_score = Column(Float, nullable=True)
    last_activity_date = Column(String, nullable=True)
    lead_source = Column(String, nullable=True)
    created_date = Column(String, nullable=True)
    extra_fields = Column(Text, nullable=True)  # JSON dictionary of unmapped columns
    
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
    run_id = Column(String, index=True, nullable=True)
    # winner_lead_id: clean_leads.id of the kept record (0 when not known, e.g. bulk pipeline runs).
    winner_lead_id = Column(Integer, nullable=False)
    # winner_raw_lead_id / archived_raw_lead_id use the SAME id space, described by id_type:
    #   "raw_lead_id" -> raw_leads.id (legacy /api/leads/clean), "csv_row" -> row number in the uploaded file (pipeline)
    winner_raw_lead_id = Column(Integer, nullable=True)
    archived_raw_lead_id = Column(Integer, nullable=False)
    id_type = Column(String, nullable=True)
    archived_lead_name = Column(String, nullable=True)
    archived_company = Column(String, nullable=True)
    archived_email = Column(String, nullable=True)
    similarity_score = Column(Float, nullable=False)
    merge_reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CleaningLog(Base):
    __tablename__ = "cleaning_log"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True, nullable=True)
    row_index = Column(Integer, nullable=True)
    lead_id = Column(Integer, nullable=True)
    field_name = Column(String, nullable=False)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    stage = Column(String, default="init")       # parse, map, clean, dedupe, score, assign, completed
    progress_percent = Column(Integer, default=0)
    row_count_in = Column(Integer, default=0)
    row_count_out = Column(Integer, default=0)
    duplicates_merged = Column(Integer, default=0)
    junk_removed = Column(Integer, default=0)
    fields_fixed = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    column_mapping = Column(Text, nullable=True)    # JSON string of detected/applied mapping
    timings = Column(Text, nullable=True)           # JSON string of stage durations (ms)
    degraded_signals = Column(Text, nullable=True)  # JSON string of missing/re-normalized signals
    summary = Column(Text, nullable=True)           # JSON summary stats
    rejected_rows = Column(Text, nullable=True)     # JSON list of rejected row dicts with reasons
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
    run_id = Column(String, index=True, nullable=True)
    lead_id = Column(Integer, ForeignKey("clean_leads.id"))
    rep_id = Column(Integer, ForeignKey("reps.id"))
    rule_matched = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
