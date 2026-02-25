"""
Scoring engine — 4-dimension composite score for founder evaluation.
"""

import logging
import re
from datetime import datetime, timezone

from backend.db import get_latest_stats, save_score

logger = logging.getLogger(__name__)


def _to_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_year(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(19|20)\d{2}", str(text))
    if not m:
        return None
    year = int(m.group(0))
    if 1900 <= year <= datetime.now(timezone.utc).year:
        return year
    return None


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        # SQLite timestamps are typically "YYYY-MM-DD HH:MM:SS"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _score_founder_pedigree(founder_info: dict) -> int:
    bio = (founder_info.get("bio") or "").lower()
    score = 0

    if "yc" in bio or "y combinator" in bio:
        score += 20

    if any(k in bio for k in ["openai", "deepmind", "anthropic", "stripe", "coinbase", "airbnb"]):
        score += 15

    if any(k in bio for k in ["google", "meta", "amazon", "apple", "microsoft", "netflix"]):
        score += 12

    if any(k in bio for k in ["serial founder", "previously founded", "co-founded"]):
        score += 18

    if any(k in bio for k in ["phd", "research scientist"]):
        score += 8

    year = _extract_year(founder_info.get("founded") or "")
    if year is not None and year <= (datetime.now(timezone.utc).year - 3):
        score += 5

    return min(score, 35)


def _commits_from_signals(signals_list: list[dict]) -> int | None:
    candidates = []
    for s in signals_list:
        for key in ("github_commits_90d", "github_commits"):
            v = s.get(key)
            if isinstance(v, (int, float)):
                candidates.append(int(v))
    return max(candidates) if candidates else None


def _score_execution_velocity(founder_info: dict, stats: dict, signals_list: list[dict]) -> int:
    commits = _commits_from_signals(signals_list)
    if commits is None:
        commits = _to_int(stats.get("github_commits_90d"), 0)
    if commits <= 0:
        commits = _to_int(founder_info.get("github_commits"), 0)

    if commits > 500:
        return 30
    if commits > 200:
        return 22
    if commits > 100:
        return 16
    if commits > 50:
        return 10
    if commits > 10:
        return 5
    return 0


def _score_momentum(founder_info: dict, stats: dict) -> int:
    stars = _to_int(stats.get("github_stars"), _to_int(founder_info.get("github_stars"), 0))
    hn_karma = _to_int(stats.get("hn_karma"), _to_int(founder_info.get("hn_karma"), 0))

    if stars > 1000:
        score = 25
    elif stars > 500:
        score = 20
    elif stars > 200:
        score = 15
    elif stars > 100:
        score = 10
    elif stars > 50:
        score = 6
    elif stars > 20:
        score = 3
    else:
        score = 0

    if hn_karma > 5000:
        score += 8
    elif hn_karma > 1000:
        score += 5
    elif hn_karma > 500:
        score += 3

    return min(score, 25)


def _score_availability(founder_info: dict) -> int:
    bio = (founder_info.get("bio") or "").lower()
    score = 0

    if not any(k in bio for k in ["raised", "series a", "seed round", "backed by"]):
        score += 5

    updated_at = _parse_dt(founder_info.get("updated_at"))
    if updated_at is None:
        score += 3
    else:
        now = datetime.now(updated_at.tzinfo) if updated_at.tzinfo else datetime.now()
        if (now - updated_at).days <= 30:
            score += 5

    return min(score, 10)


def score_founder(conn, founder_id, founder_info, signals_list):
    """
    Compute and save all scores for a founder.

    Returns:
        Dict of scores including composite.
    """
    latest_stats = get_latest_stats(conn, founder_id)
    stats = dict(latest_stats) if latest_stats else {}

    pedigree = _score_founder_pedigree(founder_info)
    execution = _score_execution_velocity(founder_info, stats, signals_list)
    momentum = _score_momentum(founder_info, stats)
    availability = _score_availability(founder_info)

    composite = min(pedigree + execution + momentum + availability, 100)

    founder_quality = pedigree
    execution_velocity = execution
    market_conviction = momentum   # momentum stored here (stars + HN karma)
    early_traction = 0             # unused column — kept for DB compat
    deal_availability = availability

    save_score(
        conn,
        founder_id,
        founder_quality,
        execution_velocity,
        market_conviction,
        early_traction,
        deal_availability,
        composite,
    )

    scores = {
        "founder_quality": founder_quality,
        "execution_velocity": execution_velocity,
        "market_conviction": market_conviction,
        "early_traction": early_traction,
        "deal_availability": deal_availability,
        "composite": composite,
    }
    logger.info("Scored founder %d: %s", founder_id, scores)
    return scores
