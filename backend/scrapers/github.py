"""
GitHub scraper using the REST API v3.

Docs: https://docs.github.com/en/rest

Strategy:
  1. Search for trending repos / users with high activity
  2. For each user: fetch profile, repos, commit activity
  3. Detect strong signals: fast star growth, high commit velocity, new repos
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from backend.config import GITHUB_TOKEN
from backend.db import (
    add_signal,
    add_source,
    add_tags,
    save_stats,
    upsert_founder,
)
from backend.incubators import detect_incubator, format_incubator

logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"
STRONG_STARS = 500
STRONG_COMMITS_90D = 300


def _headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


class RateLimitError(Exception):
    pass

def _get(path, params=None):
    resp = httpx.get(f"{GH_API}{path}", headers=_headers(), params=params, timeout=15)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        # Check reset time — if long wait, skip rather than block pipeline
        reset_ts = resp.headers.get("x-ratelimit-reset")
        wait = (int(reset_ts) - int(time.time())) if reset_ts else 120
        if wait > 30:
            logger.warning("GitHub rate limit hit — wait %ds, skipping to avoid pipeline timeout", wait)
            raise RateLimitError("rate limit exceeded")
        logger.warning("GitHub rate limit hit, sleeping %ds", wait)
        time.sleep(wait + 2)
        resp = httpx.get(f"{GH_API}{path}", headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _search_repos(query, sort="stars", per_page=30):
    """Search GitHub repos."""
    return _get("/search/repositories", {
        "q": query,
        "sort": sort,
        "per_page": per_page,
    }).get("items", [])


def _user_repos(username, per_page=100):
    """Fetch a user's public repos sorted by updated."""
    return _get(f"/users/{username}/repos", {
        "sort": "updated",
        "per_page": per_page,
        "type": "owner",
    })


def _user_profile(username):
    return _get(f"/users/{username}")


