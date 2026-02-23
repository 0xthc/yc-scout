# Product Requirements Document: SCOUT V3 — Private VC Intelligence Platform

**Version**: 3.0
**Date**: 2026-02-23
**Author**: Generated from founder brief + codebase analysis
**Status**: Draft for review

---

## 1. Executive Summary

SCOUT V3 is a private intelligence tool for a micro VC operator. Its purpose is to surface investment-ready founders and emerging themes **6–18 months before** they become visible to YC, press, or other investors.

The system does not filter a known list. It watches for things that are **about to emerge** — clusters of unrelated founders independently building in the same direction, momentum inflections in individual projects, and behavioral patterns that predict breakout founders before they have a company name.

### What changes from V2

| Dimension | V2 (Current) | V3 (Target) |
|-----------|--------------|--------------|
| **Primary unit** | Individual founders | Emerging themes (clusters of founders) |
| **Main view** | Flat ranked list sorted by score | Theme clusters with emergence signals |
| **Detection model** | Score-and-rank | Cluster-detect-then-score |
| **Data sources** | GitHub + HN + Product Hunt | GitHub + HN (primary) → Apify/Proxycurl (enrichment on threshold) |
| **Views** | 1 (founder list + detail) | 4 (Themes, Emergence, Pulse, Scouting) |
| **Update model** | Hourly full pipeline | Continuous collection + periodic clustering |
| **Intelligence layer** | Scoring only | Scoring + semantic clustering + anomaly detection |

### What stays the same

- 5-dimension scoring engine (founder_quality, execution_velocity, market_conviction, early_traction, deal_availability)
- Dark terminal UI aesthetic
- FastAPI + React + Turso stack
- GitHub Actions pipeline infrastructure
- HN and GitHub as primary data sources

---

## 2. Problem Statement

Most VCs see founders **after** they've been accepted to YC, covered in TechCrunch, or already raising. By then, signal-to-noise is terrible and competition for allocation is fierce.

A micro VC's edge is **getting there first**. That requires:

1. **Theme detection** — recognizing that 5 unrelated people are building toward the same pain point before anyone has named the category
2. **Momentum sensing** — catching the moment a project inflects from hobby to serious, before the founder themselves may realize it
3. **Identity enrichment** — once flagged, answering "who is this person really?" fast enough to reach out while they're still accessible

The current V2 system scores and ranks individual founders. V3 shifts the primary lens from "who is good" to "what is emerging" — and uses founder scoring as a dimension within that higher-order question.

---

## 3. The Four Views

### 3.1 Themes (Primary View)

**Purpose**: Answer "What problem spaces are heating up right now?"

A theme is a cluster of unrelated founders independently building in the same direction. Themes are not manually defined — they are **detected automatically** from semantic clustering of founder activity, repo descriptions, HN posts, and signal content.

#### What's displayed per theme

| Field | Description | Source |
|-------|-------------|--------|
| **Theme name** | Auto-generated label (e.g., "Browser-native AI agents", "Vertical payroll APIs") | LLM summarization of cluster centroid |
| **Emergence score** | 0–100 composite of cluster strength, velocity, and novelty | Clustering engine |
| **Builder count** | Number of distinct founders in this cluster | Cluster membership |
| **Weekly velocity** | How fast is this cluster growing? (new builders, new signals) | Delta over rolling 7-day window |
| **Pain described** | What specific problem are these founders all describing? | Extracted from HN posts, repo READMEs, bios |
| **Why now** | What recently made this buildable? (new API, regulation change, cost drop) | Extracted from signal content + temporal analysis |
| **Founder origins** | Where did these builders come from? (ex-Stripe, academia, specific geo) | Bio/profile analysis |

#### Interaction model

- Themes sorted by emergence score (default) or weekly velocity
- Click theme → expand to see constituent founders with their individual scores
- Each founder row shows: name, primary source, individual score, top signal, stage
- Filter themes by: minimum builder count, minimum emergence score, time window
- Search across theme names and pain descriptions

#### Theme lifecycle

| State | Criteria |
|-------|----------|
| **Nascent** | 2–3 builders, weak signals, just detectable |
| **Emerging** | 4–7 builders, accelerating velocity, clear pain convergence |
| **Established** | 8+ builders, press coverage appearing, VCs tweeting about it |
| **Saturated** | Well-known category, YC batch has 5+ companies in space |

The value is in Nascent and Emerging. Established and Saturated themes are shown for context but deprioritized.

---

### 3.2 Emergence (Anomaly View)

**Purpose**: Answer "What just crossed a threshold that wasn't on my radar yesterday?"

