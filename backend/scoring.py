"""
Scoring engine — 5-dimension composite score for founder evaluation.

Dimensions:
  1. Founder Quality  — Who is this person? (technical depth, distribution
     instinct, building history, network quality, cofounder complementarity)
  2. Execution Velocity — Are they actually building? (commit cadence,
     iteration speed, release velocity, feedback responsiveness)
  3. Market Conviction — Real obsession with a problem? (domain writing depth,
     time in problem space, community presence, pain-point specificity)
  4. Early Traction — Is anyone actually caring? (community formation, waitlist
     signals, stars velocity, third-party mentions, revenue signals)
  5. Deal Availability — Are you still early enough? (no public fundraising,
     low VC engagement, no press coverage, early stage indicators)

Each dimension is scored 0-100. Composite = weighted average.
Weights are tunable via the dashboard UI; defaults optimized for pre-seed.
"""

import logging
import math

from backend.db import get_latest_stats, save_score

logger = logging.getLogger(__name__)

# Default weights — pre-seed oriented (Founder Quality + Execution heavy).
# All weights must sum to 1.0. Tunable from the frontend.
DEFAULT_WEIGHTS = {
    "founder_quality": 0.30,
    "execution_velocity": 0.25,
    "market_conviction": 0.15,
    "early_traction": 0.20,
    "deal_availability": 0.10,
}

# Normalization helpers — log-scaled to reward early traction
# without over-indexing on outliers


def _log_scale(value, baseline, cap=100):
    """Log-scaled normalization. Returns 0-100."""
    if value <= 0:
        return 0
    raw = (math.log1p(value) / math.log1p(baseline)) * 100
    return min(raw, cap)


def _linear_scale(value, max_val, cap=100):
    if max_val <= 0:
        return 0
    return min((value / max_val) * 100, cap)


def _keyword_score(text, keywords, points_per_match=15, cap=100):
    """Score based on keyword presence in text."""
    score = 0
    for kw in keywords:
        if kw in text:
            score += points_per_match
    return min(score, cap)


# ── Dimension 1: Founder Quality ─────────────────────────────


def score_founder_quality(stats, founder_info, signals):
    """
    Who is this person?
    Sub-signals:
      - Technical depth (repo complexity, stars as quality proxy, commit consistency)
      - Distribution instinct (public writing, launches, community engagement)
      - Previous building history (repo count, signal volume = builder pattern)
      - Network quality (who follows them — YC alumni connections, follower quality)
      - Cofounder complementarity (tech + business coverage in bio)
    """
    bio = (founder_info.get("bio") or "").lower()
    commits = stats.get("github_commits_90d", 0)
    stars = stats.get("github_stars", 0)
    repos = stats.get("github_repos", 0)
    karma = stats.get("hn_karma", 0)
    submissions = stats.get("hn_submissions", 0)
    ph_launches = stats.get("ph_launches", 0)
    connections = founder_info.get("yc_alumni_connections", 0)
    followers = stats.get("followers", 0)

    # Technical depth: commit consistency + project quality (stars) + breadth (repos)
    technical = (
        _log_scale(commits, 300) * 0.40
        + _log_scale(stars, 2000) * 0.35
        + _log_scale(repos, 25) * 0.25
    )

    # Distribution instinct: do they write, post, engage publicly?
    distribution = (
        _log_scale(karma, 5000) * 0.40
        + _log_scale(submissions + ph_launches, 15) * 0.35
        + _log_scale(len(signals), 10) * 0.25
    )

    # Building history: bio signals for prior experience
    builder_keywords = [
        "serial founder", "exits", "ex-google", "ex-meta", "ex-stripe",
        "ex-amazon", "ex-apple", "deepmind", "openai", "phd",
        "staff engineer", "principal", "tech lead", "engineering lead",
        "cto", "vp engineering", "yc", "y combinator",
    ]
    history = _keyword_score(bio, builder_keywords, 12, 100)

    # Network quality: meaningful connections, not vanity follower count
    network = (
        _linear_scale(connections, 5) * 0.60
        + _log_scale(followers, 15000) * 0.40
    )

    # Cofounder complementarity: tech + business signals both present
    tech_kw = ["engineer", "developer", "phd", "cs", "ml", "ai", "compiler", "systems"]
    biz_kw = ["mba", "business", "sales", "growth", "marketing", "operations", "strategy", "product"]
    has_tech = any(kw in bio for kw in tech_kw)
    has_biz = any(kw in bio for kw in biz_kw)
    complementarity = 100 if (has_tech and has_biz) else 60 if has_tech else 40 if has_biz else 20

    return (
        technical * 0.30
        + distribution * 0.20
        + history * 0.20
        + network * 0.15
        + complementarity * 0.15
    )


