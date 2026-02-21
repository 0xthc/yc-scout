"""
Product Hunt scraper using the GraphQL API v2.

Docs: https://api.producthunt.com/v2/docs

Strategy:
  1. Fetch recent top posts from Product Hunt
  2. Extract maker profiles and product data
  3. Detect strong signals: Product of the Day/Week, high upvote counts
"""

import logging
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
        url
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


def scrape_producthunt(conn, pages=3, per_page=20):
    """
    Scrape Product Hunt for founder signals.

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

    seen_makers = set()
    processed = 0
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
            post_url = post.get("url", "")
            featured_at = post.get("featuredAt")

            # Extract topics
            topics = [
                t["node"]["name"].lower()
                for t in post.get("topics", {}).get("edges", [])
            ]

            for maker in post.get("makers", []):
                username = maker.get("username", "")
                if not username or username in seen_makers:
                    continue
                seen_makers.add(username)

                name = maker.get("name", username)
                headline = maker.get("headline", "")
                handle = f"@{username}"

                fid = upsert_founder(
                    conn,
                    name=name,
                    handle=handle,
                    bio=headline[:500],
                )
                add_source(
                    conn, fid, "producthunt",
                    source_id=maker.get("id", ""),
                    profile_url=f"https://www.producthunt.com/@{username}",
                )

                if topics:
                    add_tags(conn, fid, topics[:10])

                # Signal from this post
                if votes >= NOTABLE_UPVOTES:
                    is_featured = featured_at is not None
                    strong = votes >= STRONG_UPVOTES or is_featured

                    if is_featured:
                        label = f"Product of the Day — {post_name}"
                    else:
                        label = f"{post_name} — {votes} upvotes"

                    add_signal(
                        conn, fid, "producthunt", label,
                        url=post_url, strong=strong,
                    )

                # Fetch maker's other products for more context
                try:
                    maker_data = _graphql(MAKER_POSTS_QUERY, {"userId": maker["id"]})
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
                                    label=f"{p['name']} — {pv} upvotes",
                                    url=p.get("url", ""),
                                    strong=pv >= STRONG_UPVOTES,
                                )

                        save_stats(
                            conn, fid,
                            ph_upvotes=total_upvotes,
                            ph_launches=launches,
                        )
                except httpx.HTTPError:
                    logger.warning("Failed to fetch PH maker posts for: %s", username)
                    save_stats(conn, fid, ph_upvotes=votes, ph_launches=1)

                processed += 1
                time.sleep(0.3)

        cursor = page_info.get("endCursor")
        if not page_info.get("hasNextPage"):
            break

    logger.info("Product Hunt scraper processed %d founders", processed)
    return processed
