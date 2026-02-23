# Gap Analysis: Current Codebase → PRD
**Generated: Feb 2026**

This document maps what exists in the current codebase against the PRD, identifies what must be built, what must change, and what can be kept as-is.

---

## TL;DR

The current codebase is a solid **Scouting layer** (individual founder scoring + CRM). The PRD requires building three entirely new layers on top: **semantic clustering (Themes)**, **anomaly detection (Emergence)**, and a **signal feed UI (Pulse)**. The frontend needs to go from one view to four.

Roughly 30% of what's needed is already built. 70% is new.

---

## What's Already Built ✅

### Backend

| Component | File | Status |
|---|---|---|
| FastAPI server | `backend/api.py` | ✅ Complete |
| Pipeline orchestrator | `backend/pipeline.py` | ✅ Complete (needs modification) |
| 5-dimension scoring engine | `backend/scoring.py` | ✅ Complete — dimensions renamed to match PRD |
| HN scraper | `backend/scrapers/hn.py` | ✅ Keep |
| GitHub scraper | `backend/scrapers/github.py` | ✅ Keep |
| Product Hunt scraper | `backend/scrapers/producthunt.py` | ❌ Out of scope per PRD — remove from detection |
| Database layer (SQLite + Turso) | `backend/db.py` | ✅ Keep — needs schema additions |
| Alert system | `backend/alerts.py` | ✅ Keep |
| Stats snapshots (time-series data) | DB schema | ✅ Good foundation for velocity tracking |
| Signal log | DB schema | ✅ Good foundation for Pulse view |
| Status workflow | DB + API | ✅ Keep — maps directly to Scouting CRM |

### Frontend

| Component | Status | Maps to PRD view |
|---|---|---|
| Founder list + search + filters | ✅ Built | Scouting |
| Founder detail panel (score breakdown, signals, stats) | ✅ Built | Scouting |
| Status management (to_contact → watching → contacted → pass) | ✅ Built | Scouting |
| Live weight tuning (score recalculation) | ✅ Built | Scouting |
| Dark terminal UI / design system | ✅ Built | Reuse across all views |
| Multi-view navigation | ❌ Missing | Themes / Emergence / Pulse / Scouting |

---

## What Must Be Built 🔨

### 1. Semantic Clustering Engine (Themes — Primary View)

**Nothing exists.** This is the biggest build.

**Backend required:**
- `backend/embedder.py` — embed founder content (GitHub README + HN post text) via OpenAI `text-embedding-3-small` or local model
- `backend/clustering.py` — HDBSCAN clustering on founder vectors; detect new theme clusters; compute emergence scores
- `backend/theme_identity.py` — auto-generate the 3 identity fields per theme:
  - **The pain**: synthesize from HN posts + README content (LLM call)
  - **The unlock**: detect tech references (new models, APIs, infra) in recent content
  - **Founder origin**: classify bio keywords (ex-FAANG, researcher, operator, repeat founder)

**DB schema additions required:**
```sql
CREATE TABLE themes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,           -- auto-generated from cluster centroid
    emergence_score INTEGER DEFAULT 0,       -- 0-100 composite
    builder_count   INTEGER DEFAULT 0,
    weekly_velocity REAL DEFAULT 0,          -- delta in cluster size/signal volume
    pain_summary    TEXT DEFAULT '',         -- "What problem are they all describing?"
    unlock_summary  TEXT DEFAULT '',         -- "What recently made this buildable?"
    founder_origin  TEXT DEFAULT '',         -- "Where are these people coming from?"
    first_detected  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE founder_themes (
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    theme_id    INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    similarity  REAL DEFAULT 0,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (founder_id, theme_id)
);

CREATE TABLE founder_embeddings (
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE PRIMARY KEY,
    vector      BLOB NOT NULL,               -- serialized float32 array
    content_hash TEXT NOT NULL,              -- hash of embedded content (for cache invalidation)
    embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE theme_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id    INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    emergence_score INTEGER,
    builder_count   INTEGER,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**API endpoints required:**
- `GET /api/themes` — list all themes, sorted by emergence score
- `GET /api/themes/{id}` — theme detail + all founders in cluster
- `GET /api/themes/{id}/founders` — paginated founders in a theme

**Frontend required:**
- `ThemesView` component — grid of theme cards
- `ThemeCard` — emergence score, builder count, weekly velocity, 3 identity fields
- `ThemeDetail` — expanded view with founder list

---

### 2. Velocity Anomaly Detection (Emergence View)

**Partial foundation exists** (stats_snapshots stores time-series data) but no delta computation or anomaly logic.

**Backend required:**
- `backend/anomaly.py` — compute deltas between consecutive stats_snapshots; flag anomalies:
  - Commit velocity ≥ 2× week-over-week
  - HN engagement > 3 standard deviations from personal baseline
  - Star growth > 15 in 24h on sub-100 star repo
  - New theme cluster detected (≥3 founders converging within 7 days)
- Store anomaly events in DB

**DB schema additions required:**
```sql
CREATE TABLE emergence_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,               -- 'new_theme' | 'founder_inflection'
    entity_id   INTEGER NOT NULL,            -- theme_id or founder_id
    entity_type TEXT NOT NULL,               -- 'theme' | 'founder'
    signal      TEXT NOT NULL,               -- human-readable: "commit velocity 2.4× WoW"
    delta_before REAL,                       -- value before
    delta_after  REAL,                       -- value after
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**API endpoints required:**
- `GET /api/emergence` — recent emergence events, split by new themes vs. inflection founders
- `GET /api/emergence/themes` — new theme clusters in last 7 days
- `GET /api/emergence/founders` — founders whose momentum just spiked