# ── Dimension 2: Execution Velocity ──────────────────────────


def score_execution_velocity(stats, signals):
    """
    Are they actually building?
    Sub-signals:
      - Commit frequency and regularity (cadence > spikes)
      - Product iteration speed (releases, launches, changelogs)
      - Time from idea to something live (signal density as proxy)
      - Response to feedback (post-launch activity)
    """
    commits = stats.get("github_commits_90d", 0)
    ph_launches = stats.get("ph_launches", 0)
    submissions = stats.get("hn_submissions", 0)
    strong_signals = sum(1 for s in signals if s.get("strong"))

    # Commit cadence: 300+ commits/90d = top tier. Log-scaled for diminishing returns.
    cadence = _log_scale(commits, 300)

    # Iteration speed: launches + submissions indicate shipping publicly
    iteration = _log_scale(ph_launches + submissions, 15)

    # Signal density: more signals = more activity = faster execution
    density = _log_scale(len(signals), 12)

    # Strong signal ratio: shipping things that matter
    strong_ratio = _linear_scale(strong_signals, 5)

    return (
        cadence * 0.40
        + iteration * 0.25
        + density * 0.15
        + strong_ratio * 0.20
    )


# ── Dimension 3: Market Conviction ───────────────────────────


def score_market_conviction(stats, founder_info, signals):
    """
    Do they have a real obsession with a problem?
    Sub-signals:
      - Depth of domain writing (HN karma, sustained posting)
      - Time in problem space (bio keywords indicating domain expertise)
      - Community presence (multi-platform = invested in the space)
      - Specificity of the pain point (narrow domain > broad pitch)
    """
    bio = (founder_info.get("bio") or "").lower()
    domain = (founder_info.get("domain") or "").lower()
    karma = stats.get("hn_karma", 0)
    submissions = stats.get("hn_submissions", 0)

    # Domain writing depth: karma reflects sustained community engagement
    writing_depth = (
        _log_scale(karma, 4000) * 0.60
        + _log_scale(submissions, 20) * 0.40
    )

    # Domain expertise keywords: time in the problem space
    domain_keywords = [
        "years in", "previously", "background in", "industry veteran",
        "phd", "researcher", "domain expert", "built at",
        "ex-", "former", "led", "advisor",
    ]
    expertise = _keyword_score(bio, domain_keywords, 15, 100)

    # Multi-platform presence: true conviction shows up everywhere
    sources = set()
    for s in signals:
        src = s.get("source", "")
        if src:
            sources.add(src)
    presence = _linear_scale(len(sources), 3)

    # Pain point specificity: specific domain tags and narrow focus
    specific_domains = [
        "fintech", "health", "biotech", "infra", "devtools", "compiler",
        "payments", "security", "compliance", "logistics", "construction",
        "climate", "energy", "education", "legal", "proptech",
    ]
    specificity = 0
    for d in specific_domains:
        if d in domain or d in bio:
            specificity += 20
    specificity = min(specificity, 100)

    return (
        writing_depth * 0.30
        + expertise * 0.25
        + presence * 0.20
        + specificity * 0.25
    )


# ── Dimension 4: Early Traction ──────────────────────────────