This is the **delta view** — you open it to see what moved, not what exists.

#### Two types of emergence events

**1. New theme clusters**
- A cluster that just became detectable (crossed from noise to Nascent)
- Shown with: theme name, initial builder count, triggering signals, confidence level

**2. Individual momentum inflections**
- A project whose velocity just spiked (commit cadence doubled, star count hockey-sticked, HN post blew up)
- Shown with: founder name, before/after metrics, triggering event, current theme (if any)

#### What's displayed

| Field | Description |
|-------|-------------|
| **Event type** | "New Theme" or "Momentum Spike" |
| **Timestamp** | When the threshold was crossed |
| **Entity** | Theme name or founder name |
| **Trigger** | What specific signal caused the crossing |
| **Before → After** | Quantitative delta (e.g., "12 stars → 340 stars in 48h") |
| **Confidence** | How likely is this a real signal vs. noise (low/medium/high) |

#### Interaction model

- Chronological list, most recent first
- Default window: last 7 days
- Filter by: event type, confidence level, time window
- Click event → navigate to theme detail or founder detail
- Mark events as "Noted" or "Investigating" to track what you've reviewed

---

### 3.3 Pulse (Raw Signal Feed)

**Purpose**: Daily scan of every signal that fired across all themes and projects.

This is the **firehose view** — less curated, faster to scan. You check it daily to maintain ambient awareness.

#### What's displayed per signal

| Field | Description |
|-------|-------------|
| **Timestamp** | When the signal was detected |
| **Source icon** | GitHub / HN |
| **Signal type** | Show HN, new repo, star spike, commit burst, HN post, etc. |
| **Label** | Human-readable description (e.g., "Show HN: AcmePay — 847 pts") |
| **Founder** | Linked founder name (if attributed) |
| **Theme** | Linked theme name (if the founder belongs to a cluster) |
| **Strength** | Strong / Normal indicator |
| **URL** | Direct link to the source |

#### Interaction model

- Default window: last 48 hours
- Infinite scroll with lazy loading
- Filter by: source (GitHub/HN), strength (strong only), theme, time window
- Quick actions: click founder name → Scouting detail, click theme → Themes detail
- Keyboard-friendly: j/k navigation, Enter to open URL

---

### 3.4 Scouting (CRM View)

**Purpose**: Manage specific founders who've surfaced through the system and are ready for outreach.

This is the **last mile** — not the detection layer. A founder appears here only after the system has flagged them through Themes or Emergence, and optionally after enrichment has filled in their Twitter/LinkedIn.

#### What's displayed per founder

| Field | Description | Source |
|-------|-------------|--------|
| **Name & handle** | Full name, primary handle | Profile scraping |
| **Avatar** | Profile photo or initials | GitHub/HN |
| **Score** | Composite + 5-dimension breakdown | Scoring engine |
| **Stage** | Pre-seed / Seed / Series A | Inferred from signals |
| **Theme** | Which emerging theme(s) they belong to | Clustering engine |
| **Status** | New / Watching / To Contact / Contacted / Pass | User-set CRM state |
| **Top signals** | 3 most significant signals with timestamps | Signal feed |
| **GitHub** | Stars, repos, commit cadence, top repo | GitHub scraper |
| **HN** | Karma, top post, submission frequency | HN scraper |
| **Twitter** | Follower count, posting frequency, bio | Apify (enrichment only) |
| **LinkedIn** | Current role, past companies, education | Proxycurl (enrichment only) |
| **Contact** | Email, Twitter DM, LinkedIn URL | Enrichment |
| **Notes** | Free-text internal notes | User input |

#### Interaction model

- List view with sort by: score, status, theme, last signal date
- Filter by: status, theme, score range, source platform
- Detail panel (right side, same pattern as V2) with full profile
- Status cycling: New → Watching → To Contact → Contacted → Pass
- "Enrich" button: triggers Apify + Proxycurl fetch for a specific founder
- "Reach out" templates: pre-filled email/DM based on founder signals
- Batch operations: bulk status change, bulk enrich
- Weight tuning sliders (carried over from V2)

---

## 4. Data Architecture

### 4.1 Data Sources & Access Patterns

