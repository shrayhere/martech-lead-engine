# MarTech CRM

A relational CRM for marketing and sales teams, with these features:

* companies and contacts linked by foreign keys
* activity-based Hot / Warm / Cold lead scoring
* a CSV import engine with column mapping, cleaning, duplicate detection, dry-run preview and transactional sync
* a Kanban lead pipeline
* live analytics
* per-user data isolation

It is built with Flask, SQLAlchemy (MySQL 8 or SQLite), Pandas, vanilla JS and Chart.js.

> This app lives in `crm/` next to the earlier FastAPI/React prototype (`backend/`, `frontend/`). The two are independent.

---

## 1. Prerequisites
* Python 3.10+ (tested on 3.14)
* MySQL 8+ (recommended). Without it the app falls back to a local SQLite file so you can run it right away.

## 2. Installation
```bash
cd crm
python -m venv venv
# Windows:  venv\Scripts\activate      macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit SECRET_KEY and DATABASE_URL
```

## 3. MySQL configuration
```sql
CREATE DATABASE martech CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE martech_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'martech_user'@'localhost' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON martech.* TO 'martech_user'@'localhost';
GRANT ALL PRIVILEGES ON martech_test.* TO 'martech_user'@'localhost';
```
In `.env`:
```
DATABASE_URL=mysql+pymysql://martech_user:change-me@127.0.0.1:3306/martech?charset=utf8mb4
TEST_DATABASE_URL=mysql+pymysql://martech_user:change-me@127.0.0.1:3306/martech_test?charset=utf8mb4
```
Leave `DATABASE_URL` empty to use `instance/martech.db` (SQLite).

**On the current development machine** MySQL 8.4.9 is already installed as the Windows service `MySQL84`
(auto-start, listening on `127.0.0.1:3306` only, data in `C:\ProgramData\MySQL\MySQL Server 8.4\Data`).
The `martech` and `martech_test` databases and the `martech_user` account exist. The connection URLs and the
MySQL root password are in `crm/.env` (gitignored). Manage the service with `Start-Service MySQL84` and
`Stop-Service MySQL84` (admin PowerShell), or with the Services app.

## 4. Environment variables (`.env`)
| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Session and CSRF signing key (**set a long random value**) | dev value |
| `DATABASE_URL` | SQLAlchemy URL (MySQL recommended) | SQLite file |
| `TEST_DATABASE_URL` | Separate database for tests | in-memory SQLite |
| `MAX_UPLOAD_MB` / `MAX_IMPORT_ROWS` / `CSV_CHUNK_SIZE` | Upload limits and chunk size | 10 / 100000 / 1000 |
| `DEFAULT_COUNTRY_CODE` | Prefix for 10-digit phone numbers | `+1` |
| `SESSION_COOKIE_SECURE` | `1` when served over HTTPS | `0` |

## 5. Database creation and migrations
```bash
python -m flask --app run.py db upgrade        # create or upgrade all tables
python -m flask --app run.py seed              # optional demo data (see below)
```
After changing models: `python -m flask --app run.py db migrate -m "describe change"` and then `db upgrade`.
To print the MySQL DDL without connecting, run `db upgrade --sql` (output is saved in `docs/schema_mysql.sql`).

> On some locked-down Windows machines the `flask.exe` launcher is blocked. `python -m flask` always works.

## 6. Start the application
```bash
python run.py                  # http://127.0.0.1:5000
# PORT=8080 python run.py      # another port
```
Register an account at `/register`, or run the seed command and log in with the demo account below.

**Demo account (created by `flask seed`):** `demo@martech.local` / `MarTechDemo2026`
The seed command creates 12 companies (Google has the 3 contacts from the specification), 36 contacts, a
mix of Hot, Warm and Cold leads, several industries and lead sources, and activities. Seed records are linked to
the **"Seed data"** data source, CSV imports to **"CSV Import"** and manual records to **"Manual entry"**. These
appear as badges on each contact and in Data Management, so seed data is always distinguishable from
imported data.

Scores include a time-based rule (no engagement for 30 days gives -15). Scores refresh on every event and on
login. In production, schedule `python -m flask --app run.py rescore` once a day.

## 7. Run the tests
```bash
python -m pytest -q
```
Tests use a separate database (`TEST_DATABASE_URL`, default in-memory SQLite). There are 37 tests covering:
* registration and authentication, CSRF
* contact and company CRUD, contact–company relationships
* lead scoring and classification, overrides, configurable rules
* CSV upload validation, column mapping, data cleaning
* duplicate detection and every resolution action
* insert-only, update-existing and upsert syncs, dry runs, rollback, concurrent-import protection
* dashboard calculations and date ranges, search and filtering, pagination
* authorization and data isolation between users

