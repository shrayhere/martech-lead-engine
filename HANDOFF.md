# HANDOFF — MarTech Lead Engine

This project was built in a previous Claude Code session on another PC. That chat is not available here, so this file is the context.

## What it is
- `backend/`  FastAPI: CSV upload + schema mapping, cleaning, RapidFuzz dedup, lead scoring (rules or scikit-learn), rep assignment. Run: `uvicorn app.main:app --port 8000` from `backend/`.
- `frontend/` React 19 + Vite + Tailwind + Recharts. Dev server on port 3000, proxies /api to port 8000. Needs Node 20.19+ or 22.12+.
- `crm/`      Separate Flask CRM (MySQL, SQLite fallback). Independent of the above. Copy `crm/.env.example` to `crm/.env` and set a new SECRET_KEY. NOT covered by render.yaml.
- `render.yaml` Render Blueprint (API + free Postgres). `frontend/vercel.json` proxies /api to https://martech-lead-engine-api.onrender.com, so keep that Render service name.

## State
- Git remote `origin` = github.com/shrayhere/martech-lead-engine. Last commit is "Stage 4" (Oct 13). Almost all later work is UNCOMMITTED (see `git status`).
- Work done last session: dedup bug fixed (new `backend/app/services/match_rules.py`: fuzzy merge needs same last name + first name >=85% + same company/email domain); sample generator fixed; merge log ID bug fixed; tests/benchmark use temp DBs; PDF report figures now computed by `backend/report_metrics.py`; requirements pinned (Python 3.13/3.14); model retrained with scikit-learn 1.7.2; `render.yaml` added; CORS via CORS_ORIGINS / CORS_ORIGIN_REGEX (default allows martech-lead-engine*.vercel.app); Literal["rule","ml"] fix in scoring.py. 13 backend tests passed on the old PC.
- Untested: Postgres on Render, ML-mode scoring in the UI.
- Render free Postgres expires after 30 days.

## Still to do
1. Human review queue for borderline merges/junk
2. Data-quality score dashboard
3. AI classification (persona, buying role, interest)
4. HubSpot sync (pushes to a real portal: ASK THE USER FIRST; tokens in env vars only)
5. Automation opportunity matrix
(crm/ already has a review queue and quality checks that could be reused.)

## Setup on this machine
Create a fresh venv in backend/ and install `requirements.txt`; run `npm install` in frontend/; run tests (`pytest` from backend/); start both servers. The old venv/node_modules were deleted because they came from another PC. If Windows blocks a compiled package, do not change security settings; try the pinned versions or another installed Python.

## Rules
Ask before any commit or push. Never commit .env files, keys or .db files.
