"""
Scoring engine — 5-dimension composite score for founder evaluation.

Dimensions:
  1. Momentum  — recent activity velocity (commits, posts, stars growth)
  2. Domain    — depth of expertise signal (karma, tenure, specialization)
  3. Team      — founder background indicators (prior exits, network, experience)
  4. Traction  — product-market fit signals (stars, upvotes, MRR mentions)
  5. YC Fit    — alignment with YC patterns (technical founder, B2B/infra, network)

Each dimension is scored 0-100. Composite = weighted average.
Weights are calibrated against public YC batch data patterns.
"""

import logging
import math

from backend.db import get_latest_stats, save_score

logger = logging.getLogger(__name__)

# Weights calibrated to YC acceptance patterns
WEIGHTS = {
    "momentum": 0.25,
    "domain": 0.20,
    "team": 0.15,
    "traction": 0.25,
    "ycfit": 0.15,
}

# Normalization curves — log-scaled to reward early traction
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


def score_momentum(stats, signals):
    """
    Momentum: How fast is this founder moving?
    Signals: commit velocity, posting frequency, star growth rate.
    """
    commits = stats.get("github_commits_90d", 0)
    submissions = stats.get("hn_submissions", 0)
    ph_launches = stats.get("ph_launches", 0)
    strong_signals = sum(1 for s in signals if s["strong"])

    # Commit velocity: 300+ commits/90d is extremely active
    commit_score = _log_scale(commits, 300)

    # Posting frequency across platforms
    posting_score = _log_scale(submissions + ph_launches, 20)

    # Strong signal density
    signal_score = _linear_scale(strong_signals, 5)

    return commit_score * 0.40 + posting_score * 0.30 + signal_score * 0.30


def score_domain(stats, founder_info):
    """
    Domain expertise: How deep is their knowledge?
    Signals: HN karma (community recognition), specialization, tenure.
    """
    karma = stats.get("hn_karma", 0)
    stars = stats.get("github_stars", 0)
    repos = stats.get("github_repos", 0)

    # Karma reflects sustained community contribution
    karma_score = _log_scale(karma, 5000)

    # Stars reflect project quality and recognition
    stars_score = _log_scale(stars, 3000)

    # Repo count reflects breadth (but diminishing returns)
    repo_score = _log_scale(repos, 30)

    return karma_score * 0.40 + stars_score * 0.40 + repo_score * 0.20


def score_team(founder_info, stats):
    """
    Team strength: Founder background quality.
    Signals: bio keywords, alumni connections, follower count.
    """
    bio = (founder_info.get("bio") or "").lower()
    connections = founder_info.get("yc_alumni_connections", 0)
    followers = stats.get("followers", 0)

    # Bio signals — keywords indicating strong background
    bio_score = 0
    strong_keywords = [
        "ex-google", "ex-meta", "ex-stripe", "ex-amazon", "ex-apple",
        "deepmind", "openai", "phd", "serial founder", "exits",
        "yc", "y combinator", "stanford", "mit", "cmu", "berkeley",
        "engineering lead", "tech lead", "staff engineer", "principal",
        "cto", "vp engineering",
    ]
    for kw in strong_keywords:
        if kw in bio:
            bio_score += 15
    bio_score = min(bio_score, 100)

    # YC alumni network is a strong signal
    network_score = _linear_scale(connections, 5)

    # Followers indicate reputation
    follower_score = _log_scale(followers, 10000)

    return bio_score * 0.40 + network_score * 0.30 + follower_score * 0.30


def score_traction(stats, signals):
    """
    Traction: Product-market fit evidence.
    Signals: star count, upvotes, HN top score, launches.
    """
    stars = stats.get("github_stars", 0)
    hn_top = stats.get("hn_top_score", 0)
    ph_upvotes = stats.get("ph_upvotes", 0)
    total_signals = len(signals)

    # GitHub stars = sustained interest
    stars_score = _log_scale(stars, 2000)

    # HN top score = market validation moment
    hn_score = _log_scale(hn_top, 500)

    # PH upvotes = product launch success
    ph_score = _log_scale(ph_upvotes, 1000)

    # Signal volume across platforms
    signal_score = _log_scale(total_signals, 10)

    return stars_score * 0.30 + hn_score * 0.25 + ph_score * 0.25 + signal_score * 0.20


def score_ycfit(stats, founder_info, signals):
    """
    YC Fit: Alignment with typical YC acceptance patterns.
    YC tends to favor: technical founders, B2B/infra, fast builders,
    strong network, open source background.
    """
    bio = (founder_info.get("bio") or "").lower()
    domain = (founder_info.get("domain") or "").lower()
    connections = founder_info.get("yc_alumni_connections", 0)
    commits = stats.get("github_commits_90d", 0)
    stars = stats.get("github_stars", 0)

    # Technical founder signal
    technical_score = 0
    if commits > 50:
        technical_score += 40
    if stars > 100:
        technical_score += 30
    tech_bio_keywords = ["engineer", "developer", "phd", "cs", "ml", "ai", "compiler", "systems"]
    for kw in tech_bio_keywords:
        if kw in bio:
            technical_score += 10
    technical_score = min(technical_score, 100)

    # Domain fit — B2B, infra, developer tools, AI are YC sweet spots
    domain_fit = 0
    yc_domains = ["b2b", "saas", "infra", "api", "devtools", "developer", "ai", "fintech", "health"]
    for d in yc_domains:
        if d in domain or d in bio:
            domain_fit += 15
    domain_fit = min(domain_fit, 100)

    # Network fit
    network_fit = _linear_scale(connections, 3) if connections > 0 else 20  # No network isn't disqualifying

    # Builder velocity — YC wants fast shippers
    velocity_fit = _log_scale(commits, 200)

    return technical_score * 0.30 + domain_fit * 0.25 + network_fit * 0.20 + velocity_fit * 0.25


def score_founder(conn, founder_id, founder_info, signals_list):
    """
    Compute and save all scores for a founder.

    Args:
        conn: SQLite connection
        founder_id: Founder's DB id
        founder_info: Dict with founder fields (bio, domain, yc_alumni_connections, etc.)
        signals_list: List of signal dicts with 'strong' field

    Returns:
        Dict of scores including composite.
    """
    latest_stats = get_latest_stats(conn, founder_id)
    stats = dict(latest_stats) if latest_stats else {}

    m = round(score_momentum(stats, signals_list))
    d = round(score_domain(stats, founder_info))
    t = round(score_team(founder_info, stats))
    tr = round(score_traction(stats, signals_list))
    y = round(score_ycfit(stats, founder_info, signals_list))

    composite = round(
        m * WEIGHTS["momentum"]
        + d * WEIGHTS["domain"]
        + t * WEIGHTS["team"]
        + tr * WEIGHTS["traction"]
        + y * WEIGHTS["ycfit"]
    )

    save_score(conn, founder_id, m, d, t, tr, y, composite)

    scores = {
        "momentum": m,
        "domain": d,
        "team": t,
        "traction": tr,
        "ycfit": y,
        "composite": composite,
    }
    logger.info("Scored founder %d: %s", founder_id, scores)
    return scores
