# HANDOFF — MarTech Lead Engine

This project was built in a previous Claude Code session on another PC. That chat is not available here, so this file is the context.

## What it is
- `backend/`  FastAPI: CSV upload + schema mapping, cleaning, RapidFuzz dedup, lead scoring (rules or scikit-learn), rep assignment. Run: `uvicorn app.main:app --port 8000` from `backend/`.
- `frontend/` React 19 + Vite + Tailwind + Recharts. Dev server on port 3000, proxies /api to port 8000. Needs Node 20.19+ or 22.12+.
- `crm/`      Separate Flask CRM (MySQL, SQLite fallback). Independent of the above. Copy `crm/.env.example` to `crm/.env` and set a new SECRET_KEY. NOT covered by render.yaml.
- `render.yaml` Render Blueprint (API + free Postgres). `frontend/vercel.json` proxies /api to https://martech-lead-engine-api.onrender.com, so keep that Render service name.

## State (2026-11-18)
- Git remote `origin` = github.com/shrayhere/martech-lead-engine, branch `main`; everything is committed and pushed.
- Earlier work: guarded dedup rule (`backend/app/services/match_rules.py`), merge-log ID fix, temp DBs for tests/benchmark,
  PDF numbers computed by `backend/report_metrics.py`, pinned requirements, `render.yaml` (API + Postgres), CORS via env vars.
- Added 2026-11-18 (all internship "Add" items):
  1. Data-quality score + dashboard: `services/quality_service.py`, `GET /api/quality/report`, DQ Score page.
  2. Human review queue: `review_items` table, `services/review_service.py`, `/api/review`, Review page. Guarded fuzzy pairs
     80-90% go to review (auto-merge only >= 90%); junk rows and pipeline rows dropped for no email/phone are queued.
  3. AI classification: `services/classifier.py` (local scikit-learn model + optional Claude engine `claude-opus-5-5`),
     business rules -> recommended action, `/api/classify/*`, AI Classify page, `evaluate_classifier.py`,
     `docs/classification_evaluation.md`. Smart Upload classifies automatically with the local model.
  4. HubSpot sync: `services/hubspot_sync.py`, `/api/hubspot/*`, HubSpot page, `docs/hubspot_setup.md`. Dry run by default.
  5. Automation opportunity matrix: `docs/automation_opportunity_matrix.md`.
  Also: staged flow (Stages 1-4) no longer deletes/re-scores Smart Upload runs; assignment_log deleted before clean_leads
  (Postgres foreign key); header tabs wrap instead of widening the page; "Matched." merge reasons fixed.
- 24 backend tests pass (Python 3.13 venv). Frontend build + lint pass (warnings only).
- Not yet done / untested: live HubSpot push (needs the user's private-app token; ASK FIRST), HubSpot workflows (built in the
  HubSpot UI, see docs), Claude engine against the real API (needs a key; costs money; ASK FIRST), Postgres on Render,
  deployment to Render/Vercel. `benchmark.py` misses its 10 s target for 10k rows (10.2-12.4 s here; fuzzy dedup dominates).
- Render free Postgres expires after 30 days.

## Next ideas
- Closed-loop retraining of the scoring model from won/lost deals (needs real outcomes).
- Speed up fuzzy dedup for the 10k-row benchmark.

## Setup on this machine
Create a fresh venv in backend/ (Python 3.13) and install `requirements.txt`; run `npm install` in frontend/; run tests (`python -m pytest -q` from backend/); start both servers. If Windows blocks a compiled package, do not change security settings; try the pinned versions or another installed Python.

## Rules
Ask before any commit or push. Never commit .env files, keys or .db files.
