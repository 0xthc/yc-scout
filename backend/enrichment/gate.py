"""
Enrichment gate — decides which founders get enriched and when.

Rules:
  1. Only enrich founders whose composite score >= ENRICHMENT_SCORE_THRESHOLD (default 75)
  2. Never enrich a founder who was enriched < 30 days ago
  3. Refresh monthly if status is 'watching' or above
  4. Skip if both API keys are missing (no-op)

When a founder qualifies:
  1. Call Apify for Twitter data (if APIFY_API_TOKEN set)
  2. Call Proxycurl for LinkedIn data (if PROXYCURL_API_KEY set and linkedin_url known)
  3. Write enrichment data back to founders table
  4. Update enriched_at timestamp
"""

import logging

from backend.config import APIFY_API_TOKEN, PROXYCURL_API_KEY, ENRICHMENT_SCORE_THRESHOLD
from backend.enrichment.twitter import enrich_twitter
from backend.enrichment.linkedin import enrich_linkedin

logger = logging.getLogger(__name__)

# Status levels that trigger monthly refresh
REFRESH_STATUSES = {"watching", "contacted"}

# Days between enrichment refreshes
REFRESH_DAYS = 30


def _needs_enrichment(founder: dict, score: float) -> bool:
    """Determine if a founder should be enriched now."""
    if score < ENRICHMENT_SCORE_THRESHOLD:
        return False

    enriched_at = founder.get("enriched_at")

    # Never enriched → go
    if not enriched_at:
        return True

    # Check refresh eligibility
    status = founder.get("status", "")
    if status not in REFRESH_STATUSES:
        return False  # Only refresh if actively tracking

    # Check if 30 days have passed
    from datetime import datetime, timezone
    try:
        last = datetime.fromisoformat(enriched_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_since = (now - last).days
        return days_since >= REFRESH_DAYS
    except Exception:
        return True  # Malformed date → re-enrich


def _save_enrichment(conn, founder_id: int, data: dict) -> None:
    """Write enrichment results to the founders table."""
    allowed_cols = {
        "twitter_handle", "twitter_followers", "twitter_engagement_rate",
        "linkedin_url", "linkedin_summary", "is_serial_founder",
    }
    updates = {k: v for k, v in data.items() if k in allowed_cols}
    if not updates:
        return

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())

    conn.execute(
        f"UPDATE founders SET {sets}, enriched_at = CURRENT_TIMESTAMP WHERE id = ?",
        values + [founder_id],
    )


def enrich_qualified_founders(conn) -> int:
    """
    Run enrichment for all founders who qualify.
    Returns number of founders enriched.
    """
    if not APIFY_API_TOKEN and not PROXYCURL_API_KEY:
        logger.info("No enrichment API keys configured — skipping enrichment phase")
        return 0

    # Get founders with their latest composite score
    founders = conn.execute(
        """SELECT f.*,
                  (SELECT composite FROM scores
                   WHERE founder_id = f.id
                   ORDER BY scored_at DESC LIMIT 1) as latest_score
           FROM founders f"""
    ).fetchall()

    enriched_count = 0

    for f in founders:
        fid = f["id"]
        score = f["latest_score"] or 0
        founder_dict = {k: f[k] for k in f.keys()}

        if not _needs_enrichment(founder_dict, score):
            continue

        logger.info(
            "Enriching founder %d (%s) — score %.0f, status %s",
            fid, f["name"], score, f["status"],
        )

        enrichment_data = {}

        # Twitter enrichment
        if APIFY_API_TOKEN:
            handle = f["handle"] or ""
            # Try to use github handle as twitter handle (common overlap)
            if handle and not handle.startswith("http"):
                twitter_handle = handle.lstrip("@")
                try:
                    tw = enrich_twitter(twitter_handle)
                    if tw:
                        enrichment_data.update(tw)
                except Exception as e:
                    logger.error("Twitter enrichment failed for %d: %s", fid, e)

        # LinkedIn enrichment
        if PROXYCURL_API_KEY:
            linkedin_url = f.get("linkedin_url", "") or ""
            if linkedin_url:
                try:
                    li = enrich_linkedin(linkedin_url)
                    if li:
                        enrichment_data.update(li)
                except Exception as e:
                    logger.error("LinkedIn enrichment failed for %d: %s", fid, e)
            else:
                logger.debug("Founder %d has no linkedin_url — skipping LinkedIn", fid)

        if enrichment_data:
            _save_enrichment(conn, fid, enrichment_data)
            enriched_count += 1
            logger.info("Enriched founder %d with %d fields", fid, len(enrichment_data))
        else:
            # Still mark as attempted so we don't retry immediately
            conn.execute(
                "UPDATE founders SET enriched_at = CURRENT_TIMESTAMP WHERE id = ?", (fid,)
            )

    logger.info("Enrichment complete: %d founders enriched", enriched_count)
    return enriched_count
