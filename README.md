# SCOUT — YC Intelligence Dashboard

SCOUT automatically discovers and scores startup founders across Hacker News, GitHub, and Product Hunt. It runs a pipeline hourly to scrape founder activity, compute a 5-dimension score, and surface the strongest candidates in a real-time dashboard.

## Architecture

```
GitHub Actions (cron hourly)          React Dashboard (GitHub Pages)
  |                                        |
  | scrape HN/GH/PH -> score -> alert     | fetch /api/founders
  |                                        |
  v                                        v
Turso DB  <------>  FastAPI on Render  ---->  JSON response
(libsql)            (Python backend)
```

**Frontend**: React + Vite, deployed to GitHub Pages
**Backend**: FastAPI (Python), deployed to Render (free tier)
**Database**: Turso (libsql over HTTP), free tier (8GB, 9B row reads/mo)
**Pipeline**: GitHub Actions cron job, runs every hour

## Data Sources

| Source | API | What it scrapes | Token required |
|--------|-----|----------------|----------------|
| Hacker News | Algolia + Firebase | Show HN posts (50+ pts), user karma, submissions | No |
| GitHub | REST API v3 | Trending repos, commit velocity, stars, topics | Yes (`SCOUT_GITHUB_TOKEN`) |
| Product Hunt | GraphQL v2 | Top posts, maker profiles, upvotes, launches | Yes (`PH_API_TOKEN`) |

## Scoring Engine

Each founder is scored on 5 dimensions (0-100), then combined with calibrated weights:

| Dimension | Weight | Signals |
|-----------|--------|---------|
| Momentum (25%) | 0.25 | Commit velocity, posting frequency, strong signal density |
| Domain (20%) | 0.20 | HN karma, GitHub stars, repo count |
| Team (15%) | 0.15 | Bio keywords (ex-FAANG, PhD, serial founder), alumni connections, followers |
| Traction (25%) | 0.25 | Star count, HN top score, PH upvotes, signal volume |
| YC Fit (15%) | 0.15 | Technical founder signals, domain fit (B2B/infra/AI), builder velocity |

Normalization uses log-scaling to reward early traction without over-indexing on outliers.

## Alerts

Triggers when:
- Founder crosses score threshold (default: 85)
- Momentum spikes >15 points between runs

Channels: Slack webhook, email (SMTP). Both optional.

## Project Structure

```
yc-scout/
  backend/
    api.py              FastAPI server — /api/founders, /api/stats, /api/pipeline/run
    db.py               Database layer — Turso HTTP API (prod) or local SQLite (dev)
    config.py           Environment variable configuration
    models.py           Pydantic models — FounderOut, PaginatedFounders, etc.
    pipeline.py         Orchestrator — scrape -> score -> alert
    scoring.py          5-dimension scoring engine with log-scaled normalization
    alerts.py           Slack + email notification system
    seed.py             Seeds demo data for development
    requirements.txt    Python deps: fastapi, uvicorn, httpx, pydantic
    scrapers/
      hn.py             Hacker News scraper (Algolia + Firebase APIs)
      github.py         GitHub scraper (REST API v3)
      producthunt.py    Product Hunt scraper (GraphQL v2)
  src/
    App.jsx             Single-file React dashboard (dark terminal UI)
    main.jsx            React entry point
  .github/workflows/
    pipeline.yml        Hourly cron: scrape -> score -> alert
    deploy.yml          GitHub Pages deployment on push to main
  render.yaml           Render deployment config (Docker, free tier)
  Dockerfile            Python 3.12-slim, uvicorn
  .env.example          All environment variables documented
  setup.sh              One-command local setup script
```

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 20+
- (Optional) Turso CLI for cloud database

### Option A: Automated setup

```bash
chmod +x setup.sh && ./setup.sh
```

This installs deps, creates a local SQLite DB, seeds demo data, builds the frontend, and verifies the API.

### Option B: Manual setup

```bash
# Backend
pip install -r backend/requirements.txt
python -m backend.seed                       # Seed demo data into local SQLite

# Frontend
npm install
npm run build

# Run
uvicorn backend.api:app --reload             # API at http://localhost:8000
VITE_API_URL=http://localhost:8000 npm run dev  # Dashboard at http://localhost:5173
```

### Running the pipeline locally

```bash
# One-shot run (scrapes HN/GH/PH, scores founders, checks alerts)
python -m backend.pipeline

# Recurring (runs every PIPELINE_INTERVAL_MINUTES, default 60)
python -m backend.pipeline --schedule
```

## Deployment

### 1. Database (Turso)

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create scout
turso db show scout --url     # -> TURSO_DATABASE_URL
turso db tokens create scout  # -> TURSO_AUTH_TOKEN
```

### 2. API (Render)

- Connect your repo at render.com -> New Web Service
- `render.yaml` is auto-detected (Docker, free tier)
- Add env vars: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `GITHUB_TOKEN`, `PH_API_TOKEN`
- Health check: `/api/stats`

### 3. Frontend (GitHub Pages)

Deploys automatically on push to `main` via `.github/workflows/deploy.yml`.

Set `VITE_API_URL` as a **GitHub repo variable** (not secret):
- Repo -> Settings -> Secrets and variables -> Actions -> Variables tab
- Value: your Render service URL (e.g. `https://scout-api.onrender.com`)

### 4. Pipeline (GitHub Actions)

Runs hourly via `.github/workflows/pipeline.yml`.

Add these as **GitHub repo secrets**:
- `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` (required)
- `SCOUT_GITHUB_TOKEN` (GitHub PAT, for higher rate limits)
- `PH_API_TOKEN` (Product Hunt developer token)
- `SLACK_WEBHOOK_URL` (optional, for Slack alerts)
- `SMTP_USER` / `SMTP_PASS` / `ALERT_EMAIL_TO` (optional, for email alerts)

Trigger manually: Actions tab -> SCOUT Pipeline -> Run workflow

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/founders?limit=50&offset=0` | Paginated founders, sorted by score desc |
| GET | `/api/founders/{id}` | Single founder detail |
| PATCH | `/api/founders/{id}/status` | Update status (`to_contact`, `watching`, `contacted`, `pass`) |
| GET | `/api/stats` | Dashboard aggregate stats |
| POST | `/api/pipeline/run` | Trigger a full pipeline run |

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `TURSO_DATABASE_URL` | Production | Turso database URL (`libsql://...`) |
| `TURSO_AUTH_TOKEN` | Production | Turso auth token |
| `GITHUB_TOKEN` | Recommended | GitHub PAT for higher API rate limits |
| `PH_API_TOKEN` | Recommended | Product Hunt API token |
| `VITE_API_URL` | Frontend | Backend URL (build-time Vite env var) |
| `SLACK_WEBHOOK_URL` | Optional | Slack alerts |
| `ALERT_SCORE_THRESHOLD` | Optional | Score threshold for alerts (default: 85) |
