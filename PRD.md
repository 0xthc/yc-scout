# PRD: Private Market Intelligence Tool for Micro VCs
**Version 1.0 | Feb 2026**

---

## 1. Purpose

This tool is a private intelligence layer for a solo or micro VC. Its singular job: surface investment-ready founders and emerging problem spaces 6–18 months before they become visible to the broader market — before YC batch announcements, before press, before other investors see them.

This is not a filter on a known universe. It is a detection system for what is about to emerge.

---

## 2. Target User

**One person. A micro VC operator who:**
- Manages their own deal flow without an analyst team
- Has pattern recognition but lacks bandwidth to monitor signals manually
- Wants an edge that comes from seeing things *earlier*, not from seeing the same things faster
- Is comfortable with a high-signal, low-noise interface — prefers depth over breadth

This tool is not built for a firm. It is built for a person.

---

## 3. Core Design Principles

**Detect, don't filter.** The system watches for things crossing thresholds, not ranks items on a known list.

**Primary sources drive detection. Enrichment follows.** GitHub and HN are the detection engine. Apify/Proxycurl enrich *after* a founder is already flagged — never before.

**Emergence over existence.** The most important signal is not "this is good" — it's "this just changed." Velocity, inflection, and clustering anomalies matter more than absolute scores.

**No manually defined categories.** Themes are detected, not predefined. The system finds clusters; the human names them if needed.

**Built for daily use in under 10 minutes.** Four views, each answering a different question. The user should always know exactly where to go.

---

## 4. Four Views

---

### 4.1 Themes *(Primary View)*

**The question it answers:** What problem spaces are heating up right now?

**What it shows:**
A theme is an automatically detected cluster of unrelated founders who are independently building in the same direction. The fact that they don't know each other and are converging on the same problem is the signal.

Each theme card displays:

| Field | Description |
|---|---|
| **Theme name** | Auto-generated label from semantic cluster centroid |
| **Emergence score** | 0–100. Composite of cluster growth rate, velocity, and signal density |
| **Builder count** | Number of founders currently in the cluster |
| **Weekly velocity** | Change in cluster size and signal volume vs. prior 7 days |
| **The pain** | What problem are they all describing? (auto-synthesized from HN posts, repo READMEs, commit messages) |
| **The unlock** | What recently made this buildable? (detected from tech references: new model, new API, new infra) |
| **Founder origin** | Where are these people coming from? (ex-FAANG, researchers, domain operators, repeat founders) |

**Interaction:**
- Clicking a theme opens the full cluster view — all founders, their individual scores, and the signal log that triggered clustering
- Themes are sorted by emergence score by default; sortable by velocity or builder count
- No manual creation or editing of themes — the system owns this layer entirely

---

### 4.2 Emergence *(Anomaly View)*

**The question it answers:** What just crossed a threshold that wasn't on my radar yesterday?

**What it shows:**
Two sections:

**New Themes** — clusters that became detectable in the last 7 days. These are the earliest-stage signals. A new theme means the system identified ≥3 unrelated founders independently converging on the same problem within a 7-day window.

**Inflection Founders** — individual projects whose momentum just spiked. A founder whose GitHub commit velocity doubled week-over-week, or whose HN content crossed an engagement threshold, or whose repo just hit a star velocity anomaly.

Each card shows:
- What changed (the specific signal that triggered the alert)
- The delta (before vs. after)
- Time since detection
- Founder/theme score at time of detection

**Design intent:**
This is the view you open first. It's the morning brief — "what moved while I wasn't watching." It is not a list of things to evaluate. It is a list of things that just changed. The distinction matters.

---

### 4.3 Pulse *(Raw Signal Feed)*

**The question it answers:** What happened in the last 48 hours?

**What it shows:**
A chronological feed of every signal that fired across all themes and founders in the last 48 hours. Unfiltered, unranked beyond time. Each entry shows:

- Signal type (new repo, HN post, star spike, commit surge, Show HN, new cluster connection, etc.)
- Founder / theme it's attached to
- The raw signal content (repo name, HN post title, etc.)
- Score impact if any

**Design intent:**
This is the daily awareness layer. You check it to stay aware of what the system is tracking — not to make decisions. It's the fastest scan. It surfaces things that didn't cross an emergence threshold yet but are accumulating. High-volume, low-friction reading.

---

### 4.4 Scouting *(CRM Layer)*

**The question it answers:** Which founders has the system surfaced who are ready for outreach?

**What it shows:**
Specific founders who have crossed detection thresholds and are enriched with full profiles. This is the last mile — where detection ends and relationship begins.

Each founder profile shows:

**Detection Layer** (from primary sources):
- Overall score (0–100) across 5 dimensions
- Score breakdown: Momentum / Domain / Team / Traction / YC Fit
- Full signal history — every data point that contributed to their score
- Theme membership — which cluster(s) they belong to

**Enrichment Layer** (triggered after threshold crossing):
- Twitter presence (via Apify): posting frequency, engagement, technical/founder content ratio
- LinkedIn background (via Proxycurl): education, employment history, prior companies, alumni networks

**Status tracking (CRM):**
- `watching` → `to contact` → `contacted` → `passed`
- Notes field (free text, private)
- Date first detected vs. date enriched vs. date contacted

**Design intent:**
Scouting is not the detection layer. Founders don't appear here because a user added them. They appear because the system decided they were interesting. The user's job in this view is: reach out or not.

---

## 5. Data Architecture

### 5.1 Primary Sources (Detection Engine)

| Source | Access | What it provides |
|---|---|---|
| **GitHub** | REST API v3 (free, public) | Commit cadence, repo creation rate, star velocity, language, topics, README content, production-code signals |
| **Hacker News** | Algolia + Firebase (free) | Pain posts, Ask HN, Show HN launches, comment depth, karma trajectory, writing consistency over time |

These two sources do **all** detection. Nothing else fires until a founder crosses a score threshold here.

### 5.2 Enrichment Sources (Profile Deepening)

Triggered **only** when a founder crosses the detection threshold (default: score ≥ 75 across primary sources).

| Source | Provider | What it adds |
|---|---|---|
| **Twitter/X** | Apify | Posting frequency, follower trajectory, engagement rate, technical content ratio |
| **LinkedIn** | Proxycurl | Employment history, education, alumni networks, serial founder flag |

Enrichment is **pull-on-demand**, not continuous. One enrichment call per founder, refreshed monthly if status = `watching` or above.

### 5.3 Processing Engine

Three jobs run on the ingested data:

**1. Semantic Clustering (Theme Detection)**
Founders are embedded using their GitHub README content + HN post text. Clusters are detected using HDBSCAN (density-based, no predefined k). A new theme is declared when ≥3 founders cluster with cosine similarity > 0.72 within a 14-day rolling window.

**2. Founder Scoring**
Each founder scored on 5 dimensions, each 0–100:

| Dimension | Weight | Primary Signals |
|---|---|---|
| Momentum | 25% | Commit velocity, post frequency, signal acceleration |
| Domain | 20% | HN karma, GitHub stars, topic authority signals |
| Team | 15% | Bio keywords (ex-FAANG, PhD, prior exits), alumni network |
| Traction | 25% | Star velocity, HN score, engagement volume |
| YC Fit | 15% | Technical founder signals, B2B/infra/AI domain, builder velocity |

**3. Velocity Anomaly Detection**
Watches for momentum inflections — not just high scores but *sudden changes*. An alert fires when:
- Week-over-week commit velocity ≥ 2x
- HN engagement rate spikes > 3 standard deviations from personal baseline
- Star growth crosses 15+ in 24h on a sub-100 star repo

---

## 6. Technical Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI (Python) |
| **Database** | Turso (libsql) — production; SQLite — local dev |
| **Embeddings** | OpenAI `text-embedding-3-small` or local alternative |
| **Clustering** | scikit-learn HDBSCAN |
| **Pipeline** | GitHub Actions cron (hourly) |
| **Enrichment calls** | Apify + Proxycurl (on-demand, post-threshold) |
| **Frontend** | React + Vite |
| **Deployment** | Render (backend) + GitHub Pages (frontend) |

---

## 7. Pipeline Flow

```
Every hour (GitHub Actions):
  1. Scrape HN → new posts, karma deltas, Show HN launches
  2. Scrape GitHub → new repos, commit deltas, star velocity
  3. Embed content → founder vectors updated
  4. Run clustering → detect new/changed theme clusters
  5. Score founders → update 5-dimension scores
  6. Check anomalies → fire emergence alerts if thresholds crossed
  7. Trigger enrichment → call Apify/Proxycurl for newly-qualified founders
  8. Write to DB → all views update in real time
```

---

## 8. Out of Scope (V1)

- Product Hunt scraping (low signal-to-noise for pre-emergence detection)
- Team collaboration / multi-user access
- Email or Slack alerts (can be added in V2)
- Manual theme creation or curation
- Public company tracking (post-funding is too late — this tool only cares about pre-funding)

---

## 9. Success Metric

**The tool works if:** you reach out to a founder 6+ months before they announce a round, and they say "how did you find me?"

That's it.