**Frontend required:**
- `EmergenceView` component — two sections: New Themes + Inflection Founders
- `EmergenceCard` — what changed, the delta, time since detection, score at detection

---

### 3. Chronological Signal Feed (Pulse View)

**Foundation exists** (signals table is populated) but no API endpoint or UI for chronological feed.

**Backend required:**
- `GET /api/pulse` — signals from last 48h, all themes + founders, reverse-chron, paginated
  - Params: `hours` (default 48), `limit`, `offset`

**Frontend required:**
- `PulseView` component — simple reverse-chronological feed
- Each row: signal type icon, founder/theme link, raw content, score impact badge, timestamp

---

### 4. Enrichment Gate (Apify + Proxycurl)

**Nothing exists.** Currently no Twitter or LinkedIn enrichment at all, and no threshold gate.

**Backend required:**
- `backend/enrichment/twitter.py` — Apify actor call for Twitter profile (posting freq, engagement, follower trajectory, technical content ratio)
- `backend/enrichment/linkedin.py` — Proxycurl API call for LinkedIn background (employment, education, alumni networks, serial founder flag)
- Gate logic in pipeline: only trigger enrichment when `composite >= 75` and `enriched_at IS NULL`
- Monthly refresh for founders with status `watching` or above

**DB schema additions required:**
```sql
-- Add to founders table:
ALTER TABLE founders ADD COLUMN enriched_at TIMESTAMP;
ALTER TABLE founders ADD COLUMN twitter_handle TEXT DEFAULT '';
ALTER TABLE founders ADD COLUMN twitter_followers INTEGER DEFAULT 0;
ALTER TABLE founders ADD COLUMN twitter_engagement_rate REAL DEFAULT 0;
ALTER TABLE founders ADD COLUMN linkedin_url TEXT DEFAULT '';
ALTER TABLE founders ADD COLUMN linkedin_summary TEXT DEFAULT '';
ALTER TABLE founders ADD COLUMN is_serial_founder BOOLEAN DEFAULT 0;
ALTER TABLE founders ADD COLUMN first_detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE founders ADD COLUMN contacted_at TIMESTAMP;

-- Add to .env.example:
APIFY_API_TOKEN=
PROXYCURL_API_KEY=
ENRICHMENT_SCORE_THRESHOLD=75
```

---

### 5. Notes Field (Scouting CRM)

**Missing from DB and UI.**

```sql
ALTER TABLE founders ADD COLUMN notes TEXT DEFAULT '';
```

API: `PATCH /api/founders/{id}/notes` — update notes field

Frontend: editable textarea in DetailPanel

---

### 6. Frontend Navigation (4 Views)

**Currently a single-view app.** Needs nav bar + 4 route-like view states.

```
Header nav: [THEMES] [EMERGENCE] [PULSE] [SCOUTING]
```

No router needed — view state managed in React. Each view is a component lazy-loaded.

---

## What Must Change 🔄

### Remove Product Hunt from Detection

