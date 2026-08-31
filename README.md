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
- **Fuzzy Deduplication**: Uses `rapidfuzz` on composite tuple `(name + company + email)` with an **85% similarity threshold**.
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

### Why RapidFuzz 85% Similarity Threshold Was Chosen
In real-world B2B sales databases, exact string matching misses 30-40% of duplicate entries due to slight spelling typos (*Jonathan Smith* vs *Jonathon Smith*), company suffixes (*Acme Corp* vs *Acme Corporation*), or modified email domains. An **85% RapidFuzz token sort ratio** threshold provides the optimal empirical balance: high recall for typos while avoiding false-positive merges between distinct individuals at similar companies.

### Rule-Based Scoring Weight Allocation
| Signal Category | Signal Name | Weight | Rationale |
| :--- | :--- | :--- | :--- |
| **Firmographic** | Company Size | **15%** | Enterprise accounts (>1,000 employees) yield higher ACV. |
| **Firmographic** | Target Industry | **15%** | Matches ICP high-value industries (SaaS, Fintech, Cybersecurity). |
| **Firmographic** | Job Seniority | **10%** | Decision-maker titles (C-Level, VP, Director) convert faster. |
| **Behavioral** | Engagement Score | **35%** | Direct marketing engagement (opens, clicks, site visits). |
| **Behavioral** | Recency Decay | **25%** | Applies exponential decay $S = 100 \cdot e^{-0.02 \cdot \text{days}}$ to prioritize recent activity. |

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.10+
- Node.js v18+ & npm

### 2. Backend Setup (FastAPI)
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
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

### Backend Deployment (Render / Railway)
1. Create a Web Service on Render/Railway using `backend/render.yaml` or set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## 📁 Repository Architecture
```text
martech-lead-engine/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app & CORS setup
│   │   ├── config.py            # Scoring weights & RapidFuzz thresholds
│   │   ├── database.py          # SQLite / SQLAlchemy connection
│   │   ├── models/schemas.py    # SQLAlchemy database models
│   │   ├── routes/              # API endpoints (ingestion, cleaning, scoring, assignment)
│   │   ├── services/            # Core business logic algorithms
│   │   └── ml/                  # Scikit-learn Logistic Regression classifier
│   ├── requirements.txt
│   └── render.yaml
├── frontend/
│   ├── src/
│   │   ├── components/          # Upload, Data Quality, Scoring, Assignment pages
│   │   ├── App.jsx              # Main tab routing & state
│   │   └── index.css            # Tailwind & glassmorphism custom styles
│   ├── package.json
│   └── vercel.json
└── README.md
```
