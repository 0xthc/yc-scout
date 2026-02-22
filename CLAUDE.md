# CLAUDE.md — Development Guide for SCOUT

## What is this project?

SCOUT is a YC founder intelligence dashboard. It scrapes Hacker News, GitHub, and Product Hunt for founder signals, scores them on 5 dimensions, and displays them in a React dashboard. The pipeline runs hourly via GitHub Actions.

## Tech Stack

- **Frontend**: React 19 + Vite 7 (single-file `src/App.jsx`), deployed to GitHub Pages
- **Backend**: FastAPI (Python 3.12), deployed to Render via Docker
- **Database**: Turso (libsql over HTTP) in production, local SQLite in dev
- **Pipeline**: GitHub Actions cron (hourly)

## How to run locally

```bash
# Install deps
pip install -r backend/requirements.txt
npm install

# Seed demo data (only needed once, uses local SQLite)
python -m backend.seed

# Start API server
uvicorn backend.api:app --reload

# Start frontend dev server (separate terminal)
VITE_API_URL=http://localhost:8000 npm run dev
```

## Key Files to Know

### Backend

- `backend/api.py` — All API endpoints. The main one is `GET /api/founders` which uses `_build_founders_batch()` to efficiently batch Turso HTTP calls (5 queries in one pipeline instead of 4N+1). Response is paginated: `{ founders: [...], total, limit, offset }`.
- `backend/db.py` — Database abstraction. `_TursoConnection` wraps Turso's HTTP pipeline API to look like sqlite3. Key method: `execute_batch()` batches multiple queries into a single HTTP call. `get_db()` context manager auto-selects Turso vs local SQLite based on env vars.
- `backend/scoring.py` — 5-dimension scoring engine. Dimensions: founder_quality (who is this person?), execution_velocity (are they building?), market_conviction (domain obsession), early_traction (community/market signals), deal_availability (still early enough?). Each scored 0-100 using log-scaled normalization. Composite = weighted average. Default weights in `DEFAULT_WEIGHTS` dict, tunable from the frontend UI.
- `backend/pipeline.py` — Orchestrator: scrape all 3 sources -> score every founder -> check alerts. Can run one-shot (`python -m backend.pipeline`) or scheduled (`--schedule`).
- `backend/scrapers/hn.py` — Searches Algolia for Show HN posts with 50+ points, fetches user profiles from Firebase API. No token needed.
- `backend/scrapers/github.py` — Searches trending repos by topic, fetches user profiles, repos, and 90-day commit counts. Needs `GITHUB_TOKEN` for rate limits.
- `backend/scrapers/producthunt.py` — GraphQL API, fetches top posts and maker profiles. Needs `PH_API_TOKEN`.
- `backend/alerts.py` — Slack webhook + email alerts. Triggers on: high score crossing threshold (85), momentum spike (>15pts).
- `backend/models.py` — Pydantic models: `FounderOut`, `PaginatedFounders`, `StatusUpdate`, `PipelineResult`.
- `backend/config.py` — All env var defaults in one place.

### Frontend

- `src/App.jsx` — Entire dashboard in one file. Dark terminal UI with: header stats, source/status filters, search, sortable founder list, detail panel with score breakdown + weight tuning sliders + signals. Weight sliders recalculate composite scores client-side in real time. Fetches from `VITE_API_URL/api/founders?limit=50`. Shows loading spinner, error with retry, or empty state.

### Infrastructure

- `.github/workflows/pipeline.yml` — Hourly cron. Runs `python -m backend.pipeline` with secrets.
- `.github/workflows/deploy.yml` — GitHub Pages deploy on push to main. Reads `VITE_API_URL` from repo variables (not secrets).
- `render.yaml` — Render Web Service config (Docker, free tier). Health check at `/api/stats`.
- `Dockerfile` — Python 3.12-slim, installs deps, runs uvicorn on port 8000.

## Database Schema

7 tables in `backend/db.py`:

- `founders` — Core founder data (name, handle, bio, domain, stage, company, status)
- `founder_sources` — Which platforms a founder was found on (github, hn, producthunt)
- `founder_tags` — Tags inferred from repo topics and PH categories
- `signals` — Activity signals (e.g. "Show HN: X — 847 pts", "500 commits in 90 days")
- `stats_snapshots` — Time-series metrics (stars, karma, commits, followers, upvotes)
- `scores` — Time-series composite + dimension scores
- `alert_log` — Record of sent alerts

Key indexes: `idx_signals_founder`, `idx_scores_founder`, `idx_stats_founder` — all on `(founder_id, timestamp DESC)`.

## Important Patterns

### Turso HTTP API
The db layer talks to Turso via its HTTP pipeline API (`/v3/pipeline`). Each `execute()` call is one HTTP request. For bulk operations, use `execute_batch()` which sends multiple SQL statements in a single HTTP call — critical for performance.

### N+1 Query Prevention
`_build_founders_batch()` in `api.py` fetches all related data (sources, tags, scores, stats, signals) with 5 `IN(...)` queries batched into one Turso pipeline call, instead of 4 queries per founder. This was the key optimization that brought the endpoint from 60s to ~1-2s.

### Frontend Data Flow
1. App starts with empty state + loading spinner
2. Fetches `GET /api/founders?limit=50`
3. On success: sets founders, shows LIVE indicator, starts 60s polling
4. On failure: shows error message with retry button
5. Status changes are optimistic (update UI immediately, fire-and-forget PATCH)

## Common Tasks

### Add a new scraper
1. Create `backend/scrapers/newplatform.py` with a `scrape_newplatform(conn)` function
2. Export it from `backend/scrapers/__init__.py`
3. Add the call in `backend/pipeline.py` Phase 1
4. Add the source to the CHECK constraint in `db.py` schema (`founder_sources.source` and `signals.source`)

### Adjust scoring weights
Default weights are in `DEFAULT_WEIGHTS` dict in `backend/scoring.py`. Users can also tune weights live via the dashboard UI sliders — composite scores recalculate client-side.

### Add a new alert channel
Add a `_send_newchannel()` function in `backend/alerts.py`, then call it from `check_alerts()`.

### Change the pipeline schedule
Edit the cron expression in `.github/workflows/pipeline.yml` (currently `0 * * * *` = every hour).

## Environment Variables

All defaults are in `backend/config.py`. For local dev, copy `.env.example` to `.env`. For production, set as GitHub Secrets (pipeline) or Render env vars (API).

Critical for production:
- `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` — without these, falls back to local SQLite
- `VITE_API_URL` — must be a GitHub **variable** (not secret), read at build time by Vite
