# Precognition — Documentation
**VC Intelligence Platform · v1.0**

---

## What is Precognition?

Precognition is a private intelligence tool for micro VCs. It surfaces investment-ready founders and emerging problem spaces **6–18 months before they become visible to the broader market** — before YC, before press, before other investors.

It does not filter a known list. It detects what is about to emerge.

---

## Data Sources

Everything flows from two primary sources that are fully accessible without paywalls:

### GitHub
Behavioral signals — what founders actually build.

| Signal | What it captures |
|--------|-----------------|
| Commit cadence | How often they push code (90-day window) |
| Repo creation | New projects started recently |
| Star velocity | How fast repos are gaining attention |
| Repo topics & README | What they're building and how they describe it |
| Language stack | Technical depth indicators |

**Access:** GitHub REST API v3 (public repos, free). Requires `GITHUB_TOKEN` for higher rate limits.

---

### Hacker News
Language signals — what founders write before they have a company.

| Signal | What it captures |
|--------|-----------------|
| Ask HN / Show HN posts | Problem pain posts, product launches |
| Karma trajectory | Sustained community engagement over time |
| Comment depth | Quality of thinking, not just volume |
| Writing consistency | Years of presence = domain conviction |
| Top post score | Peak engagement moment |

**Access:** Algolia HN API + Firebase (fully public, no key needed).

---

### Enrichment Sources *(optional, fires only after score ≥ 75)*

These enrich a profile after the system has already flagged a founder as interesting. They do not drive detection.

| Source | Provider | What it adds |
|--------|----------|-------------|
| Twitter / X | Apify | Follower count, posting frequency, engagement rate, technical content ratio |
| LinkedIn | Proxycurl | Employment history, education, serial founder detection, FAANG/YC/PhD signals |

---

## The Four Views

---

### 1. Themes
**The question it answers:** What problem spaces are heating up right now?

A **Theme** is an automatically detected cluster of unrelated founders who are independently building in the same direction. The convergence is the signal — not one founder, but many, who don't know each other, all moving toward the same problem.

Themes are **not manually defined**. The system detects them using semantic clustering (HDBSCAN on founder embeddings).

#### Theme Card Parameters

| Parameter | Description |
|-----------|-------------|
| **Name** | Auto-generated from the most common domain/tag words across founders in the cluster |
| **Emergence Score** | 0–100. Composite of builder count, signal velocity, and week-over-week growth. Higher = stronger signal |
| **Builder Count** | Number of founders currently in the cluster |
| **WoW Growth** | Week-over-week change in builder count (%). Positive = cluster is expanding |
| **First Detected** | When the system first identified this cluster |
| **Pain** | What problem are they all describing? Synthesized from HN posts and GitHub READMEs |
| **Unlock** | What recently made this buildable? (new model, API, infrastructure) |
| **Founder Origin** | Where these founders come from (ex-FAANG, researchers, operators, serial founders) |
| **Founder Avatars** | The top 5 founders in the cluster |

#### Emergence Score Breakdown

| Factor | Weight | Signal |
|--------|--------|--------|
| Builder count | 30% | More unrelated founders = stronger convergence |
| Signal velocity | 40% | Signals per founder per day over last 7 days |
| WoW builder growth | 30% | Cluster expanding = theme is accelerating |

**Threshold for a valid theme:** ≥ 3 founders with cosine similarity > 0.72 within a 14-day rolling window.

---

### 2. Emergence
**The question it answers:** What just crossed a threshold that wasn't on my radar yesterday?

This is the anomaly view. You open it to see **what moved**, not what exists. Two sections:

#### New Theme Clusters
Themes detected in the last 7 days. These are the earliest signals — the system just identified 3+ founders converging on the same problem for the first time.

| Parameter | Description |
|-----------|-------------|
| **Theme Name** | Auto-generated cluster label |
| **Event Type** | `new_theme` (first detection) or `theme_spike` (50%+ WoW growth) |
| **Builder Count** | Founders in the cluster at time of detection |
| **Signal** | Human-readable description of what triggered the event |
| **Detected At** | Timestamp of the event |