def _commit_count_90d(username):
    """Estimate commits in last 90 days via the search API."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        data = _get("/search/commits", {
            "q": f"author:{username} committer-date:>{cutoff}",
            "per_page": 1,
        })
        return data.get("total_count", 0)
    except httpx.HTTPError:
        return 0


def scrape_github(conn, search_queries=None, num_days=90):
    """
    Scrape GitHub for founder signals.

    Args:
        conn: SQLite connection
        search_queries: Optional list of repo search queries.
        num_days: How far back to look for active repos (default 90 days).

    Returns:
        Number of founders processed.
    """
    if search_queries is None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=num_days)).strftime("%Y-%m-%d")
        # 30-day window for early-stage repos
        early_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        # GitHub Search API: 30 req/min authenticated — keep total queries ≤ 25
        search_queries = [
            # ── Established repos (90-day window, higher bar) ─────────────────
            f"stars:>50 pushed:>{cutoff} topic:ai",
            f"stars:>50 pushed:>{cutoff} topic:llm",
            f"stars:>50 pushed:>{cutoff} topic:agents",
            f"stars:>50 pushed:>{cutoff} topic:devtools",
            f"stars:>50 pushed:>{cutoff} topic:infrastructure",
            f"stars:>50 pushed:>{cutoff} topic:database",
            f"stars:>50 pushed:>{cutoff} topic:saas",
            f"stars:>50 pushed:>{cutoff} topic:fintech",
            f"stars:>50 pushed:>{cutoff} topic:security",
            f"stars:>50 pushed:>{cutoff} topic:analytics",
            f"stars:>30 pushed:>{cutoff} topic:automation",
            f"stars:>30 pushed:>{cutoff} topic:b2b",
            f"stars:>30 pushed:>{cutoff} topic:healthtech",
            f"stars:>30 pushed:>{cutoff} topic:marketplace",
            # ── Early-stage: 30-day window, lower bar ─────────────────────────
            # 10+ stars in 30 days for a new repo = real developer interest
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:ai",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:llm",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:agents",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:devtools",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:saas",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:infrastructure",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:automation",
            f"stars:>10 created:>{early_cutoff} pushed:>{early_cutoff} topic:fintech",
            # ── Incubator-affiliated ───────────────────────────────────────────
            f"stars:>5 pushed:>{cutoff} topic:ycombinator",
            f"stars:>5 pushed:>{cutoff} topic:yc",
            f"stars:>5 pushed:>{cutoff} topic:500startups",
        ]

    seen_users = set()
    processed = 0

    # Pre-load recently scraped GitHub handles to skip re-fetching their profiles.
    # Founders updated within the last 24h don't need a fresh API round-trip —
    # the signals and stats are still current. This prevents rate limit exhaustion
    # when the DB has hundreds of founders and the pipeline runs every hour.
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recently_scraped = set(
        row[0].lstrip("@")
        for row in conn.execute(
            """SELECT f.handle FROM founders f
               JOIN founder_sources s ON s.founder_id = f.id
               WHERE s.source = 'github' AND f.updated_at > ?""",
            (cutoff_ts,),
        ).fetchall()
        if row[0]
    )
    logger.info("Skipping %d GitHub founders updated in last 24h", len(recently_scraped))

    for i, query in enumerate(search_queries):
        # GitHub Search API limit: 30 req/min authenticated.
        # Sleep 2.5s between queries to stay safely under the cap.
        if i > 0:
            time.sleep(2.5)
        try:
            repos = _search_repos(query)
        except httpx.HTTPError as e:
            logger.warning("GitHub search failed for '%s': %s", query, e)
            continue

        for repo in repos:
            owner = repo.get("owner", {})
            username = owner.get("login", "")
            if not username or username in seen_users or owner.get("type") == "Organization":
                continue
            seen_users.add(username)

            # Skip full API round-trip if we already have fresh data for this user
            if username in recently_scraped:
                continue

            try:
                profile = _user_profile(username)
            except httpx.HTTPError:
                logger.warning("Failed to fetch GitHub user: %s", username)
                continue

            # Upsert founder — detect incubator from bio
            handle = f"@{username}"
            name = profile.get("name") or username
            bio = profile.get("bio") or ""
            location = profile.get("location") or ""
            followers = profile.get("followers", 0)

            inc_name, inc_batch = detect_incubator(bio)
            incubator_str = format_incubator(inc_name, inc_batch)

            fid = upsert_founder(
                conn,
                name=name,
                handle=handle,
                bio=bio[:500],
                location=location,
                **({"incubator": incubator_str} if incubator_str else {}),
            )
            add_source(
                conn, fid, "github",
                source_id=username,
                profile_url=profile.get("html_url", ""),
            )

            # Analyze repos for signals
            try:
                user_repos = _user_repos(username)
            except httpx.HTTPError:
                user_repos = [repo]

            total_stars = 0
            repo_count = 0
            repo_names = []

            for r in user_repos:
                if r.get("fork"):
                    continue
                stars = r.get("stargazers_count", 0)
                total_stars += stars
                repo_count += 1
                repo_names.append(r.get("name", ""))

                if stars >= STRONG_STARS:
                    add_signal(
                        conn, fid, "github",
                        label=f"{r['name']} — {stars:,} stars",
                        url=r.get("html_url", ""),
                        strong=True,
                    )
                elif stars >= 50:
                    add_signal(
                        conn, fid, "github",
                        label=f"{r['name']} — {stars:,} stars",
                        url=r.get("html_url", ""),
                        strong=False,
                    )

            # Commit activity
            commits_90d = _commit_count_90d(username)
            if commits_90d >= STRONG_COMMITS_90D:
                add_signal(
                    conn, fid, "github",
                    label=f"{commits_90d} commits in 90 days",
                    strong=True,
                )
            elif commits_90d >= 100:
                add_signal(
                    conn, fid, "github",
                    label=f"{commits_90d} commits in 90 days",
                    strong=False,
                )

            # New repos signal
            recent_repos = [r for r in user_repos if not r.get("fork") and _is_recent(r)]
            if len(recent_repos) >= 3:
                names = ", ".join(r["name"] for r in recent_repos[:3])
                add_signal(
                    conn, fid, "github",
                    label=f"{len(recent_repos)} new repos: {names}",
                    strong=False,
                )

            # Infer tags from repo topics + detect incubator from topics
            tags = set()
            for r in user_repos[:10]:
                for topic in r.get("topics", []):
                    tags.add(topic)
                # Check repo description for incubator mentions
                if not incubator_str:
                    desc = r.get("description") or ""
                    inc_name, inc_batch = detect_incubator(desc)
                    incubator_str = format_incubator(inc_name, inc_batch)

            # Check topics for incubator affiliation
            if not incubator_str:
                incubator_topics = {
                    "ycombinator": "YC", "yc": "YC", "y-combinator": "YC",
                    "500startups": "500 Global", "500-startups": "500 Global",
                    "plugandplay": "Plug and Play", "plug-and-play": "Plug and Play",
                }
                for topic in tags:
                    if topic.lower() in incubator_topics:
                        incubator_str = incubator_topics[topic.lower()]
                        break

            if incubator_str:
                conn.execute(
                    "UPDATE founders SET incubator = ? WHERE id = ? AND (incubator IS NULL OR incubator = '')",
                    (incubator_str, fid),
                )
                tags.add(incubator_str.lower().replace(" ", "-"))

            if tags:
                add_tags(conn, fid, list(tags)[:10])

            # Save stats
            save_stats(
                conn, fid,
                github_stars=total_stars,
                github_commits_90d=commits_90d,
                github_repos=repo_count,
                followers=followers,
            )

            processed += 1
            time.sleep(0.5)  # Rate limiting

    logger.info("GitHub scraper processed %d founders", processed)
    return processed


def _is_recent(repo, days=30):
    created = repo.get("created_at", "")
    if not created:
        return False
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days <= days
    except ValueError:
        return False