def score_early_traction(stats, signals):
    """
    Is anyone actually caring?
    Sub-signals:
      - Organic community formation (followers, engagement patterns)
      - Waitlist/early user signals (PH upvotes, launches)
      - GitHub stars velocity (open-source traction)
      - Unprompted third-party mentions (strong signal count)
      - Revenue transparency (MRR/revenue mentions in signals)
    """
    stars = stats.get("github_stars", 0)
    hn_top = stats.get("hn_top_score", 0)
    ph_upvotes = stats.get("ph_upvotes", 0)
    followers = stats.get("followers", 0)
    strong_signals = sum(1 for s in signals if s.get("strong"))

    # GitHub stars = sustained organic interest
    stars_score = _log_scale(stars, 2000)

    # HN top score = market validation moment
    hn_score = _log_scale(hn_top, 500)

    # PH upvotes = early user excitement
    ph_score = _log_scale(ph_upvotes, 800)

    # Strong signals = unprompted external validation
    external_score = _linear_scale(strong_signals, 5)

    # Revenue/MRR mentions in signals (strong traction indicator)
    revenue_signals = sum(
        1 for s in signals
        if any(kw in (s.get("label") or "").lower() for kw in ["mrr", "revenue", "arr", "$", "paying"])
    )
    revenue_score = _linear_scale(revenue_signals, 2)

    return (
        stars_score * 0.25
        + hn_score * 0.20
        + ph_score * 0.20
        + external_score * 0.20
        + revenue_score * 0.15
    )


# ── Dimension 5: Deal Availability ───────────────────────────


def score_deal_availability(stats, founder_info, signals):
    """
    Are you still early enough to invest?
    This is an *inverse* signal — less exposure = higher score.
    Sub-signals:
      - No public fundraising (absence of raise signals is good)
      - Low VC engagement (not yet swarmed by investors)
      - No press coverage (first press = deal window closing)
      - Early stage indicators (pre-seed > seed > series A)
    """
    stage = (founder_info.get("stage") or "").lower()
    followers = stats.get("followers", 0)

    # Stage indicator: earlier = more available
    stage_scores = {
        "pre-seed": 95, "bootstrapped": 90, "unknown": 80,
        "seed": 55, "series a": 20, "series b": 5,
    }
    stage_score = stage_scores.get(stage, 70)

    # Fundraising activity signals (absence = good)
    fundraise_keywords = ["raised", "funding", "series", "round", "investment", "backed by", "investor"]
    fundraise_signals = sum(
        1 for s in signals
        if any(kw in (s.get("label") or "").lower() for kw in fundraise_keywords)
    )
    no_fundraise = max(100 - fundraise_signals * 40, 0)

    # Public profile size: less discovered = more accessible
    # Inverse: high followers = deal window narrowing
    if followers <= 1000:
        profile_score = 95
    elif followers <= 5000:
        profile_score = 75
    elif followers <= 15000:
        profile_score = 50
    elif followers <= 50000:
        profile_score = 25
    else:
        profile_score = 10

    # Press/coverage signal density: fewer mentions = still under radar
    total_signals = len(signals)
    if total_signals <= 2:
        exposure_score = 90
    elif total_signals <= 5:
        exposure_score = 70
    elif total_signals <= 10:
        exposure_score = 45
    else:
        exposure_score = 20

    return (
        stage_score * 0.35
        + no_fundraise * 0.25
        + profile_score * 0.20
        + exposure_score * 0.20
    )


# ── Composite scoring ────────────────────────────────────────


def score_founder(conn, founder_id, founder_info, signals_list):
    """
    Compute and save all scores for a founder.

    Args:
        conn: SQLite connection
        founder_id: Founder's DB id
        founder_info: Dict with founder fields (bio, domain, stage, yc_alumni_connections, etc.)
        signals_list: List of signal dicts with 'strong', 'source', 'label' fields

    Returns:
        Dict of scores including composite.
    """
    latest_stats = get_latest_stats(conn, founder_id)
    stats = dict(latest_stats) if latest_stats else {}

    fq = round(score_founder_quality(stats, founder_info, signals_list))
    ev = round(score_execution_velocity(stats, signals_list))
    mc = round(score_market_conviction(stats, founder_info, signals_list))
    et = round(score_early_traction(stats, signals_list))
    da = round(score_deal_availability(stats, founder_info, signals_list))

    composite = round(
        fq * DEFAULT_WEIGHTS["founder_quality"]
        + ev * DEFAULT_WEIGHTS["execution_velocity"]
        + mc * DEFAULT_WEIGHTS["market_conviction"]
        + et * DEFAULT_WEIGHTS["early_traction"]
        + da * DEFAULT_WEIGHTS["deal_availability"]
    )

    save_score(conn, founder_id, fq, ev, mc, et, da, composite)

    scores = {
        "founder_quality": fq,
        "execution_velocity": ev,
        "market_conviction": mc,
        "early_traction": et,
        "deal_availability": da,
        "composite": composite,
    }
    logger.info("Scored founder %d: %s", founder_id, scores)
    return scores