```
┌─────────────────────────────────────────────────────────┐
│                    PRIMARY SOURCES                        │
│              (drive detection, run always)                │
│                                                          │
│   ┌─────────┐           ┌─────────┐                     │
│   │ GitHub  │           │   HN    │                     │
│   │  API    │           │ Algolia │                     │
│   └────┬────┘           └────┬────┘                     │
│        │                     │                           │
│        │  behavioral         │  language                 │
│        │  signals            │  signals                  │
│        ▼                     ▼                           │
│   ┌──────────────────────────────────┐                  │
│   │       PROCESSING ENGINE          │                  │
│   │                                  │                  │
│   │  1. Semantic clustering          │                  │
│   │     (detect emerging themes)     │                  │
│   │                                  │                  │
│   │  2. 5-dimension scoring          │                  │
│   │     (score each founder)         │                  │
│   │                                  │                  │
│   │  3. Anomaly detection            │                  │
│   │     (velocity spikes, new        │                  │
│   │      cluster formation)          │                  │
│   └──────────────┬───────────────────┘                  │
│                  │                                        │
│     detection    │  threshold crossed?                    │
│                  ▼                                        │
├─────────────────────────────────────────────────────────┤
│                 ENRICHMENT SOURCES                        │
│          (profile fill, run on-demand)                    │
│                                                          │
│   ┌──────────┐           ┌────────────┐                 │
│   │  Apify   │           │ Proxycurl  │                 │
│   │ (Twitter)│           │ (LinkedIn) │                 │
│   └─────┬────┘           └─────┬──────┘                 │
│         │                      │                         │
│         ▼                      ▼                         │
│   ┌──────────────────────────────────┐                  │
│   │       ENRICHED PROFILES          │                  │
│   │  (who is this person really?)    │                  │
│   └──────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │    FOUR VIEWS         │
              │                       │
              │  Themes │ Emergence   │
              │  Pulse  │ Scouting    │
              └───────────────────────┘
```

### 4.2 GitHub — Behavioral Signals

**What we collect** (already built in `backend/scrapers/github.py`):

| Signal | What it tells us | Current implementation |
|--------|-----------------|----------------------|
| Commit cadence (90-day) | Are they actively building? | `commits_90d` via GitHub Events API |
| Repo creation velocity | Are they shipping new things? | Search API: created in last 30 days |
| Star velocity | Is the market noticing? | Stars count + delta tracking |
| Production-grade patterns | Serious project vs. toy? | Repo size, CI presence, license |
| Topic tags | What domain are they in? | Repo topics → `founder_tags` |
| Profile metadata | Who are they? | Bio, company, location, followers |

**What's new for V3**:

| New signal | Purpose | Implementation |
|------------|---------|----------------|
| README semantic content | Input to clustering engine | Fetch README.md, extract key sentences |
| Repo description embeddings | Semantic similarity for theme clustering | Embed descriptions via sentence-transformers |
| Dependency analysis (package.json, requirements.txt) | Technology convergence detection | Parse manifest files from top repos |
| Issue/discussion activity | Community engagement signal | GitHub Issues API |

### 4.3 Hacker News — Language Signals

**What we collect** (already built in `backend/scrapers/hn.py`):

| Signal | What it tells us | Current implementation |
|--------|-----------------|----------------------|
| Show HN posts | They're shipping something | Algolia search, 50+ points |
| Post content | What pain are they describing? | Post title + URL |
| Karma trajectory | Community standing | Firebase user API |
| Comment content | Domain expertise, pain awareness | Not yet — text only via Algolia |

**What's new for V3**:

| New signal | Purpose | Implementation |
|------------|---------|----------------|
| Comment text on relevant threads | Pain language extraction for clustering | Algolia comment search by user |
| "Ask HN" / pain posts | What problems are they articulating? | Search for non-Show-HN posts by flagged users |
| Writing consistency | Long-term conviction signal | Submission frequency over 6+ months |
| Thread participation patterns | Domain obsession detection | Which topics do they repeatedly engage with? |

### 4.4 Enrichment Sources (New)

Enrichment fires **only after** a founder crosses a detection threshold from primary sources.

#### Apify (Twitter/X)

| Data point | Purpose |
|------------|---------|
| Follower count | Public profile size (deal_availability inverse signal) |
| Posting frequency | Activity / building-in-public signal |
| Bio | Company/role info, links |
| Recent tweets | Content analysis for theme alignment |

**Trigger**: Founder composite score ≥ 60 OR belongs to Emerging+ theme
**API**: Apify Twitter Scraper actor
**Cost**: ~$5/1000 profiles on Apify pay-per-result

#### Proxycurl (LinkedIn)

| Data point | Purpose |
|------------|---------|
| Current role + company | Stage inference, is this a side project or full-time? |
| Past companies | Founder quality signal (ex-FAANG, ex-startup) |
| Education | Domain expertise signal |
| Connections count | Network signal |
| Skills endorsements | Technical depth signal |