#### Inflection Founders
Individual founders whose momentum just spiked. Three types of events:

| Event Type | Trigger Condition |
|------------|------------------|
| `commit_spike` | Commit velocity ≥ 2× week-over-week (minimum base of 5 commits) |
| `star_spike` | GitHub repo gained 15+ stars in 24h while total stars < 100 |
| `hn_spike` | HN post score exceeds 100 points (new personal best) |

Each event shows:
- **What changed** — the specific signal that triggered the alert
- **Before → After** — the delta in numbers
- **Time since detection** — how fresh the signal is
- **Founder score** — their composite score at time of detection

---

### 3. Pulse
**The question it answers:** What happened in the last 48 hours?

The raw chronological feed of every signal that fired across all themes and founders. Unfiltered, sorted by time. You check it daily to stay aware of what's accumulating — things that haven't crossed an emergence threshold yet but are building.

#### Signal Parameters

| Parameter | Description |
|-----------|-------------|
| **Source** | `GH` (GitHub), `HN` (Hacker News), `PH` (Product Hunt) |
| **Founder / Company** | Who the signal belongs to |
| **Label** | The specific signal (e.g. "Show HN: I built X", "Launched repo: fast-inference", "1,200 HN karma") |
| **Key** | Marked on strong signals — ones that indicate a meaningful traction event |
| **Timestamp** | When the signal was detected |

#### Signal Source Colors
- **GH (blue)** — GitHub activity
- **HN (amber)** — Hacker News activity
- **PH (red)** — Product Hunt activity

---

### 4. Scouting
**The question it answers:** Which founders are ready for outreach?

The CRM layer — the last mile between detection and relationship. Founders appear here because the system surfaced them, not because you added them manually.

#### Founder Card (List)

| Parameter | Description |
|-----------|-------------|
| **Name / Company** | Founder name and their current company or project |
| **Stage** | Estimated funding stage: Pre-seed, Bootstrapped, Seed, Series A, etc. |
| **Domain** | The problem space they're working in |
| **Location** | Where they're based |
| **Source Badge** | Which platform they were discovered on (GH / HN / PH) |
| **Score** | Composite score 0–100 with color indicator |

#### Founder Detail Panel

**Header**
- Name, company, stage, location, bio
- Status badge (click to cycle through stages)
- Composite score pill

**Stats Grid**

| Metric | Source | What it means |
|--------|--------|---------------|
| GH Stars | GitHub | Total stars across all public repos |
| Commits/90d | GitHub | Commit count over last 90 days |
| HN Karma | Hacker News | Lifetime karma score |
| HN Top | Hacker News | Highest single post score ever |
| PH Upvotes | Product Hunt | Total upvotes across all launches |
| Followers | Cross-platform | Follower count (GitHub + social) |

---

## Founder Scoring

Every founder is scored on **5 dimensions**, each 0–100. Scores are computed on every pipeline run.

### Dimension 1 — Founder Quality (25%)
*Who is this person?*

| Sub-signal | What it measures |
|-----------|-----------------|
| Technical depth | Repo complexity, star quality, commit consistency |
| Distribution instinct | Public writing, launches, community engagement |
| Building history | Prior roles, exits, alma mater signals in bio |
| Network quality | YC alumni connections, follower quality |
| Incubator affiliation | YC (+20pts), 500 Global (+12pts), Plug and Play (+5pts) |

### Dimension 2 — Execution Velocity (20%)
*Are they actually building?*

| Sub-signal | What it measures |
|-----------|-----------------|
| Commit cadence | 300+ commits/90d = top tier (log-scaled) |
| Iteration speed | Public launches and HN posts |
| Signal density | Total signals as proxy for activity volume |
| Strong signal ratio | Signals that indicate meaningful milestones |

### Dimension 3 — Market Conviction (15%)
*Do they have a real obsession with the problem?*