Per PRD: "Product Hunt scraping — low signal-to-noise for pre-emergence detection — Out of Scope V1"

- Remove `scrape_producthunt` from pipeline Phase 1
- Keep PH data that's already in DB (don't delete)
- Remove PH from source filter in UI (or mark as "legacy")
- Keep PH scraper file for potential V2

### Pipeline Phase Order

Current pipeline: Scrape → Enrich → Score → Alert

New pipeline: Scrape (HN + GH only) → Embed → Cluster → Score → Anomaly Detection → Enrichment Gate → Alert

Add `embed_founders()` and `run_clustering()` phases between scraping and scoring.

### Scoring Weights

PRD specifies: Momentum 25%, Domain 20%, Team 15%, Traction 25%, YC Fit 15%

Current backend has been renamed to: founder_quality (30%), execution_velocity (25%), market_conviction (15%), early_traction (20%), deal_availability (10%)

The *dimension logic* is equivalent but weights differ. Update `DEFAULT_WEIGHTS` in `scoring.py` to match PRD:

```python
DEFAULT_WEIGHTS = {
    "founder_quality": 0.25,     # Momentum
    "execution_velocity": 0.20,  # Domain
    "market_conviction": 0.15,   # Team
    "early_traction": 0.25,      # Traction
    "deal_availability": 0.15,   # YC Fit
}
```

Also update in `App.jsx`.

---

## What Can Stay As-Is ✅

- All DB infrastructure (SQLite/Turso abstraction)
- HN scraper
- GitHub scraper
- Alert system (Slack/email)
- Scoring engine logic (just weights change)
- Status workflow
- Design system (colors, fonts, components)
- Founder card + detail panel (Scouting view)
- Weight tuning UI
- API caching layer
- GitHub Actions pipeline YAML

---

## Build Order (Recommended Sequence)

```
Phase 1 — Data foundation (no UI yet)
  1a. Add schema: themes, founder_themes, founder_embeddings, theme_history, emergence_events
  1b. Build backend/embedder.py — embed founder content
  1c. Build backend/clustering.py — HDBSCAN clustering + theme detection
  1d. Wire into pipeline (add embed + cluster phases)
  1e. Build backend/anomaly.py — velocity delta + anomaly flagging

Phase 2 — API layer
  2a. GET /api/themes, /api/themes/{id}
  2b. GET /api/emergence (new themes + inflection founders)
  2c. GET /api/pulse (48h signal feed)
  2d. PATCH /api/founders/{id}/notes
  2e. Enrichment gate endpoints

Phase 3 — Enrichment
  3a. backend/enrichment/twitter.py (Apify)
  3b. backend/enrichment/linkedin.py (Proxycurl)
  3c. Gate logic in pipeline

Phase 4 — Frontend
  4a. Navigation bar (4 views)
  4b. PulseView (easiest — signals already exist)
  4c. EmergenceView (anomaly events from Phase 1e)
  4d. ThemesView + ThemeCard + ThemeDetail (biggest build)
  4e. Notes field in Scouting detail panel
  4f. Enrichment data in Scouting detail panel

Phase 5 — Polish
  5a. Theme identity LLM generation (pain/unlock/origin)
  5b. Auto-naming of theme clusters
  5c. Score weight alignment
  5d. Remove PH from detection pipeline
```

---

## New Dependencies Required

```txt
# backend/requirements.txt additions
scikit-learn>=1.4     # HDBSCAN clustering
numpy>=1.26           # Vector math
openai>=1.0           # Embeddings (text-embedding-3-small)
httpx                 # Already present — used for Apify/Proxycurl calls
```

Optional (if avoiding OpenAI):
```txt
sentence-transformers  # Local embeddings (larger install, no API cost)
```

---

## Effort Estimate

| Phase | Effort | Blocker |
|---|---|---|
| Schema additions | 1h | None |
| Embedder | 2h | OpenAI API key (or local model) |
| Clustering engine | 4h | Embedder |
| Anomaly detection | 3h | Stats snapshots (already accumulating) |
| API layer | 3h | Schema + clustering |
| Enrichment (Apify + Proxycurl) | 4h | API keys |
| Frontend — Nav + Pulse | 2h | API |
| Frontend — Emergence | 3h | Anomaly API |
| Frontend — Themes | 6h | Themes API |
| Polish + testing | 3h | All of above |
| **Total** | **~31h** | |