**Trigger**: Founder composite score ≥ 70 OR status set to "Watching" / "To Contact"
**API**: Proxycurl Person Profile API
**Cost**: ~$0.03/profile

### 4.5 Product Hunt — Removed from Primary Sources

Product Hunt is **deprioritized** in V3. Rationale:

1. PH launches happen *after* a product is built — too late for 6–18 month lead time
2. PH is noisy — many non-technical launches, marketing-driven products
3. The PH scraper (`backend/scrapers/producthunt.py`) remains in codebase but is not part of the primary collection loop
4. PH signals can be re-enabled as an enrichment source for known founders

---

## 5. Processing Engine (New)

The processing engine is the core new component in V3. It sits between data collection and the four views.

### 5.1 Semantic Clustering

**Purpose**: Automatically detect emerging themes by grouping founders building in similar directions.

#### Input

For each founder, build a **semantic profile** from:
- GitHub repo descriptions and README excerpts
- HN post titles and comment content
- Bio and self-described domain
- Repo topics and tags
- Signal labels

#### Method

1. **Embed** each founder's semantic profile using a sentence embedding model (e.g., `all-MiniLM-L6-v2` via sentence-transformers, runs locally)
2. **Cluster** embeddings using HDBSCAN (density-based, auto-determines cluster count, handles noise)
3. **Label** each cluster using LLM summarization of the cluster's most representative texts
4. **Score** each cluster on emergence dimensions (see 5.2)

#### Clustering parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `min_cluster_size` | 3 | A theme needs at least 3 independent builders to be meaningful |
| `min_samples` | 2 | Allow loose clusters in early stages |
| `cluster_selection_epsilon` | 0.3 | Balance between too many micro-clusters and too few mega-clusters |
| `metric` | cosine | Standard for text embeddings |

#### Output: `themes` table (new)

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `name` | TEXT | Auto-generated theme label |
| `description` | TEXT | 1-2 sentence summary |
| `pain_described` | TEXT | What pain are founders describing? |
| `why_now` | TEXT | What recently made this buildable? |
| `founder_origins` | TEXT | Where did these builders come from? |
| `emergence_score` | REAL | 0-100 composite |
| `builder_count` | INTEGER | Number of founders in cluster |
| `weekly_velocity` | REAL | Growth rate |
| `lifecycle` | TEXT | nascent / emerging / established / saturated |
| `centroid_embedding` | BLOB | For similarity queries |
| `created_at` | TIMESTAMP | When theme was first detected |
| `updated_at` | TIMESTAMP | Last reclustering |

#### Output: `theme_members` table (new)

| Column | Type | Description |
|--------|------|-------------|
| `theme_id` | TEXT FK | Reference to themes |
| `founder_id` | TEXT FK | Reference to founders |
| `similarity_score` | REAL | How close to cluster centroid |
| `joined_at` | TIMESTAMP | When founder was added to this theme |

### 5.2 Theme Emergence Scoring

Each theme gets an **emergence score** (0-100) computed from:

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| **Cluster density** | 25% | How tightly correlated are the founders' work? (average pairwise similarity) |
| **Builder velocity** | 25% | How fast is the cluster growing? (new members per week) |
| **Signal intensity** | 20% | How strong are the constituent founders' signals? (average founder score) |
| **Independence** | 20% | Are builders truly independent? (different companies, locations, backgrounds) |
| **Novelty** | 10% | Is this a new pattern or well-known category? (inverse of press/VC mention frequency) |

### 5.3 Anomaly Detection

**Purpose**: Detect threshold crossings that should trigger Emergence events.

#### Theme-level anomalies

| Anomaly | Detection method | Threshold |
|---------|-----------------|-----------|
| New cluster formation | HDBSCAN detects new cluster that didn't exist in previous run | cluster_size ≥ 3 |
| Cluster growth spike | Builder count delta exceeds 2σ of historical weekly growth | > 2 standard deviations |
| Cluster densification | Average pairwise similarity increases sharply | > 0.1 increase in one cycle |

#### Founder-level anomalies

| Anomaly | Detection method | Threshold |
|---------|-----------------|-----------|
| Star velocity spike | GitHub stars delta in 48h exceeds 10× 30-day average daily rate | 10× baseline |
| Commit burst | 90-day commit count jumps > 50% between cycles | > 50% increase |
| HN breakout | Single post exceeds 200 points (already in V2 as "strong signal") | 200+ points |
| Score inflection | Composite score increases > 15 points in one cycle | > 15 point delta |
| Multi-platform emergence | Founder detected on 2nd platform within 7 days | Cross-source within window |