| Sub-signal | What it measures |
|-----------|-----------------|
| Writing depth | HN karma + sustained posting history |
| Domain expertise | Bio keywords: "years in", "ex-", "PhD", "led" |
| Multi-platform presence | Active on GitHub AND HN = stronger conviction |
| Pain specificity | Narrow, named domain > broad pitch |

### Dimension 4 — Early Traction (25%)
*Is anyone actually caring?*

| Sub-signal | What it measures |
|-----------|-----------------|
| GitHub stars | Organic developer interest |
| HN top score | Peak market validation moment |
| PH upvotes | Early user excitement |
| Strong signals | Third-party mentions, unprompted attention |
| Revenue signals | MRR/ARR mentions in signals |

### Dimension 5 — Deal Availability (15%)
*Are you still early enough?*

This is an **inverse signal** — less exposure = higher score.

| Sub-signal | What it measures |
|-----------|-----------------|
| Stage | Pre-seed (95) → Bootstrapped (90) → Seed (55) → Series A (20) |
| No fundraising signals | Absence of "raised", "backed by", "round" language |
| Low public profile | Followers < 1,000 = still under the radar |
| Low signal density | Fewer total signals = less discovered |
| Incubator penalty | YC (-25pts at Demo Day — round oversubscribes fast) |

### Score Interpretation

| Score | Label | Meaning |
|-------|-------|---------|
| 85–100 | **Strong** | High conviction — reach out now |
| 70–84 | **Good** | Worth tracking closely |
| 50–69 | **Monitor** | Early signal, keep watching |
| 0–49 | **Weak** | Not yet ready |

---

## CRM Status Workflow

Founders move through four statuses. Click the status badge in the detail panel to advance.

| Status | Meaning |
|--------|---------|
| **To Contact** | System flagged them — not yet reached out |
| **Watching** | On your radar, monitoring closely. Triggers monthly enrichment refresh |
| **Contacted** | Outreach initiated. Also triggers monthly enrichment refresh |
| **Pass** | Decided not to pursue |

---

## Enrichment

Enrichment activates automatically when:
1. A founder's composite score reaches **≥ 75**
2. They have not been enriched in the last **30 days**
3. Their status is `watching` or `contacted` for monthly refreshes

#### Twitter Enrichment (Apify)

| Field | Description |
|-------|-------------|
| Handle | @username |
| Followers | Total follower count |
| Engagement Rate | Average (likes + retweets) per tweet |
| Technical Ratio | % of tweets containing technical/founder keywords |

#### LinkedIn Enrichment (Proxycurl)

| Field | Description |
|-------|-------------|
| Summary | Enriched bio with detected signals (ex-FAANG, PhD, YC, serial founder) |
| Serial Founder | True if they've founded more than one company |
| Employment History | Current and prior companies, titles, tenures |
| Education | School, degree, field — flags top universities and PhDs |

---

## Pipeline Schedule

The system runs every hour via GitHub Actions.

```
Every hour:
  1. Scrape HN          → new posts, karma deltas, Show HN launches
  2. Scrape GitHub      → new repos, commit deltas, star velocity
  3. Embed founders     → generate/update content vectors (OpenAI)
  4. Cluster founders   → detect new/updated theme clusters (HDBSCAN)
  5. Score founders     → update 5-dimension scores
  6. Enrich             → Twitter + LinkedIn for founders scoring ≥ 75
  7. Detect anomalies   → flag velocity spikes, new clusters
  8. Send alerts        → Slack / email if configured
```

---

## Required API Keys

| Key | Required | Purpose | Cost |
|-----|----------|---------|------|
| `OPENAI_API_KEY` | Strongly recommended | Semantic embeddings for theme clustering | ~$0.01 per full run |
| `SCOUT_GITHUB_TOKEN` | Recommended | Higher GitHub rate limits (5,000 req/hr vs 60) | Free |
| `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` | Required (production) | Database | Free tier available |
| `APIFY_API_TOKEN` | Optional | Twitter enrichment | ~$0.002/profile |
| `PROXYCURL_API_KEY` | Optional | LinkedIn enrichment | ~$0.01/profile |
| `SLACK_WEBHOOK_URL` | Optional | Alert notifications | Free |
