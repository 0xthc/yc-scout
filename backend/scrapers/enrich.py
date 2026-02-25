"""
Cross-platform enrichment — after initial scraping, proactively check
other platforms for founders already in the database.

If a founder was discovered on HN, check whether they exist on GitHub and
Product Hunt (and vice-versa).  This closes the coverage gap where the same
person is active on multiple platforms but only happened to be "trending"
on one of them during a given pipeline run.
"""

import logging
import re
import time

import httpx

from backend.config import GITHUB_TOKEN, PH_API_TOKEN
from backend.db import add_signal, add_source, add_tags, save_stats
from backend.incubators import detect_incubator, format_incubator

logger = logging.getLogger(__name__)

# ── GitHub helpers ───────────────────────────────────────────

GH_API = "https://api.github.com"
_GH_URL_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)(?:/|$)")
_GH_NON_USER_PATHS = frozenset({
    "features", "pricing", "enterprise", "topics", "trending",
    "explore", "settings", "orgs", "about", "security", "login",
})


def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _gh_get(path, params=None):
    resp = httpx.get(f"{GH_API}{path}", headers=_gh_headers(), params=params, timeout=15)
    if resp.status_code == 404:
        return None
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        logger.warning("GitHub rate limit hit during enrichment, sleeping 60s")
        time.sleep(60)
        resp = httpx.get(f"{GH_API}{path}", headers=_gh_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _extract_github_username(text):
    """Extract a GitHub username from a URL or bio text."""
    if not text:
        return None
    m = _GH_URL_RE.search(text)
    if m:
        username = m.group(1)
        if username.lower() not in _GH_NON_USER_PATHS:
            return username
    return None


def _enrich_from_github(conn, fid, username):
    """Given a GitHub username, fetch profile + repos and attach to founder."""
    profile = _gh_get(f"/users/{username}")
    if not profile or profile.get("type") == "Organization":
        return False

    add_source(
        conn, fid, "github",
        source_id=username,
        profile_url=profile.get("html_url", ""),
    )

    # Check bio for incubator affiliation
    bio = profile.get("bio") or ""
    inc_name, inc_batch = detect_incubator(bio)
    incubator_str = format_incubator(inc_name, inc_batch)

    # Fetch repos for signals
    repos = _gh_get(f"/users/{username}/repos", {
        "sort": "updated", "per_page": 100, "type": "owner",
    })
    if not repos:
        repos = []

    total_stars = 0
    repo_count = 0
    tags = set()

    for r in repos:
        if r.get("fork"):
            continue
        stars = r.get("stargazers_count", 0)
        total_stars += stars
        repo_count += 1

        if stars >= 500:
            add_signal(conn, fid, "github",
                       label=f"{r['name']} — {stars:,} stars",
                       url=r.get("html_url", ""), strong=True)
        elif stars >= 50:
            add_signal(conn, fid, "github",
                       label=f"{r['name']} — {stars:,} stars",
                       url=r.get("html_url", ""), strong=False)

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

    # Commit activity
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        data = _gh_get("/search/commits", {
            "q": f"author:{username} committer-date:>{cutoff}",
            "per_page": 1,
        })
        commits_90d = data.get("total_count", 0) if data else 0
    except httpx.HTTPError:
        commits_90d = 0

    if commits_90d >= 300:
        add_signal(conn, fid, "github",
                   label=f"{commits_90d} commits in 90 days", strong=True)
    elif commits_90d >= 100:
        add_signal(conn, fid, "github",
                   label=f"{commits_90d} commits in 90 days", strong=False)

    save_stats(conn, fid,
               github_stars=total_stars,
               github_commits_90d=commits_90d,
               github_repos=repo_count,
               followers=profile.get("followers", 0))

    logger.debug("Enriched founder %d with GitHub data (@%s)", fid, username)
    return True


# ── HN helpers ───────────────────────────────────────────────

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"


def _enrich_from_hn(conn, fid, username):
    """Given an HN username, fetch profile + posts and attach to founder."""
    try:
        resp = httpx.get(f"{FIREBASE_BASE}/user/{username}.json", timeout=10)
        resp.raise_for_status()
        user_data = resp.json()
    except httpx.HTTPError:
        return False

    if not user_data:
        return False

    karma = user_data.get("karma", 0)

    add_source(
        conn, fid, "hn",
        source_id=username,
        profile_url=f"https://news.ycombinator.com/user?id={username}",
    )

    # Fetch posts for signals
    try:
        resp = httpx.get(f"{ALGOLIA_BASE}/search", params={
            "tags": f"author_{username},story",
            "hitsPerPage": 30,
        }, timeout=15)
        resp.raise_for_status()
        posts = resp.json().get("hits", [])
    except httpx.HTTPError:
        posts = []

    hn_top_score = 0
    hn_submissions = len(posts)

    for post in posts:
        points = post.get("points", 0) or 0
        title = post.get("title", "")
        hn_top_score = max(hn_top_score, points)

        if points >= 50:
            is_show = title.lower().startswith("show hn")
            prefix = "Show HN" if is_show else "HN"
            post_url = f"https://news.ycombinator.com/item?id={post.get('objectID', '')}"
            add_signal(conn, fid, "hn",
                       label=f"{prefix}: {title.split(':', 1)[-1].strip() if ':' in title else title} — {points} pts",
                       url=post_url, strong=points >= 200)

    save_stats(conn, fid,
               hn_karma=karma,
               hn_submissions=hn_submissions,
               hn_top_score=hn_top_score)

    logger.debug("Enriched founder %d with HN data (@%s)", fid, username)
    return True


# ── Product Hunt helpers ─────────────────────────────────────

PH_API_URL = "https://api.producthunt.com/v2/api/graphql"

PH_USER_SEARCH_QUERY = """
query($username: String!) {
  user(username: $username) {
    id
    name
    username
    headline
    madePosts(first: 10) {
      edges {
        node {
          id
          name
          tagline
          slug
          url
          votesCount
          featuredAt
          topics(first: 5) {
            edges {
              node { name }
            }
          }
        }
      }
    }
  }
}
"""


def _ph_graphql(query, variables=None):
    if not PH_API_TOKEN:
        return None
    headers = {
        "Authorization": f"Bearer {PH_API_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(PH_API_URL, json={"query": query, "variables": variables or {}},
                      headers=headers, timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("data")


def _enrich_from_producthunt(conn, fid, username):
    """Given a username, try to find them on Product Hunt and attach data."""
    if not PH_API_TOKEN:
        return False

    data = _ph_graphql(PH_USER_SEARCH_QUERY, {"username": username})
    if not data or not data.get("user"):
        return False

    user = data["user"]
    made_posts = user.get("madePosts", {}).get("edges", [])
    if not made_posts:
        return False

    # They exist on PH and have launched products
    first_post = made_posts[0].get("node", {})
    add_source(conn, fid, "producthunt",
               source_id=first_post.get("id", ""),
               profile_url=first_post.get("url", ""))

    total_upvotes = 0
    launches = 0
    all_topics = set()

    for edge in made_posts:
        post = edge.get("node", {})
        votes = post.get("votesCount", 0)
        total_upvotes += votes
        launches += 1
        featured = post.get("featuredAt") is not None

        topics = [t["node"]["name"].lower()
                  for t in post.get("topics", {}).get("edges", [])]
        all_topics.update(topics)

        if votes >= 100:
            if featured:
                label = f"Product of the Day — {post['name']}"
            else:
                label = f"{post['name']} — {votes} upvotes"
            add_signal(conn, fid, "producthunt", label,
                       url=post.get("url", ""), strong=votes >= 500 or featured)

    if all_topics:
        add_tags(conn, fid, list(all_topics)[:10])

    save_stats(conn, fid, ph_upvotes=total_upvotes, ph_launches=launches)

    logger.debug("Enriched founder %d with PH data (@%s)", fid, username)
    return True


# ── Main enrichment orchestrator ─────────────────────────────


def _row_val(row, key):
    """Extract a value from a row that might be sqlite3.Row or _TursoRow."""
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def enrich_founders(conn):
    """
    Cross-platform enrichment pass.

    For every founder in the DB, check which sources they're missing and
    try to find them on those platforms.  Uses the founder's handle, bio,
    and existing source data to derive usernames for the missing platforms.

    Returns:
        Number of new source links created.
    """
    founders = conn.execute("""
        SELECT f.id, f.handle, f.name, f.bio
        FROM founders f
    """).fetchall()

    # Build a map of existing sources per founder
    all_sources = conn.execute(
        "SELECT founder_id, source, source_id FROM founder_sources"
    ).fetchall()

    source_map = {}  # fid -> {source: source_id}
    for row in all_sources:
        fid = _row_val(row, "founder_id") or row[0]
        src = _row_val(row, "source") or row[1]
        sid = _row_val(row, "source_id") or row[2]
        source_map.setdefault(fid, {})[src] = sid

    enriched = 0
    github_rate_limited = False  # once hit, skip all remaining GitHub enrichment

    for founder in founders:
        fid = _row_val(founder, "id") or founder[0]
        handle = _row_val(founder, "handle") or founder[1]
        bio = _row_val(founder, "bio") or founder[3] or ""
        existing = source_map.get(fid, {})

        # Clean handle: remove @ prefix and ph- prefix
        clean_handle = handle.lstrip("@")
        if clean_handle.startswith("ph-"):
            clean_handle = None  # Product-only entries don't have a reusable username

        # ── Try GitHub enrichment ────────────────────────
        if "github" not in existing and not github_rate_limited:
            gh_username = None

            # Check if their bio or handle hints at a GitHub username
            if clean_handle:
                gh_username = clean_handle

            # Also check bio for github.com links
            bio_gh = _extract_github_username(bio)
            if bio_gh:
                gh_username = bio_gh

            if gh_username:
                try:
                    if _enrich_from_github(conn, fid, gh_username):
                        enriched += 1
                        time.sleep(0.5)
                        continue  # Move to next founder after a successful enrichment
                except Exception as e:
                    logger.warning("GitHub enrichment failed for %s: %s", gh_username, e)
                    from backend.scrapers.github import RateLimitError
                    if isinstance(e, RateLimitError):
                        logger.warning("GitHub rate limit hit — skipping remaining GitHub enrichment this run")
                        github_rate_limited = True

        # ── Try HN enrichment ────────────────────────────
        if "hn" not in existing and clean_handle:
            try:
                if _enrich_from_hn(conn, fid, clean_handle):
                    enriched += 1
                    time.sleep(0.3)
            except Exception as e:
                logger.warning("HN enrichment failed for %s: %s", clean_handle, e)

        # ── Try Product Hunt enrichment ──────────────────
        if "producthunt" not in existing and clean_handle:
            try:
                if _enrich_from_producthunt(conn, fid, clean_handle):
                    enriched += 1
                    time.sleep(0.3)
            except Exception as e:
                logger.warning("PH enrichment failed for %s: %s", clean_handle, e)

    logger.info("Cross-platform enrichment added %d new source links", enriched)
    return enriched