#### Output: `emergence_events` table (new)

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `event_type` | TEXT | new_theme / theme_spike / momentum_spike / score_inflection / multi_platform |
| `entity_type` | TEXT | theme / founder |
| `entity_id` | TEXT | Reference to theme or founder |
| `trigger_description` | TEXT | Human-readable: "Stars went from 12 to 340 in 48h" |
| `before_value` | REAL | Quantitative before |
| `after_value` | REAL | Quantitative after |
| `confidence` | TEXT | low / medium / high |
| `status` | TEXT | new / noted / investigating |
| `detected_at` | TIMESTAMP | When the anomaly was detected |

---

## 6. Updated Database Schema

### 6.1 Existing tables (kept from V2)

- `founders` — add `twitter_handle TEXT`, `linkedin_url TEXT`, `enriched_at TIMESTAMP`
- `founder_sources` — no changes
- `founder_tags` — no changes
- `signals` — add `embedding BLOB` for semantic search
- `stats_snapshots` — add `twitter_followers INTEGER`, `twitter_posts_30d INTEGER`
- `scores` — no changes
- `alert_log` — no changes

### 6.2 New tables

- `themes` — cluster definitions with emergence scores (see 5.1)
- `theme_members` — founder-to-theme mapping with similarity scores (see 5.1)
- `emergence_events` — anomaly log (see 5.3)
- `founder_embeddings` — cached semantic profile embeddings

| Column | Type | Description |
|--------|------|-------------|
| `founder_id` | TEXT PK | Reference to founders |
| `embedding` | BLOB | Sentence embedding vector |
| `source_text` | TEXT | Concatenated text that was embedded |
| `computed_at` | TIMESTAMP | When embedding was last computed |

- `enrichment_queue` — track enrichment requests

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `founder_id` | TEXT FK | Reference to founders |
| `source` | TEXT | apify_twitter / proxycurl_linkedin |
| `status` | TEXT | pending / in_progress / completed / failed |
| `triggered_by` | TEXT | score_threshold / manual / theme_membership |
| `requested_at` | TIMESTAMP | |
| `completed_at` | TIMESTAMP | |

---

## 7. API Changes

### 7.1 New Endpoints

```
GET  /api/themes
     ?sort=emergence_score|velocity|builder_count
     &lifecycle=nascent,emerging
     &min_builders=3
     &min_score=40
     &limit=20&offset=0
     → { themes: [...], total, limit, offset }

GET  /api/themes/{id}
     → { theme, founders: [...] }

GET  /api/emergence
     ?event_type=new_theme,momentum_spike
     &confidence=medium,high
     &days=7
     &limit=50&offset=0
     → { events: [...], total, limit, offset }

PATCH /api/emergence/{id}/status
      body: { status: "noted" | "investigating" }
      → { ok: true }

GET  /api/pulse
     ?hours=48
     &source=github,hn
     &strength=strong
     &theme_id=xxx
     &limit=100&offset=0
     → { signals: [...], total, limit, offset }

GET  /api/founders  (updated)
     — add: ?theme_id=xxx filter
     — add: theme field in response
     → { founders: [...], total, limit, offset }

POST /api/founders/{id}/enrich
     body: { sources: ["twitter", "linkedin"] }
     → { queued: true, enrichment_id: "xxx" }

GET  /api/founders/{id}/enrichment-status
     → { twitter: "completed", linkedin: "pending" }
```

### 7.2 Updated Endpoints

```
GET  /api/stats (updated)
     — add: active_themes, nascent_themes, emergence_events_7d
     → { total_founders, strong_signal, to_contact, avg_score,
         active_themes, nascent_themes, emergence_events_7d }

POST /api/pipeline/run (updated)
     — add optional body: { phases: ["collect", "cluster", "score", "detect"] }
     — default: run all phases
```

---

## 8. Frontend Architecture

### 8.1 Navigation

Replace the single-view layout with a **tabbed navigation** at the top:

```
┌──────────────────────────────────────────────────────────────────┐
│  SCOUT  [VC Intelligence]          [stats pills]      [LIVE •]  │
├──────────────────────────────────────────────────────────────────┤
│  ◉ Themes    ○ Emergence    ○ Pulse    ○ Scouting               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│                     [Active view content]                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

- Maintain the existing dark terminal aesthetic (#06060e background, #7c3aed accent)
- Tab indicators show unread counts (e.g., "Emergence (3)")
- URL-based routing: `/themes`, `/emergence`, `/pulse`, `/scouting`

### 8.2 Themes View Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Search themes...]  [Lifecycle: All ▾]  [Sort: Emergence ▾] │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│  ┌────────────────┐  │  THEME DETAIL                    │
│  │ ▲ Browser-     │  │                                  │
│  │   native AI    │  │  "Browser-native AI agents"      │
│  │   agents       │  │  Emergence: 82  Builders: 6      │
│  │   ●82  6 bldrs │  │  Velocity: +3/wk                 │
│  │   +3/wk  ↗     │  │                                  │
│  └────────────────┘  │  PAIN: "Browser automation is     │
│  ┌────────────────┐  │  still scriptable but not         │
│  │   Vertical     │  │  intelligent..."                  │
│  │   payroll APIs │  │                                  │
│  │   ●74  4 bldrs │  │  WHY NOW: "GPT-4V made visual    │
│  │   +1/wk       │  │  understanding viable; Playwright │
│  └────────────────┘  │  standardized browser control"    │
│  ┌────────────────┐  │                                  │
│  │   Compliance   │  │  ORIGINS: "3 ex-Google Chrome     │
│  │   automation   │  │  team, 1 ex-Selenium maintainer,  │
│  │   ●68  3 bldrs │  │  2 indie devtools builders"       │
│  │   +2/wk       │  │                                  │
│  └────────────────┘  │  ──── FOUNDERS IN THEME ────      │
│                      │                                  │
│  [more themes...]    │  [Founder cards with scores,      │
│                      │   signals, and actions]           │
│                      │                                  │
└──────────────────────┴──────────────────────────────────┘
```

### 8.3 Emergence View Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Type: All ▾]  [Confidence: Med+ ▾]  [Window: 7 days ▾]    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⬆ NEW THEME                              2h ago       │
│  "Compliance automation for crypto exchanges"           │
│  3 independent builders detected · Confidence: HIGH     │
│  [View Theme →]                    [Noted] [Investigate]│
│  ─────────────────────────────────────────────────────  │
│  ⚡ MOMENTUM SPIKE                         6h ago       │
│  @aiko-tanaka · "AcmePay" repo                         │
│  Stars: 45 → 1,200 in 48h · Commits: 12/day           │
│  Theme: Vertical payroll APIs                           │
│  [View Founder →]                  [Noted] [Investigate]│
│  ─────────────────────────────────────────────────────  │
│  ⬆ NEW THEME                              1d ago       │
│  "Browser-native AI agents"                             │
│  4 builders in initial cluster · Confidence: MEDIUM     │
│  [View Theme →]                    [Noted] [Investigate]│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.4 Pulse View Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Source: All ▾]  [Strength: All ▾]  [48h ▾]  [Search] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  14:23  ◆ GH  Show HN: AcmePay — instant payroll API   │
│              @aiko-tanaka · Vertical payroll APIs  KEY  │
│                                                         │
│  14:01  ◆ GH  New repo: browser-agent-sdk (★ 23)       │
│              @mwebb · Browser-native AI agents          │
│                                                         │
│  13:45  ◆ HN  "Why I quit Google to build compliance    │
│              tooling" — 312 pts                          │
│              @cryptodev42 · Compliance automation   KEY │
│                                                         │
│  12:30  ◆ GH  Commit burst: 847 commits in 14 days     │
│              @priya-nair · ML compiler optimization     │
│                                                         │
│  [infinite scroll...]                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.5 Scouting View Layout

Evolves the current V2 founder list view with additions:

- Theme tag on each founder card
- Enrichment status indicator (enriched / pending / not enriched)
- "Enrich" action button
- Notes field in detail panel
- Contact methods section (email, Twitter, LinkedIn)
- Outreach template generator

---

## 9. Implementation Plan

### Phase 0: Thin End-to-End Slice (Recommended First Move)

**Goal**: One collector → minimal processing → real data appearing in the interface.

This validates the full data-to-display chain before building the processing engine.

| Step | What | Details |
|------|------|---------|
| 0.1 | Run HN collector against live Algolia | The collector code is written. Deploy it to collect real data into local SQLite. |
| 0.2 | Run existing scorer on collected data | V2 scoring engine works. Score the real founders. |
| 0.3 | Verify `/api/founders` returns real data | Confirm the API serves real scraped + scored founders. |
| 0.4 | Display in current V2 frontend | Confirm real data renders correctly in the existing UI. |
| 0.5 | Add a minimal static "Themes" tab | Hardcode 2-3 themes from manual inspection of collected data. Wire the tab navigation. |

**Success criteria**: Real HN founders visible in the UI with real scores. One manually-curated theme visible in a new tab. The full loop from scrape → store → score → serve → render is proven.

### Phase 1: GitHub Collector + Storage Layer

