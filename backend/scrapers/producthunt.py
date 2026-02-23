"""
Product Hunt scraper using the GraphQL API v2.

Docs: https://api.producthunt.com/v2/docs

Strategy (product-centric with automatic reconciliation):
  1. Fetch recent top posts (products) from Product Hunt
  2. For each product, try to match it to an existing founder in the DB
     (already discovered via HN or GitHub) using maker usernames, GitHub
     URLs, repo name matching, and company name matching
  3. If matched, attach PH signals/stats to that existing founder
  4. If no match, create a product-based founder entry
  5. Detect strong signals: Product of the Day, high upvote counts
"""

import logging
import re
import time

import httpx

from backend.config import PH_API_TOKEN
from backend.db import (
    add_signal,
    add_source,
    add_tags,
    save_stats,
    upsert_founder,
)

logger = logging.getLogger(__name__)

PH_API = "https://api.producthunt.com/v2/api/graphql"

STRONG_UPVOTES = 500
NOTABLE_UPVOTES = 100

_GH_URL_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)(?:/|$)")
_GH_NON_USER_PATHS = frozenset({
    "features", "pricing", "enterprise", "topics", "trending",
    "explore", "settings", "orgs", "about", "security", "login",
})


def _graphql(query, variables=None):
    """Execute a Product Hunt GraphQL query."""
    if not PH_API_TOKEN:
        logger.warning("PH_API_TOKEN not set, skipping Product Hunt scraper")
        return None
    headers = {
        "Authorization": f"Bearer {PH_API_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = httpx.post(
        PH_API,
        json={"query": query, "variables": variables or {}},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data")


POSTS_QUERY = """
query($first: Int!, $after: String) {
  posts(first: $first, after: $after, order: VOTES) {
    edges {
      node {
        id
        name
        tagline
        slug
        url
        website
        votesCount
        createdAt
        featuredAt
        topics(first: 5) {
          edges {
            node {
              name
            }
          }
        }
        makers {
          id
          name
          username
          headline
          profileImage
          websiteUrl
          twitterUsername
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

MAKER_POSTS_QUERY = """
query($userId: ID!) {
  user(id: $userId) {
    id
    name
    username
    headline
    madePosts(first: 10) {
      edges {
        node {
          name
          votesCount
          featuredAt
          url
        }
      }
    }
  }
}
"""


# ── Reconciliation helpers ────────────────────────────────────


def _extract_github_username(url):
    """Extract a GitHub username from a URL like https://github.com/user/repo."""
    if not url:
        return None
    m = _GH_URL_RE.search(url)
    if m:
        username = m.group(1)
        if username.lower() not in _GH_NON_USER_PATHS:
            return username
    return None


def _normalize(s):
    """Lowercase and strip non-alphanumeric chars for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _row_val(row, key):
    """Extract a value from a row that might be sqlite3.Row or _TursoRow."""
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def _find_existing_founder(conn, post, makers):
    """Try to match a PH product to an existing founder in the DB.

    Matching strategies (in priority order):
    1. Maker username matches an existing handle (@username)
    2. Maker Twitter username matches an existing handle
    3. Maker website contains a GitHub URL → match by handle or source_id
    4. Product website is a GitHub URL → match by handle or source_id
    5. Product name matches a GitHub repo name in existing signals
    6. Product name matches an existing founder's company name

    Returns (founder_id, reconciled_maker) if matched, (None, None) otherwise.
    The reconciled_maker is the maker dict that caused the match (for fetching
    full PH history), or None if matched by product data alone.
    """
    # Strategy 1: Maker username → existing handle
    for maker in makers:
        username = maker.get("username", "")
        if not username:
            continue
        row = conn.execute(
            "SELECT id FROM founders WHERE handle = ?", (f"@{username}",)
        ).fetchone()
        if row:
            fid = _row_val(row, "id") or row[0]
            logger.debug("PH reconcile: maker @%s → founder %d", username, fid)
            return fid, maker

    # Strategy 2: Maker Twitter username → existing handle
    for maker in makers:
        twitter = maker.get("twitterUsername", "")
        if not twitter:
            continue
        row = conn.execute(
            "SELECT id FROM founders WHERE handle = ?", (f"@{twitter}",)
        ).fetchone()
        if row:
            fid = _row_val(row, "id") or row[0]
            logger.debug("PH reconcile: twitter @%s → founder %d", twitter, fid)
            return fid, maker

    # Strategy 3: Maker website GitHub URL → existing handle or source_id
    for maker in makers:
        gh_user = _extract_github_username(maker.get("websiteUrl", ""))
        if not gh_user:
            continue
        fid = _match_github_user(conn, gh_user)
        if fid:
            logger.debug("PH reconcile: maker website github.com/%s → founder %d", gh_user, fid)
            return fid, maker

    # Strategy 4: Product website GitHub URL
    gh_user = _extract_github_username(post.get("website", ""))
    if gh_user:
        fid = _match_github_user(conn, gh_user)
        if fid:
            logger.debug("PH reconcile: product website github.com/%s → founder %d", gh_user, fid)
            # No specific maker to attribute — pick the first one if available
            return fid, makers[0] if makers else None

    # Strategy 5: Product name matches a GitHub repo name in signals
    product_name = post.get("name", "")
    norm_name = _normalize(product_name)
    if norm_name and len(norm_name) >= 3:
        rows = conn.execute(
            "SELECT DISTINCT founder_id, label FROM signals WHERE source = 'github'"
        ).fetchall()
        for row in rows:
            label = _row_val(row, "label") or row[1]
            # Signal labels look like "repo-name — 500 stars"
            sep = label.find(" \u2014 ")
            if sep == -1:
                continue
            repo_name = label[:sep]
            if _normalize(repo_name) == norm_name:
                fid = _row_val(row, "founder_id") or row[0]
                logger.debug(
                    "PH reconcile: product '%s' matched signal '%s' → founder %d",
                    product_name, label, fid,
                )
                return fid, makers[0] if makers else None

    # Strategy 6: Product name matches founder company
    if norm_name and len(norm_name) >= 3:
        rows = conn.execute(
            "SELECT id, company FROM founders WHERE company != ''"
        ).fetchall()
        for row in rows:
            company = _row_val(row, "company") or row[1]
            if _normalize(company) == norm_name:
                fid = _row_val(row, "id") or row[0]
                logger.debug(
                    "PH reconcile: product '%s' matched company '%s' → founder %d",
                    product_name, company, fid,
                )
                return fid, makers[0] if makers else None

    return None, None


def _match_github_user(conn, gh_username):
    """Try to find a founder by GitHub username (handle or source_id)."""
    row = conn.execute(
        "SELECT id FROM founders WHERE handle = ?", (f"@{gh_username}",)
    ).fetchone()
    if row:
        return _row_val(row, "id") or row[0]
    row = conn.execute(
        "SELECT founder_id FROM founder_sources WHERE source = 'github' AND source_id = ?",
        (gh_username,),
    ).fetchone()
    if row:
        return _row_val(row, "founder_id") or row[0]
    return None


# ── Main scraper ──────────────────────────────────────────────


def scrape_producthunt(conn, pages=3, per_page=20):
    """
    Scrape Product Hunt for founder signals (product-centric approach).

    Iterates over top products. For each product, tries to reconcile with
    an existing founder already in the DB (from HN or GitHub) using maker
    usernames, GitHub URLs, repo names, and company names. Creates a
    product-based entry only when no match is found.

    Args:
        conn: SQLite connection
        pages: Number of pages to fetch
        per_page: Posts per page

    Returns:
        Number of founders processed.
    """
    if not PH_API_TOKEN:
        logger.warning("PH_API_TOKEN not set, skipping Product Hunt scraper")
        return 0

    seen_founders = set()  # founder IDs already processed this run
    processed = 0
    reconciled_count = 0
    cursor = None

    for _ in range(pages):
        data = _graphql(POSTS_QUERY, {"first": per_page, "after": cursor})
        if not data:
            break

        posts = data.get("posts", {})
        edges = posts.get("edges", [])
        page_info = posts.get("pageInfo", {})

        for edge in edges:
            post = edge.get("node", {})
            votes = post.get("votesCount", 0)
            post_name = post.get("name", "")
            post_slug = post.get("slug", "")
            post_url = post.get("url", "")
            post_tagline = post.get("tagline", "")
            featured_at = post.get("featuredAt")
            makers = post.get("makers", []) or []

            topics = [
                t["node"]["name"].lower()
                for t in post.get("topics", {}).get("edges", [])
            ]

            # ── Reconcile or create ───────────────────────────
            fid, matched_maker = _find_existing_founder(conn, post, makers)
            reconciled = fid is not None

            if fid is None:
                # No match — create a product-based entry
                handle = f"@ph-{post_slug}" if post_slug else f"@ph-{post.get('id', '')}"
                fid = upsert_founder(
                    conn,
                    name=post_name,
                    handle=handle,
                    bio=post_tagline[:500],
                    company=post_name,
                )

            if fid in seen_founders:
                continue
            seen_founders.add(fid)

            if reconciled:
                reconciled_count += 1

            # ── Attach PH data to founder ─────────────────────
            add_source(
                conn, fid, "producthunt",
                source_id=post.get("id", ""),
                profile_url=post_url,
            )

            if topics:
                add_tags(conn, fid, topics[:10])

            # Signal from this post
            if votes >= NOTABLE_UPVOTES:
                is_featured = featured_at is not None
                strong = votes >= STRONG_UPVOTES or is_featured

                if is_featured:
                    label = f"Product of the Day \u2014 {post_name}"
                else:
                    label = f"{post_name} \u2014 {votes} upvotes"

                add_signal(
                    conn, fid, "producthunt", label,
                    url=post_url, strong=strong,
                )

            # ── Stats: fetch full maker history if we have a maker ─
            if matched_maker and matched_maker.get("id"):
                try:
                    maker_data = _graphql(
                        MAKER_POSTS_QUERY, {"userId": matched_maker["id"]}
                    )
                    if maker_data and maker_data.get("user"):
                        made_posts = (
                            maker_data["user"]
                            .get("madePosts", {})
                            .get("edges", [])
                        )
                        total_upvotes = 0
                        launches = 0
                        for mp in made_posts:
                            p = mp.get("node", {})
                            total_upvotes += p.get("votesCount", 0)
                            launches += 1
                            pv = p.get("votesCount", 0)
                            if pv >= NOTABLE_UPVOTES and p["name"] != post_name:
                                add_signal(
                                    conn, fid, "producthunt",
                                    label=f"{p['name']} \u2014 {pv} upvotes",
                                    url=p.get("url", ""),
                                    strong=pv >= STRONG_UPVOTES,
                                )

                        save_stats(
                            conn, fid,
                            ph_upvotes=total_upvotes,
                            ph_launches=launches,
                        )
                    else:
                        save_stats(conn, fid, ph_upvotes=votes, ph_launches=1)
                except httpx.HTTPError:
                    logger.warning(
                        "Failed to fetch PH maker posts for founder %d", fid,
                    )
                    save_stats(conn, fid, ph_upvotes=votes, ph_launches=1)
            else:
                # Product-only entry or no maker data — use this post's votes
                save_stats(conn, fid, ph_upvotes=votes, ph_launches=1)

            processed += 1
            time.sleep(0.3)

        cursor = page_info.get("endCursor")
        if not page_info.get("hasNextPage"):
            break

    logger.info(
        "Product Hunt scraper processed %d founders (%d reconciled, %d product-only)",
        processed, reconciled_count, processed - reconciled_count,
    )
    return processed
