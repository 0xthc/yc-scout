"""
Hacker News scraper using the official Firebase API + Algolia search.

Firebase API: https://hacker-news.firebaseio.com/v0/
Algolia API: https://hn.algolia.com/api/v1/

Strategy:
  1. Search Algolia for "Show HN" posts with high scores (potential founders)
  2. Fetch user profiles from Firebase for karma + submission history
  3. Detect strong signals: high-scoring Show HN posts, frequent front-page appearances
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from backend.db import (
    add_signal,
    add_source,
    add_tags,
    save_stats,
    upsert_founder,
)
from backend.incubators import detect_incubator, detect_incubator_from_signals, format_incubator

logger = logging.getLogger(__name__)

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"

# Minimum points for a Show HN post to be considered notable
SHOW_HN_MIN_POINTS = 50
STRONG_SIGNAL_POINTS = 200


def _algolia_search(query, tags="show_hn", hits_per_page=50, num_days=90):
    """Search Algolia HN API with filters."""
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=num_days)).timestamp())
    params = {
        "query": query,
        "tags": tags,
        "numericFilters": f"points>{SHOW_HN_MIN_POINTS},created_at_i>{cutoff}",
        "hitsPerPage": hits_per_page,
    }
    resp = httpx.get(f"{ALGOLIA_BASE}/search", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("hits", [])


def _algolia_user_posts(username, hits_per_page=30):
    """Fetch recent posts by a specific user."""
    params = {
        "tags": f"author_{username},story",
        "hitsPerPage": hits_per_page,
    }
    resp = httpx.get(f"{ALGOLIA_BASE}/search", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("hits", [])


def _firebase_user(username):
    """Fetch user profile from HN Firebase API."""
    resp = httpx.get(f"{FIREBASE_BASE}/user/{username}.json", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _time_ago(ts):
    """Convert a timestamp to a human-readable 'X ago' string."""
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    if delta.days > 7:
        return f"{delta.days // 7}w ago"
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    return f"{hours}h ago" if hours > 0 else "just now"


def _build_incubator_queries():
    """Generate incubator search queries with batch codes based on current date.

    YC runs two batches per year:
      - Winter (W): applications ~Sep, batch Jan-Mar, Demo Day ~Mar
      - Summer (S): applications ~Mar, batch Jun-Aug, Demo Day ~Aug

    We search for the current batch and the two most recent past batches,
    so the list stays fresh automatically.
    """
    now = datetime.now(timezone.utc)
    year_short = now.year % 100  # e.g. 26

    # Current and recent YC batch codes (last 3 batches to cover ~18 months)
    if now.month <= 6:
        # Jan-Jun: current batch is W{year}, recent are S{year-1}, W{year-1}
        batches = [f"W{year_short}", f"S{year_short - 1}", f"W{year_short - 1}"]
    else:
        # Jul-Dec: current batch is S{year}, recent are W{year}, S{year-1}
        batches = [f"S{year_short}", f"W{year_short}", f"S{year_short - 1}"]

    queries = [("Launch YC", "story")]
    for batch in batches:
        queries.append((f"YC {batch}", "story"))

    queries.extend([
        ("500 Startups", "story"),
        ("500 Global", "story"),
        ("Plug and Play", "story"),
    ])
    return queries


def scrape_hn(conn, search_terms=None, num_days=90):
    """
    Scrape HN for founder signals.

    Args:
        conn: SQLite connection
        search_terms: Optional list of search queries. Defaults to startup-related terms.
        num_days: How far back to search (default 90 days).

    Returns:
        Number of founders processed.
    """
    if search_terms is None:
        search_terms = [
            "", "API", "AI", "infrastructure", "SaaS", "open source",
            "developer tools", "devtools", "startup", "launch",
            "B2B", "fintech", "healthtech", "marketplace", "platform",
            "database", "security", "analytics", "ML",
        ]

    # Also search for "Launch YC" and incubator-related posts (story tag, not just show_hn).
    # Batch codes are computed dynamically from the current date so they never go stale.
    # YC runs Winter (W, Jan-Mar) and Summer (S, Jun-Aug) batches.
    incubator_queries = _build_incubator_queries()

    seen_users = set()
    processed = 0

    # Phase A: Show HN posts with startup search terms
    for term in search_terms:
        try:
            hits = _algolia_search(term, num_days=num_days)
        except httpx.HTTPError as e:
            logger.warning("Algolia search failed for '%s': %s", term, e)
            continue

        for hit in hits:
            author = hit.get("author")
            if not author or author in seen_users:
                continue
            seen_users.add(author)

            try:
                user_data = _firebase_user(author)
                if not user_data:
                    continue
            except httpx.HTTPError:
                logger.warning("Failed to fetch HN user: %s", author)
                continue

            karma = user_data.get("karma", 0)
            about = user_data.get("about", "") or ""

            # Upsert founder — detect incubator from bio
            handle = f"@{author}"
            inc_name, inc_batch = detect_incubator(about)
            incubator_str = format_incubator(inc_name, inc_batch)

            fid = upsert_founder(
                conn,
                name=author,
                handle=handle,
                bio=about[:500],
                **({"incubator": incubator_str} if incubator_str else {}),
            )
            add_source(
                conn, fid, "hn",
                source_id=author,
                profile_url=f"https://news.ycombinator.com/user?id={author}",
            )

            # Fetch user's recent posts for signals
            try:
                user_posts = _algolia_user_posts(author)
            except httpx.HTTPError:
                user_posts = [hit]

            hn_top_score = 0
            hn_submissions = len(user_posts)
            collected_signals = []

            for post in user_posts:
                points = post.get("points", 0) or 0
                title = post.get("title", "")
                hn_top_score = max(hn_top_score, points)
                post_url = f"https://news.ycombinator.com/item?id={post.get('objectID', '')}"

                if points >= SHOW_HN_MIN_POINTS:
                    is_show = title.lower().startswith("show hn")
                    is_ask = title.lower().startswith("ask hn")
                    is_launch = title.lower().startswith("launch")
                    prefix = "Show HN" if is_show else "Ask HN" if is_ask else "Launch" if is_launch else "HN"
                    strong = points >= STRONG_SIGNAL_POINTS

                    label = f"{prefix}: {title.split(':', 1)[-1].strip() if ':' in title else title} — {points} pts"
                    add_signal(
                        conn, fid, "hn", label,
                        url=post_url, strong=strong,
                    )
                    collected_signals.append({"label": label, "source": "hn", "strong": strong})

            # Check signals for incubator mentions if not detected from bio
            if not incubator_str:
                inc_name, inc_batch = detect_incubator_from_signals(collected_signals)
                incubator_str = format_incubator(inc_name, inc_batch)
                if incubator_str:
                    conn.execute(
                        "UPDATE founders SET incubator = ? WHERE id = ? AND (incubator IS NULL OR incubator = '')",
                        (incubator_str, fid),
                    )

            # Tag incubator
            if incubator_str:
                add_tags(conn, fid, [incubator_str.lower().replace(" ", "-")])

            # Save stats snapshot
            save_stats(
                conn, fid,
                hn_karma=karma,
                hn_submissions=hn_submissions,
                hn_top_score=hn_top_score,
            )

            processed += 1
            time.sleep(0.2)  # Rate limiting

    # Phase B: Incubator-specific searches (story tag, broader reach)
    for query, tag in incubator_queries:
        try:
            hits = _algolia_search(query, tags=tag, num_days=num_days)
        except httpx.HTTPError as e:
            logger.warning("Algolia incubator search failed for '%s': %s", query, e)
            continue

        for hit in hits:
            author = hit.get("author")
            if not author or author in seen_users:
                continue
            seen_users.add(author)

            try:
                user_data = _firebase_user(author)
                if not user_data:
                    continue
            except httpx.HTTPError:
                continue

            karma = user_data.get("karma", 0)
            about = user_data.get("about", "") or ""
            title = hit.get("title", "")

            # Detect incubator from the post title or bio
            inc_name, inc_batch = detect_incubator(title)
            if not inc_name:
                inc_name, inc_batch = detect_incubator(about)
            if not inc_name:
                # Infer from the query itself
                if "yc" in query.lower():
                    inc_name = "YC"
                elif "500" in query:
                    inc_name = "500 Global"
                elif "plug" in query.lower():
                    inc_name = "Plug and Play"
            incubator_str = format_incubator(inc_name, inc_batch)

            handle = f"@{author}"
            fid = upsert_founder(
                conn, name=author, handle=handle, bio=about[:500],
                **({"incubator": incubator_str} if incubator_str else {}),
            )
            add_source(conn, fid, "hn", source_id=author,
                       profile_url=f"https://news.ycombinator.com/user?id={author}")

            points = hit.get("points", 0) or 0
            post_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            if points >= 10:  # Lower threshold for incubator posts
                label = f"Launch: {title.split(':', 1)[-1].strip() if ':' in title else title} — {points} pts"
                add_signal(conn, fid, "hn", label, url=post_url, strong=points >= 100)

            if incubator_str:
                add_tags(conn, fid, [incubator_str.lower().replace(" ", "-")])

            save_stats(conn, fid, hn_karma=karma, hn_submissions=1, hn_top_score=points)
            processed += 1
            time.sleep(0.2)

    logger.info("HN scraper processed %d founders", processed)
    return processed