| Step | What | Details |
|------|------|---------|
| 1.1 | Deploy HN collector to run on schedule | GitHub Actions cron, writing to Turso |
| 1.2 | Deploy GitHub collector to run on schedule | Same pipeline, staggered timing |
| 1.3 | Implement cross-platform dedup | Use existing `enrich.py` reconciliation logic |
| 1.4 | Validate data accumulation | Confirm founders + signals growing over days |

### Phase 2: Semantic Clustering Engine

| Step | What | Details |
|------|------|---------|
| 2.1 | Add `founder_embeddings` table | Schema migration |
| 2.2 | Build embedding pipeline | Collect semantic text per founder → embed with sentence-transformers |
| 2.3 | Implement HDBSCAN clustering | Cluster embeddings, output theme assignments |
| 2.4 | Add `themes` + `theme_members` tables | Schema migration |
| 2.5 | Build theme labeling | LLM call to generate theme name, pain, why_now, origins |
| 2.6 | Add `/api/themes` endpoint | Serve theme data to frontend |
| 2.7 | Build Themes view in frontend | Replace static themes with live clustered data |

### Phase 3: Anomaly Detection + Emergence

| Step | What | Details |
|------|------|---------|
| 3.1 | Add `emergence_events` table | Schema migration |
| 3.2 | Build threshold detection logic | Compare current vs. previous cycle for all anomaly types |
| 3.3 | Add `/api/emergence` endpoint | Serve emergence events |
| 3.4 | Build Emergence view in frontend | Chronological event list with actions |
| 3.5 | Integrate with existing alert system | High-confidence emergence events trigger Slack/email |

### Phase 4: Pulse + Scouting Views

| Step | What | Details |
|------|------|---------|
| 4.1 | Add `/api/pulse` endpoint | Serve signals with theme attribution |
| 4.2 | Build Pulse view in frontend | Raw signal feed with filters |
| 4.3 | Evolve Scouting view from V2 list | Add theme tags, enrichment UI, notes, contacts |
| 4.4 | Add keyboard navigation | j/k/Enter for power-user scanning |

### Phase 5: Enrichment Layer

| Step | What | Details |
|------|------|---------|
| 5.1 | Add `enrichment_queue` table | Schema migration |
| 5.2 | Integrate Apify Twitter actor | On-demand Twitter profile fetch |
| 5.3 | Integrate Proxycurl LinkedIn API | On-demand LinkedIn profile fetch |
| 5.4 | Add enrichment triggers | Auto-enrich on score threshold or manual button |
| 5.5 | Display enrichment data in Scouting view | Twitter/LinkedIn sections in founder detail |
| 5.6 | Feed enrichment data back to scoring | Adjust founder_quality and deal_availability with new signals |

### Phase 6: Polish + Operational Maturity

| Step | What | Details |
|------|------|---------|
| 6.1 | Reclustering schedule | Run clustering every 6 hours, not every pipeline cycle |
| 6.2 | Theme lifecycle management | Auto-transition themes between lifecycle stages |
| 6.3 | Emergence event dedup | Don't re-fire the same anomaly within a cooldown window |
| 6.4 | Dashboard performance | Optimize for 1000+ founders, 50+ themes |
| 6.5 | Monitoring + observability | Pipeline health dashboard, error rates, data freshness |

---

## 10. Technical Decisions

### 10.1 Embedding Model

**Recommendation**: `all-MiniLM-L6-v2` via `sentence-transformers`

| Criterion | Decision |
|-----------|----------|
| Runs locally | Yes — no API cost, no rate limits |
| Embedding dimension | 384 — small enough to store in SQLite BLOB |
| Quality | Strong for short text similarity (repo descriptions, bios) |
| Speed | ~100 embeddings/sec on CPU |
| Alternative considered | OpenAI `text-embedding-3-small` — better quality but adds API dependency and cost |

### 10.2 Clustering Algorithm

**Recommendation**: HDBSCAN

| Criterion | Decision |
|-----------|----------|
| Auto-determines cluster count | Yes — critical since we don't know how many themes exist |
| Handles noise | Yes — not every founder belongs to a theme, and that's fine |
| Density-based | Yes — finds natural groupings, not forced partitions |
| Incremental updates | Partial — can use `approximate_predict` for new points, full recluster periodically |
| Alternative considered | K-means — requires specifying k, forces all points into clusters |

### 10.3 Theme Labeling

**Recommendation**: Claude API (Haiku) for cost efficiency

