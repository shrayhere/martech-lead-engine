# MarTech Data Quality & Lead Scoring Engine

[![GitHub Repository](https://img.shields.io/badge/GitHub-shrayhere%2Fmartech--lead--engine-indigo?logo=github)](https://github.com/shrayhere/martech-lead-engine)
[![Python](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Pandas%20%7C%20Scikit--Learn-blue)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%7C%20Tailwind%20CSS%20%7C%20Recharts-cyan)](https://reactjs.org/)

An enterprise-grade B2B Marketing & Sales Data Quality, Fuzzy Deduplication, Lead Scoring, and Automated Sales Rep Assignment Engine. Designed to mirror marketing automation platforms (like Salesforce Data Governance & Marketo Revenue Stage models).

---

## 🌟 Key Features & Pipeline Stages

### 1. Data Ingestion Engine (`POST /api/leads/upload`)
- Ingests messy B2B CSV lead files into a `raw_leads` database table before cleaning.
- Validates schema headers (`first_name`, `last_name`, `email`, `company`, `job_title`, `phone`, `state`, `industry`, `company_size`, `engagement_score`, `last_activity_date`).
- **Built-in Sample Generator (`GET /api/leads/sample-csv`)**: Downloads 200 synthetic B2B lead records with realistic data quality issues (typos, inconsistent state spellings, mixed phone formats, placeholder junk rows).

### 2. Data Quality & RapidFuzz Deduplication Pipeline (`POST /api/leads/clean`)
- **Field Normalization**: Standardizes US state names/abbreviations (`"California"`, `"calif"` → `"CA"`), formats phone numbers to international **E.164** standard (`"+15552345678"`), and normalizes company casing.
- **Deduplication**: Merges records with the same email or phone. A fuzzy match (for typos without a shared identifier) also requires the **same last name**, a **first name ≥ 85% similar** and the **same company or email domain**, then a RapidFuzz `token_sort_ratio` of the composite `name | company | email` ≥ 85% (`backend/app/services/match_rules.py`).
- **Junk Detection**: Flags rows missing both email and phone, or containing placeholder strings like `"test"`, `"n/a"`, `"asdf"`.
- **Merge & Audit Trail**: Keeps the most complete/recent lead in `clean_leads` and archives secondary duplicates in the audit log `merged_leads_log`.

### 3. Lead Scoring Engine (`POST /api/leads/score`)
- Calculates a 0–100 score for every clean lead.
- **Score Bands**:
  - 🔥 **Hot (80 – 100)**: Immediate sales routing priority (Red/Coral badge).
  - ⚡ **Warm (50 – 79)**: Nurture sequence / sales outreach (Amber badge).
  - ❄️ **Cold (0 – 49)**: Low engagement / non-target segment (Slate badge).
- **Dual Scoring Engine (Toggleable in UI)**:
  1. **Rule-Based Explainable Model**: Firmographic signals (Company size 15%, Target Industry 15%, Title Seniority 10%) + Behavioral signals (Engagement 35%, Activity Recency Exponential Decay 25%).
  2. **Scikit-Learn ML Model**: Trained Logistic Regression classifier predicting conversion probability $P(\text{converted})$.

### 4. Sales Rep Automated Assignment Engine (`POST /api/leads/assign`)
- Routes scored leads to seed sales reps according to strict rule priority:
  - **Rule 1 (Highest)**: Territory Match AND Industry Specialty Match.
  - **Rule 2**: Territory Match Only.
  - **Rule 3**: Industry Specialty Match Only.
  - **Rule 4 (Fallback)**: Round-Robin Load-Balancing (assigns to rep with lowest active lead count).
- Generates human-readable routing audit rationale (e.g. `"Assigned to Rep Sarah Jenkins: territory match (CA) + industry match (SaaS)"`).

---

## 🔬 Core Rationale & Code Logic Explanations

### Deduplication rule and how it was tested
85% started as a default. Testing it against the sample generator's ground truth (exactly 20 planted duplicates among 170 distinct people) showed that a composite-string score alone is **name-blind**. Different colleagues at the same company (e.g. *Katherine Thomas* and *Katherine Wilson* at OmniChannel Media) score about 85%, so they were merged. The name guards above fix this:

| Rule | Threshold | Correct merges | Wrong merges | Missed |
|---|---:|---:|---:|---:|
| Composite score only (old) | 85% | 20 | 20 | 0 |
| Composite score only (old) | 90% | 20 | 1 | 0 |
| Guarded rule (current) | 80–95% | 20 | 0 | 0 |

Reproduce with `cd backend && python evaluate_dedup.py` (full table in [`docs/dedup_evaluation.md`](docs/dedup_evaluation.md)). Limitation: every planted duplicate in the sample still shares an email or phone with its original, so the fuzzy path is covered by unit tests (`backend/tests/test_dedup_rules.py`) rather than by this dataset.

The merge log (`merged_leads_log`) stores the kept record (`winner_raw_lead_id`) and the archived record (`archived_raw_lead_id`) in the same ID space, named by `id_type` (`raw_lead_id` for `/api/leads/clean`, `csv_row` for the smart pipeline). The surviving record is chosen by completeness and engagement (winner-take-all). Fields from merged records are not copied over.

### Rule-Based Scoring Weight Allocation
| Signal Category | Signal Name | Weight | Rationale |
| :--- | :--- | :--- | :--- |
| **Firmographic** | Company Size | **15%** | Enterprise accounts (>1,000 employees) yield higher ACV. |
| **Firmographic** | Target Industry | **15%** | Matches ICP high-value industries (SaaS, Fintech, Cybersecurity). |
| **Firmographic** | Job Seniority | **10%** | Decision-maker titles (C-Level, VP, Director) convert faster. |
| **Behavioral** | Engagement Score | **35%** | Direct marketing engagement (opens, clicks, site visits). |
| **Behavioral** | Recency Decay | **25%** | Applies exponential decay $S = 100 \cdot e^{-0.02 \cdot \text{days}}$ to prioritize recent activity. |

The weights are a judgement call favouring recent behaviour (60% behavioural, 40% firmographic). They have not been fitted to or validated against real conversion outcomes.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.13+ (versions pinned in `backend/requirements.txt`)
- Node.js **20.19+ or 22.12+** & npm (required by Vite 8)

### 2. Backend Setup (FastAPI)
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI development server (uses ./martech.db unless DATABASE_URL is set)
uvicorn app.main:app --reload --port 8000

# Tests (use a temporary database, never martech.db)
python -m pytest -q

# Deduplication accuracy report / performance benchmark (benchmark uses its own temporary database)
python evaluate_dedup.py
python benchmark.py
```
- API Documentation available at: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup (React + Vite + Tailwind CSS)
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
- Frontend App available at: `http://localhost:3000`

---

## 🌐 Deployment Setup

### Frontend Deployment (Vercel)
1. Push code to GitHub (`shrayhere/martech-lead-engine`).
2. Connect repo to Vercel.
3. Vercel automatically detects Vite settings. Uses included `frontend/vercel.json` for API rewrites.

### Backend Deployment (Render + Postgres)
SQLite does **not** persist on Render: the service disk is wiped on every deploy and restart. The Blueprint in [`render.yaml`](render.yaml) (repository root) therefore creates a managed **Render Postgres** database and passes its URL to the API as `DATABASE_URL`. `postgres://` URLs are handled automatically.
1. In Render: **New → Blueprint**, pick this repository. It creates `martech-db` and the `martech-lead-engine-api` web service (`rootDir: backend`).
2. Set `CORS_ORIGINS` to your exact Vercel URL (comma-separated for several). Production and preview URLs matching `https://martech-lead-engine*.vercel.app` are allowed by default through `CORS_ORIGIN_REGEX`.
3. Render's free Postgres plan expires after 30 days. Use a paid plan for data you need to keep.

Postgres support is configured but has not been tested against a live Postgres server here. The test suite runs on SQLite.

---

## 📁 Repository Architecture
```text
martech-lead-engine/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app & CORS setup
│   │   ├── config.py            # Scoring weights & RapidFuzz thresholds
│   │   ├── database.py          # SQLAlchemy connection (SQLite locally, Postgres on Render)
│   │   ├── models/schemas.py    # SQLAlchemy database models
│   │   ├── routes/              # API endpoints (ingestion, cleaning, scoring, assignment)
│   │   ├── services/            # Core business logic algorithms
│   │   └── ml/                  # Scikit-learn Logistic Regression classifier
│   ├── evaluate_dedup.py        # dedup accuracy vs. generator ground truth
│   ├── report_metrics.py        # computes every number in the PDF report
│   ├── benchmark.py             # performance benchmark (temporary database)
│   ├── tests/
│   └── requirements.txt         # exact pinned versions
├── frontend/
│   ├── src/
│   │   ├── components/          # Upload, Data Quality, Scoring, Assignment pages
│   │   ├── App.jsx              # Main tab routing & state
│   │   └── index.css            # Tailwind & glassmorphism custom styles
│   ├── package.json
│   └── vercel.json
├── render.yaml                  # Render Blueprint (API + Postgres)
├── generate_pdf_report.py       # regenerates the architecture report from measured numbers
└── README.md
```
