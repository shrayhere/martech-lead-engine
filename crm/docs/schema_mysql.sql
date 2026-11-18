CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> ff0104bf2a60

CREATE TABLE users (
    user_id INTEGER NOT NULL AUTO_INCREMENT, 
    full_name VARCHAR(120) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    `role` VARCHAR(20) NOT NULL, 
    notifications_seen_at DATETIME, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (user_id), 
    CONSTRAINT ck_users_role_valid CHECK (role IN ('admin','member')), 
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX ix_users_created_at ON users (created_at);

CREATE TABLE audit_logs (
    audit_id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER, 
    entity_type VARCHAR(30) NOT NULL, 
    entity_id INTEGER, 
    operation VARCHAR(40) NOT NULL, 
    old_values TEXT, 
    new_values TEXT, 
    timestamp DATETIME NOT NULL, 
    CONSTRAINT pk_audit_logs PRIMARY KEY (audit_id), 
    CONSTRAINT fk_audit_logs_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_entity ON audit_logs (entity_type, entity_id);

CREATE INDEX ix_audit_logs_timestamp ON audit_logs (timestamp);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE companies (
    company_id INTEGER NOT NULL AUTO_INCREMENT, 
    owner_id INTEGER NOT NULL, 
    company_name VARCHAR(200) NOT NULL, 
    name_key VARCHAR(200) NOT NULL, 
    industry VARCHAR(100), 
    website VARCHAR(255), 
    company_email VARCHAR(255), 
    phone VARCHAR(32), 
    address VARCHAR(255), 
    city VARCHAR(100), 
    country VARCHAR(100), 
    employee_count INTEGER, 
    annual_revenue NUMERIC(15, 2), 
    description TEXT, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_companies PRIMARY KEY (company_id), 
    CONSTRAINT ck_companies_annual_revenue_nonneg CHECK (annual_revenue IS NULL OR annual_revenue >= 0), 
    CONSTRAINT ck_companies_employee_count_nonneg CHECK (employee_count IS NULL OR employee_count >= 0), 
    CONSTRAINT fk_companies_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (user_id) ON DELETE CASCADE, 
    CONSTRAINT uq_company_owner_name_key UNIQUE (owner_id, name_key)
);

CREATE INDEX ix_companies_created_at ON companies (created_at);

CREATE INDEX ix_companies_industry ON companies (industry);

CREATE INDEX ix_companies_owner_id ON companies (owner_id);

CREATE INDEX ix_companies_owner_name ON companies (owner_id, company_name);

CREATE TABLE csv_import_jobs (
    import_id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER NOT NULL, 
    original_filename VARCHAR(255) NOT NULL, 
    stored_filename VARCHAR(255) NOT NULL, 
    upload_timestamp DATETIME NOT NULL, 
    file_size INTEGER NOT NULL, 
    encoding VARCHAR(30), 
    delimiter VARCHAR(5), 
    total_rows INTEGER NOT NULL, 
    successful_rows INTEGER NOT NULL, 
    inserted_rows INTEGER NOT NULL, 
    updated_rows INTEGER NOT NULL, 
    failed_rows INTEGER NOT NULL, 
    duplicate_rows INTEGER NOT NULL, 
    skipped_rows INTEGER NOT NULL, 
    import_status VARCHAR(20) NOT NULL, 
    sync_mode VARCHAR(20), 
    column_mapping TEXT, 
    error_report_path VARCHAR(255), 
    duplicate_report_path VARCHAR(255), 
    success_report_path VARCHAR(255), 
    error_message TEXT, 
    started_at DATETIME, 
    completed_at DATETIME, 
    duration_ms INTEGER, 
    CONSTRAINT pk_csv_import_jobs PRIMARY KEY (import_id), 
    CONSTRAINT ck_csv_import_jobs_import_status_valid CHECK (import_status IN ('uploaded','previewed','processing','completed','failed','rolled_back')), 
    CONSTRAINT fk_csv_import_jobs_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE INDEX ix_csv_import_jobs_import_status ON csv_import_jobs (import_status);

CREATE INDEX ix_csv_import_jobs_upload_timestamp ON csv_import_jobs (upload_timestamp);

CREATE INDEX ix_csv_import_jobs_user_id ON csv_import_jobs (user_id);

CREATE TABLE data_sources (
    source_id INTEGER NOT NULL AUTO_INCREMENT, 
    owner_id INTEGER NOT NULL, 
    source_name VARCHAR(120) NOT NULL, 
    source_type VARCHAR(30) NOT NULL, 
    description TEXT, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_data_sources PRIMARY KEY (source_id), 
    CONSTRAINT fk_data_sources_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (user_id) ON DELETE CASCADE, 
    CONSTRAINT uq_data_source_owner_name UNIQUE (owner_id, source_name)
);

CREATE INDEX ix_data_sources_owner_id ON data_sources (owner_id);

CREATE TABLE scoring_rules (
    rule_id INTEGER NOT NULL AUTO_INCREMENT, 
    owner_id INTEGER NOT NULL, 
    activity_type VARCHAR(40) NOT NULL, 
    label VARCHAR(100) NOT NULL, 
    points INTEGER NOT NULL, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_scoring_rules PRIMARY KEY (rule_id), 
    CONSTRAINT ck_scoring_rules_points_range CHECK (points >= -100 AND points <= 100), 
    CONSTRAINT fk_scoring_rules_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (user_id) ON DELETE CASCADE, 
    CONSTRAINT uq_scoring_rule_owner_type UNIQUE (owner_id, activity_type)
);

CREATE INDEX ix_scoring_rules_created_at ON scoring_rules (created_at);

CREATE INDEX ix_scoring_rules_owner_id ON scoring_rules (owner_id);

CREATE TABLE contacts (
    contact_id INTEGER NOT NULL AUTO_INCREMENT, 
    owner_id INTEGER NOT NULL, 
    first_name VARCHAR(100) NOT NULL, 
    last_name VARCHAR(100), 
    email VARCHAR(255), 
    phone VARCHAR(32), 
    job_title VARCHAR(150), 
    company_id INTEGER, 
    lifecycle_stage VARCHAR(20) NOT NULL, 
    lead_source VARCHAR(100), 
    lead_score INTEGER NOT NULL, 
    lead_category VARCHAR(10), 
    lead_category_override VARCHAR(10), 
    lead_status VARCHAR(20) NOT NULL, 
    last_activity_at DATETIME, 
    created_at DATETIME NOT NULL, 
    updated_at DATETIME NOT NULL, 
    CONSTRAINT pk_contacts PRIMARY KEY (contact_id), 
    CONSTRAINT ck_contacts_lead_category_valid CHECK (lead_category IS NULL OR lead_category IN ('hot','warm','cold')), 
    CONSTRAINT ck_contacts_lead_override_valid CHECK (lead_category_override IS NULL OR lead_category_override IN ('hot','warm','cold')), 
    CONSTRAINT ck_contacts_lead_score_range CHECK (lead_score >= 0 AND lead_score <= 100), 
    CONSTRAINT fk_contacts_company_id_companies FOREIGN KEY(company_id) REFERENCES companies (company_id) ON DELETE SET NULL, 
    CONSTRAINT fk_contacts_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (user_id) ON DELETE CASCADE, 
    CONSTRAINT uq_contact_owner_email UNIQUE (owner_id, email)
);

CREATE INDEX ix_contacts_company_id ON contacts (company_id);

CREATE INDEX ix_contacts_created_at ON contacts (created_at);

CREATE INDEX ix_contacts_last_activity_at ON contacts (last_activity_at);

CREATE INDEX ix_contacts_lead_category ON contacts (lead_category);

CREATE INDEX ix_contacts_lead_source ON contacts (lead_source);

CREATE INDEX ix_contacts_owner_category ON contacts (owner_id, lead_category);

CREATE INDEX ix_contacts_owner_id ON contacts (owner_id);

CREATE INDEX ix_contacts_owner_name ON contacts (owner_id, last_name, first_name);

CREATE INDEX ix_contacts_phone ON contacts (phone);

CREATE TABLE sync_logs (
    sync_id INTEGER NOT NULL AUTO_INCREMENT, 
    import_id INTEGER NOT NULL, 
    source_id INTEGER, 
    sync_type VARCHAR(20) NOT NULL, 
    records_inserted INTEGER NOT NULL, 
    records_updated INTEGER NOT NULL, 
    records_skipped INTEGER NOT NULL, 
    records_failed INTEGER NOT NULL, 
    sync_status VARCHAR(20) NOT NULL, 
    started_at DATETIME NOT NULL, 
    completed_at DATETIME, 
    CONSTRAINT pk_sync_logs PRIMARY KEY (sync_id), 
    CONSTRAINT fk_sync_logs_import_id_csv_import_jobs FOREIGN KEY(import_id) REFERENCES csv_import_jobs (import_id) ON DELETE CASCADE, 
    CONSTRAINT fk_sync_logs_source_id_data_sources FOREIGN KEY(source_id) REFERENCES data_sources (source_id) ON DELETE SET NULL
);

CREATE INDEX ix_sync_logs_import_id ON sync_logs (import_id);

CREATE INDEX ix_sync_logs_source_id ON sync_logs (source_id);

CREATE TABLE contact_sources (
    contact_id INTEGER NOT NULL, 
    source_id INTEGER NOT NULL, 
    linked_at DATETIME NOT NULL, 
    CONSTRAINT pk_contact_sources PRIMARY KEY (contact_id, source_id), 
    CONSTRAINT fk_contact_sources_contact_id_contacts FOREIGN KEY(contact_id) REFERENCES contacts (contact_id) ON DELETE CASCADE, 
    CONSTRAINT fk_contact_sources_source_id_data_sources FOREIGN KEY(source_id) REFERENCES data_sources (source_id) ON DELETE CASCADE
);

CREATE TABLE duplicate_records (
    duplicate_id INTEGER NOT NULL AUTO_INCREMENT, 
    owner_id INTEGER NOT NULL, 
    original_contact_id INTEGER NOT NULL, 
    duplicate_contact_id INTEGER, 
    import_id INTEGER, 
    incoming_data TEXT, 
    matching_reason VARCHAR(255) NOT NULL, 
    confidence_score FLOAT NOT NULL, 
    resolution_status VARCHAR(20) NOT NULL, 
    detected_at DATETIME NOT NULL, 
    resolved_at DATETIME, 
    resolved_by INTEGER, 
    CONSTRAINT pk_duplicate_records PRIMARY KEY (duplicate_id), 
    CONSTRAINT ck_duplicate_records_resolution_status_valid CHECK (resolution_status IN ('pending','kept_existing','updated_existing','merged','not_duplicate')), 
    CONSTRAINT ck_duplicate_records_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1), 
    CONSTRAINT fk_duplicate_records_duplicate_contact_id_contacts FOREIGN KEY(duplicate_contact_id) REFERENCES contacts (contact_id) ON DELETE SET NULL, 
    CONSTRAINT fk_duplicate_records_import_id_csv_import_jobs FOREIGN KEY(import_id) REFERENCES csv_import_jobs (import_id) ON DELETE SET NULL, 
    CONSTRAINT fk_duplicate_records_original_contact_id_contacts FOREIGN KEY(original_contact_id) REFERENCES contacts (contact_id) ON DELETE CASCADE, 
    CONSTRAINT fk_duplicate_records_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (user_id) ON DELETE CASCADE, 
    CONSTRAINT fk_duplicate_records_resolved_by_users FOREIGN KEY(resolved_by) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE INDEX ix_duplicate_records_duplicate_contact_id ON duplicate_records (duplicate_contact_id);

CREATE INDEX ix_duplicate_records_import_id ON duplicate_records (import_id);

CREATE INDEX ix_duplicate_records_original_contact_id ON duplicate_records (original_contact_id);

CREATE INDEX ix_duplicate_records_owner_id ON duplicate_records (owner_id);

CREATE INDEX ix_duplicate_records_resolution_status ON duplicate_records (resolution_status);

CREATE TABLE lead_activities (
    activity_id INTEGER NOT NULL AUTO_INCREMENT, 
    contact_id INTEGER NOT NULL, 
    activity_type VARCHAR(40) NOT NULL, 
    activity_description TEXT, 
    activity_score INTEGER NOT NULL, 
    activity_date DATETIME NOT NULL, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_lead_activities PRIMARY KEY (activity_id), 
    CONSTRAINT fk_lead_activities_contact_id_contacts FOREIGN KEY(contact_id) REFERENCES contacts (contact_id) ON DELETE CASCADE
);

CREATE INDEX ix_activities_contact_date ON lead_activities (contact_id, activity_date);

CREATE INDEX ix_lead_activities_activity_date ON lead_activities (activity_date);

CREATE INDEX ix_lead_activities_activity_type ON lead_activities (activity_type);

CREATE INDEX ix_lead_activities_contact_id ON lead_activities (contact_id);

INSERT INTO alembic_version (version_num) VALUES ('ff0104bf2a60');