- Input: Top 5 most representative texts from cluster (closest to centroid)
- Output: Theme name, pain_described, why_now, founder_origins
- Cost: ~$0.001 per theme labeling call
- Frequency: Only on new cluster formation or significant membership change

### 10.4 Enrichment Architecture

**Recommendation**: Async queue with background worker

- Enrichment requests go into `enrichment_queue` table
- Background worker picks up pending requests, calls Apify/Proxycurl
- Results written back to `founders` + `stats_snapshots`
- Frontend polls enrichment status
- Rate limiting: 1 request/sec for Apify, 1 request/2sec for Proxycurl

### 10.5 Frontend Routing

**Recommendation**: Hash-based routing (no library dependency)

- `#/themes`, `#/emergence`, `#/pulse`, `#/scouting`
- Keep the single-file `App.jsx` pattern but split view logic into clearly separated render functions
- Consider extracting to separate files only if `App.jsx` exceeds ~1500 lines

---

## 11. Success Metrics

### Detection Quality

| Metric | Target | How to measure |
|--------|--------|----------------|
| Theme detection lead time | 6+ months before TechCrunch coverage | Compare theme detection date vs. first press mention |
| Founder detection lead time | 3+ months before YC application | Compare detection date vs. YC batch announcement |
| False positive rate (themes) | <30% of themes should be noise | Manual review of detected themes weekly |
| False positive rate (founders) | <20% of "To Contact" founders are irrelevant | Track conversion from "To Contact" to "Contacted" |

### Operational

| Metric | Target | How to measure |
|--------|--------|----------------|
| Pipeline reliability | 99%+ successful runs | GitHub Actions success rate |
| Data freshness | <2 hours stale | Time since last successful pipeline run |
| API response time | <500ms p95 | Backend logging |
| Enrichment queue drain time | <1 hour for batch of 20 | Queue monitoring |

### Usage

| Metric | Target | How to measure |
|--------|--------|----------------|
| Daily active check | 1x/day minimum | Frontend analytics (optional) |
| Founders contacted per week | 2-5 via Scouting view | Status transition tracking |
| Themes being watched | 3-8 active at any time | Theme interaction tracking |

---

## 12. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Clustering produces garbage themes | Medium | High | Start with manual review of all themes; tune HDBSCAN params iteratively; add a "dismiss theme" action |
| GitHub/HN rate limits block collection | Low | Medium | Already handled with backoff in V2 scrapers; add circuit breaker pattern |
| Apify/Proxycurl costs spike | Low | Medium | Hard cap on enrichment per day (default: 50); only enrich on threshold |
| Embedding quality insufficient for clustering | Medium | High | Test with real data in Phase 0 before committing to architecture; have fallback to keyword-based clustering |
| Single-file frontend becomes unwieldy | High | Low | Extract views to separate files if >1500 lines; maintain shared component patterns |
| Turso free tier limits hit | Low | Low | 9B reads/month is generous; add monitoring; paid tier is $29/mo if needed |
| LLM theme labeling hallucination | Medium | Medium | Use structured output format; human review of new theme labels; allow manual override |

---

## 13. Out of Scope (V3)

The following are explicitly **not** in this version:

- **Mobile app** — desktop-first tool for a single operator
- **Multi-user / team features** — single micro VC user
- **Automated outreach** — system surfaces, human reaches out
- **Portfolio tracking** — this is pre-investment intelligence only
- **Custom data source plugins** — GitHub + HN + enrichment only
- **Real-time websocket updates** — polling at 60s intervals is sufficient
- **ML model training** — use off-the-shelf embeddings and clustering, no custom model training
- **Backtesting / historical analysis** — forward-looking detection only

---

## 14. Glossary

| Term | Definition |
|------|------------|
| **Theme** | An automatically detected cluster of unrelated founders building in the same problem space |
| **Emergence score** | 0-100 composite measuring how strongly a theme is forming |
| **Builder** | A founder who belongs to a theme cluster |
| **Emergence event** | An anomaly — something that just crossed a detection threshold |
| **Enrichment** | Fetching Twitter/LinkedIn data for a founder after primary detection |
| **Primary sources** | GitHub and Hacker News — drive detection, always collected |
| **Enrichment sources** | Apify (Twitter) and Proxycurl (LinkedIn) — profile fill, on-demand |
| **Pain described** | The specific problem that founders in a theme cluster are all articulating |
| **Why now** | The enabling change (new API, cost drop, regulation) that made this theme buildable |
| **Founder origins** | Common backgrounds of founders in a theme (ex-companies, domains, geographies) |
| **Pulse** | The raw chronological feed of all signals across the system |
| **Scouting** | The CRM layer for managing outreach to specific founders |
