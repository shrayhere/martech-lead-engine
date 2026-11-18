# MarTech CRM: Entity-Relationship Diagram

```mermaid
erDiagram
    users ||--o{ companies : owns
    users ||--o{ contacts : owns
    users ||--o{ csv_import_jobs : uploads
    users ||--o{ data_sources : owns
    users ||--o{ scoring_rules : configures
    users ||--o{ duplicate_records : reviews
    users |o--o{ audit_logs : performs
    companies |o--o{ contacts : "employs (company_id, SET NULL)"
    contacts ||--o{ lead_activities : "has (CASCADE)"
    contacts }o--o{ data_sources : "contact_sources (M:N)"
    csv_import_jobs ||--o{ sync_logs : "produces (CASCADE)"
    data_sources |o--o{ sync_logs : "feeds (SET NULL)"
    contacts ||--o{ duplicate_records : "original (CASCADE)"
    contacts |o--o{ duplicate_records : "duplicate (SET NULL)"
    csv_import_jobs |o--o{ duplicate_records : "detected in (SET NULL)"

    users {
        int user_id PK
        varchar full_name "NOT NULL"
        varchar email "UNIQUE NOT NULL"
        varchar password_hash "NOT NULL"
        varchar role "CHECK admin|member"
        datetime notifications_seen_at
        datetime created_at
        datetime updated_at
    }
    companies {
        int company_id PK
        int owner_id FK "users, CASCADE"
        varchar company_name "NOT NULL"
        varchar name_key "UNIQUE(owner_id, name_key)"
        varchar industry "INDEX"
        varchar website
        varchar company_email
        varchar phone
        varchar address
        varchar city
        varchar country
        int employee_count "CHECK >= 0"
        decimal annual_revenue "CHECK >= 0"
        text description
        datetime created_at
        datetime updated_at
    }
    contacts {
        int contact_id PK
        int owner_id FK "users, CASCADE"
        varchar first_name "NOT NULL"
        varchar last_name
        varchar email "UNIQUE(owner_id, email)"
        varchar phone "INDEX"
        varchar job_title
        int company_id FK "companies, SET NULL, nullable"
        varchar lifecycle_stage "NOT NULL"
        varchar lead_source "INDEX"
        int lead_score "CHECK 0..100"
        varchar lead_category "auto: hot|warm|cold|NULL"
        varchar lead_category_override "manual: hot|warm|cold|NULL"
        varchar lead_status
        datetime last_activity_at "INDEX"
        datetime created_at
        datetime updated_at
    }
    lead_activities {
        int activity_id PK
        int contact_id FK "contacts, CASCADE"
        varchar activity_type "INDEX"
        text activity_description
        int activity_score
        datetime activity_date "INDEX"
        datetime created_at
    }
    scoring_rules {
        int rule_id PK
        int owner_id FK
        varchar activity_type "UNIQUE(owner_id, activity_type)"
        varchar label
        int points "CHECK -100..100"
    }
    csv_import_jobs {
        int import_id PK
        int user_id FK "users, CASCADE"
        varchar original_filename
        varchar stored_filename
        datetime upload_timestamp
        int total_rows
        int successful_rows
        int inserted_rows
        int updated_rows
        int failed_rows
        int duplicate_rows
        int skipped_rows
        varchar import_status "CHECK"
        varchar sync_mode
        text column_mapping "JSON"
        varchar error_report_path
        varchar duplicate_report_path
        varchar success_report_path
        int duration_ms
    }
    data_sources {
        int source_id PK
        int owner_id FK
        varchar source_name "UNIQUE(owner_id, source_name)"
        varchar source_type "manual|csv|seed"
        text description
        datetime created_at
    }
    contact_sources {
        int contact_id PK, FK
        int source_id PK, FK
        datetime linked_at
    }
    sync_logs {
        int sync_id PK
        int import_id FK
        int source_id FK
        varchar sync_type
        int records_inserted
        int records_updated
        int records_skipped
        int records_failed
        varchar sync_status
        datetime started_at
        datetime completed_at
    }
    duplicate_records {
        int duplicate_id PK
        int owner_id FK
        int original_contact_id FK
        int duplicate_contact_id FK "nullable"
        int import_id FK "nullable"
        text incoming_data "JSON of incoming row"
        varchar matching_reason
        float confidence_score "CHECK 0..1"
        varchar resolution_status "CHECK"
        datetime detected_at
        datetime resolved_at
        int resolved_by FK
    }
    audit_logs {
        int audit_id PK
        int user_id FK "SET NULL"
        varchar entity_type "INDEX(entity_type, entity_id)"
        int entity_id
        varchar operation
        text old_values "JSON"
        text new_values "JSON"
        datetime timestamp "INDEX"
    }
```

## Design notes

* **Normalisation (3NF).** Company attributes live only in `companies`; contacts reference them through
  `company_id`. Lead score and category are attributes of a contact (a lead is a contact in a
  pre-customer lifecycle stage), so there is no redundant `leads` table.
* **One-to-many:** company → contacts, contact → activities, import job → sync logs, user → everything they own.
* **Many-to-many:** `contact_sources` records every data source (manual entry, seed data, CSV import) that
  created or updated a contact.
* **Referential integrity / deletion policies:** deleting a company sets `contacts.company_id` to NULL
  (contacts survive), deleting a contact cascades to its activities, deleting a user cascades to their data.
  SQLite enforces this with `PRAGMA foreign_keys=ON`; MySQL/InnoDB enforces it natively.
* **Uniqueness under concurrency:** `UNIQUE(owner_id, email)` on contacts and `UNIQUE(owner_id, name_key)` on
  companies make concurrent imports unable to create duplicates. A conflicting import fails with an
  IntegrityError and is rolled back completely.
* **Ownership:** every CRM table carries `owner_id` / `user_id`; every query filters on the logged-in user.
* The generated MySQL 8 DDL is in [`schema_mysql.sql`](schema_mysql.sql) (from `flask db upgrade --sql`).