## 8. Importing the sample CSV files (`samples/`)
Open **Import & Sync**, drop a file, check the column mapping, choose a mode, **run the dry-run preview**,
then **Confirm & import**.

| File | Scenario |
|---|---|
| `01_first_import.csv` | **First-time import (Upsert).** It contains messy whitespace and casing, several phone formats, `usa` and `bangalore` aliases, company variants (`TechNova Inc.` / `technova inc` become one company), an invalid email, a row without identifiers, a bad date, and an email repeated within the file. |
| `02_second_import_updates.csv` | **Second import with existing contacts.** Run it as *Upsert* or *Update existing*. Ritika and Grace are updated (blank cells keep existing values). Gracie (same phone as Grace), Kabir and Daniel (same name at the same company, new email) go to **duplicate review**. New contacts are inserted. |
| `03_different_columns_semicolon_latin1.csv` | **Different structure.** Semicolon-delimited, Windows-1252 encoded, with `name; Email Address; Mobile; Organization; Designation; Sector; Web; Source`. Auto-mapped, accents preserved, and `Sharma, Rahul` is split. |
| `04_activity_updates.csv` | **Score recalculation.** Run it as *Update existing*: demo and pricing activities move Grace from Cold to **Hot**. The unknown email is skipped. |

Then open **Data Management** to Keep, Update or Merge the flagged duplicates, and **Overview** to see the dashboard reflect the imported records.

## 9. Key behaviour and design decisions
* **Lead = contact** in a pre-customer lifecycle stage (subscriber, lead, MQL, SQL, opportunity). Score and category live on the contact (normalised; no duplicate leads table).
* **Scoring:** sum of activity points from configurable rules (Settings), plus the one-off 30-day inactivity penalty, bounded 0–100. Hot 60–100, Warm 30–59, Cold 0–29. A contact with no valid email or phone is **excluded** (category NULL, status `excluded`). A manual override is stored separately (`lead_category_override`), so the automatic category is never lost, and every override is audited.
* **Duplicates:** an exact email match is certain and handled by the sync mode. Phone, name + company and fuzzy name (≥ 88%) matches are **never merged automatically**; they go to the review queue with *Keep existing*, *Update existing*, *Merge* or *Not a duplicate*.
* **Sync safety:** each import runs in one transaction (all or nothing). A dry run executes the exact same code and rolls back. Records missing from a CSV are never deleted. Empty CSV cells never overwrite existing data. Unique constraints plus a per-user "one running import" check prevent concurrent duplicate inserts.
* **Invalid data is never silently dropped:** each failed row is listed with its reasons, and you can download it as CSV with the original values.
* **Security:** passwords are hashed with Werkzeug scrypt. Sessions use Flask-Login. Flask-WTF CSRF checks every state-changing request (the JS sends `X-CSRFToken`). Queries are parameterised through the ORM. Uploads are checked for extension, size, binary or Excel content and row limits, stored under random names and only ever parsed as text. Every query is scoped to the logged-in user.
* **Multi-user:** each user has a private workspace (contacts, companies, imports, rules, reports). The first registered user gets the `admin` role, which is currently informational.

## 10. Project structure
```
crm/
├── app/
│   ├── __init__.py          # app factory, error handlers, SQLite FK pragma
│   ├── extensions.py        # db, migrate, login manager, CSRF
│   ├── cli.py               # flask seed / flask rescore
│   ├── models/              # user, company, contact, activity, lead (scoring rules), import_job, audit_log
│   ├── routes/              # auth, pages, contacts, companies, leads, imports, dashboard, reports, data_management, settings
│   ├── services/            # data_cleaner, csv_processor, duplicate_detector, sync_engine, lead_scoring, analytics, crm
│   ├── utils/api.py         # pagination, errors, ownership, audit helpers
│   ├── templates/           # Jinja page shells
│   └── static/              # css/app.css, js/app.js, js/pages/*, js/vendor/chart.umd.min.js
├── migrations/              # Flask-Migrate / Alembic
├── samples/                 # sample CSV files
├── tests/                   # pytest suite
├── docs/                    # ER diagram, API reference, MySQL DDL
├── config.py · run.py · requirements.txt · .env.example
```
More detail: [docs/ER_DIAGRAM.md](docs/ER_DIAGRAM.md) · [docs/API.md](docs/API.md)
