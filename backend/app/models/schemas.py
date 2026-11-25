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

    # Source record reference: CSV row number for pipeline runs (raw_lead_id covers the staged flow)
    source_row = Column(Integer, nullable=True)

    # AI classification (see app/services/classifier.py)
    persona = Column(String, nullable=True)
    buying_role = Column(String, nullable=True)
    interest = Column(String, nullable=True)
    classification_confidence = Column(Float, nullable=True)
    classification_engine = Column(String, nullable=True)
    recommended_action = Column(String, nullable=True)

    # HubSpot sync (see app/services/hubspot_sync.py)
    hubspot_synced_at = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReviewItem(Base):
    """Human review queue: borderline duplicate pairs and junk rows wait here for approve/reject."""
    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True, nullable=True)   # None = staged flow (Stages 1-4)
    item_type = Column(String, nullable=False)           # "merge" | "junk"
    status = Column(String, default="pending", index=True)  # pending | approved | rejected
    # Record references in the same id space as merged_leads_log (see id_type)
    id_type = Column(String, nullable=False)             # "raw_lead_id" | "csv_row"
    record_a_ref = Column(Integer, nullable=False)
    record_b_ref = Column(Integer, nullable=True)        # merge items only
    record_a = Column(Text, nullable=True)               # JSON snapshot for display
    record_b = Column(Text, nullable=True)
    similarity_score = Column(Float, nullable=True)
    reason = Column(String, nullable=True)
    resolution_note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

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


class HubSpotWorkflow(Base):
    """A HubSpot automation workflow imported from the Automation v4 API."""
    __tablename__ = "hubspot_workflows"

    id = Column(Integer, primary_key=True, index=True)
    hubspot_id = Column(String, unique=True, index=True, nullable=False)  # HubSpot's internal flow id
    name = Column(String, nullable=False)
    workflow_type = Column(String, nullable=True)      # e.g. CONTACT_DATE_CENTERED, CONTACT
    status = Column(String, nullable=True)             # ACTIVE, INACTIVE, DRAFT
    enrollment_trigger_summary = Column(Text, nullable=True)   # JSON: parsed trigger info
    actions_summary = Column(Text, nullable=True)              # JSON: list of parsed actions
    mapped = Column(Boolean, default=False)            # True if converted to scoring rules
    not_mapped_reason = Column(String, nullable=True)  # why it couldn't be mapped
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HubSpotScoringRule(Base):
    """A scoring rule derived from a HubSpot workflow action/trigger."""
    __tablename__ = "hubspot_scoring_rules"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String, index=True, nullable=False)  # → hubspot_workflows.hubspot_id
    rule_type = Column(String, nullable=False)         # "score_boost" | "score_penalty" | "routing"
    trigger_type = Column(String, nullable=True)       # "property_change" | "list_membership" | "form_submit" | etc.
    field_name = Column(String, nullable=True)         # HubSpot property name
    field_value = Column(String, nullable=True)        # matching value / operator
    score_delta = Column(Float, nullable=True)         # +/- points to apply
    routing_rep = Column(String, nullable=True)        # rep name for routing rules
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HubSpotSyncLog(Base):
    """Log of each sync attempt (import from HubSpot or push to HubSpot)."""
    __tablename__ = "hubspot_sync_log"

    id = Column(Integer, primary_key=True, index=True)
    direction = Column(String, nullable=False)         # "import" (pull from HS) | "push" (send to HS)
    status = Column(String, nullable=False)            # "ok" | "error"
    workflows_found = Column(Integer, nullable=True)
    workflows_mapped = Column(Integer, nullable=True)
    rules_created = Column(Integer, nullable=True)
    contacts_synced = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    triggered_by = Column(String, nullable=True)       # "manual" | "scheduled" | "webhook"
    synced_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemSetting(Base):
    """System-wide configuration settings (default country, scoring weights)."""
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)  # JSON or string representation
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
