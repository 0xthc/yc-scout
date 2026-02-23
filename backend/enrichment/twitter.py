"""
Twitter/X enrichment via Apify.

Uses the Twitter Profile Scraper actor (apidojo/tweet-scraper or
apify/twitter-scraper). Pulls:
  - follower count
  - tweet count / posting frequency
  - engagement rate (avg likes + retweets per tweet)
  - technical content ratio (tweets mentioning code, AI, startups, products)
  - profile URL

Requires: APIFY_API_TOKEN in environment.
Falls back gracefully (returns None) if token is missing or call fails.
"""

import logging
import time

import httpx

from backend.config import APIFY_API_TOKEN

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "apidojo/twitter-user-scraper"
TIMEOUT = 60  # seconds to wait for actor run

TECHNICAL_KEYWORDS = [
    "ai", "llm", "gpt", "api", "github", "code", "startup", "saas", "b2b",
    "ml", "model", "agent", "product", "launch", "deploy", "ship", "build",
    "founder", "infra", "rag", "embedding", "vector", "open source",
]


def _call_actor(handle: str) -> dict | None:
    """Run the Apify Twitter actor synchronously and return raw result."""
    if not APIFY_API_TOKEN:
        logger.warning("APIFY_API_TOKEN not set — skipping Twitter enrichment")
        return None

    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}"}

    # Start actor run
    try:
        resp = httpx.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            headers=headers,
            json={
                "startUrls": [{"url": f"https://twitter.com/{handle}"}],
                "tweetsDesired": 20,
                "addUserInfo": True,
            },
            timeout=30,
        )
        resp.raise_for_status()
        run_id = resp.json()["data"]["id"]
    except Exception as e:
        logger.error("Apify actor start failed for @%s: %s", handle, e)
        return None

    # Poll for completion
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        try:
            status_resp = httpx.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers=headers,
                timeout=10,
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                logger.warning("Apify run %s ended with status %s", run_id, status)
                return None
        except Exception as e:
            logger.warning("Apify poll error: %s", e)
        time.sleep(3)
    else:
        logger.warning("Apify run %s timed out after %ds", run_id, TIMEOUT)
        return None

    # Fetch dataset
    try:
        items_resp = httpx.get(
            f"{APIFY_BASE}/actor-runs/{run_id}/dataset/items",
            headers=headers,
            timeout=20,
        )
        items = items_resp.json()
        return items[0] if items else None
    except Exception as e:
        logger.error("Apify dataset fetch failed: %s", e)
        return None


def _compute_engagement_rate(tweets: list[dict]) -> float:
    """Average (likes + retweets) per tweet, as a ratio of followers."""
    if not tweets:
        return 0.0
    total = sum((t.get("likeCount", 0) or 0) + (t.get("retweetCount", 0) or 0) for t in tweets)
    return round(total / len(tweets), 2)


def _technical_ratio(tweets: list[dict]) -> float:
    """Fraction of tweets containing at least one technical keyword."""
    if not tweets:
        return 0.0
    technical = sum(
        1 for t in tweets
        if any(kw in (t.get("text") or "").lower() for kw in TECHNICAL_KEYWORDS)
    )
    return round(technical / len(tweets), 2)


def enrich_twitter(handle: str) -> dict | None:
    """
    Enrich a founder's Twitter profile.

    Returns dict with keys:
      twitter_handle, twitter_followers, twitter_engagement_rate,
      twitter_tweet_count, twitter_technical_ratio
    or None if enrichment failed.
    """
    # Strip @ if present
    handle = handle.lstrip("@")
    if not handle:
        return None

    raw = _call_actor(handle)
    if not raw:
        return None

    user = raw.get("user") or raw  # actor shapes vary
    tweets = raw.get("tweets") or []

    followers = user.get("followersCount") or user.get("followers_count") or 0
    tweet_count = user.get("statusesCount") or user.get("statuses_count") or len(tweets)
    engagement = _compute_engagement_rate(tweets)
    tech_ratio = _technical_ratio(tweets)

    logger.info(
        "Twitter enriched @%s: %d followers, %.2f engagement, %.0f%% technical",
        handle, followers, engagement, tech_ratio * 100,
    )

    return {
        "twitter_handle": f"@{handle}",
        "twitter_followers": followers,
        "twitter_engagement_rate": engagement,
        "twitter_tweet_count": tweet_count,
        "twitter_technical_ratio": tech_ratio,
    }
