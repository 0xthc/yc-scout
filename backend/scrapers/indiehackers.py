"""
Indie Hackers scraper — no API key required.

Strategy:
  1. Fetch IH homepage + /starting-up and /products pages (SSR-rendered HTML)
  2. Extract product launch posts (URLs containing /product/) with upvote counts
  3. Skip generic discussion posts — focus on founders who have launched something
  4. For each author, try to reconcile with an existing founder (GitHub handle match)
  5. If no match, create a new IH-origin founder entry
  6. Threshold: NOTABLE_UPVOTES = 20, STRONG_UPVOTES = 100

Signal meaning for Precognition:
  A founder posting a product launch on IH with notable upvotes = product exists,
  early users, pre-raise, community traction. This is exactly the pre-visible
  window between "building" and "announced round".
"""

import logging
import re
import time

import httpx

from backend.db import (
    add_signal,
    add_source,
    add_tags,
    save_stats,
    upsert_founder,
)

logger = logging.getLogger(__name__)

NOTABLE_UPVOTES = 20
STRONG_UPVOTES = 100

PAGES_TO_SCRAPE = [
    "https://www.indiehackers.com/",
    "https://www.indiehackers.com/starting-up",
    "https://www.indiehackers.com/tech",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Precognition/1.0; +https://yc-scout.onrender.com)",
    "Accept": "text/html,application/xhtml+xml",
}

# HTML patterns for IH server-rendered pages
# Product post URL: <a href="/product/slug?post=ID" class="...story__text-link...">
_PRODUCT_HREF_RE = re.compile(r'href="(/product/([a-z0-9_-]+)\?post=[A-Za-z0-9]+)"[^>]*class="[^"]*story__text-link')
# Post title: <h3 class="story__title">TITLE</h3>
_TITLE_RE = re.compile(r'class="story__title">\s*([^<]+?)\s*</')
# Author username: <span class="user-link__name user-link__name--username">USERNAME</span>
_AUTHOR_NAME_RE = re.compile(r'class="user-link__name user-link__name--username">\s*([A-Za-z0-9_.-]+)\s*</')
# Upvote count: <span class="story__count-number">N</span>\n<span class="story__count-text">upvotes</span>
_UPVOTE_BLOCK_RE = re.compile(
    r'class="story__count-number">(\d+)</span>\s*\n\s*<span class="story__count-text">upvotes?</span>',
)

# Try to find GitHub usernames in IH profile bios or post content
_GH_RE = re.compile(r'github\.com/([A-Za-z0-9_.-]+)', re.IGNORECASE)


def _fetch_page(url):
    """Fetch a page and return text, or None on failure."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning("IH fetch failed for %s: %s", url, e)
        return None


def _parse_posts(html):
    """
    Extract product launch posts from IH HTML.

    IH renders HTML with these patterns:
      <a href="/product/slug?post=ID" class="...story__text-link...">
      <h3 class="story__title">TITLE</h3>
      <span class="user-link__name ...">USERNAME</span>
      <span class="story__count-number">N</span>
      <span class="story__count-text">upvotes</span>
    """
    results = []
    if not html:
        return results

    # Split HTML into story blocks on product link anchors — each block is one post
    # We split on each story__text-link for a product URL
    chunks = _PRODUCT_HREF_RE.split(html)
    # split gives: [pre, path, slug, post, path, slug, post, ...]
    # chunks[0] is pre-content, then groups of 3: (full_path, slug, following_html)
    # Actually re.split with groups returns: [before, g1, g2, after, g1, g2, after ...]
    # So: chunks[0]=pre, chunks[1]=path, chunks[2]=slug, chunks[3]=content_until_next, etc.

    i = 1
    while i + 2 < len(chunks):
        post_path = chunks[i]    # e.g. /product/leadsynthai?post=xxx
        slug = chunks[i + 1]    # e.g. leadsynthai
        block = chunks[i + 2]   # HTML content following this story's link

        # Extract title
        tm = _TITLE_RE.search(block)
        title = tm.group(1).strip() if tm else slug.replace("-", " ").title()

        # Extract author
        am = _AUTHOR_NAME_RE.search(block)
        author = am.group(1).strip() if am else None

        # Extract upvotes
        vm = _UPVOTE_BLOCK_RE.search(block)
        upvotes = int(vm.group(1)) if vm else 0

        if author and upvotes >= NOTABLE_UPVOTES:
            results.append({
                "title": title,
                "slug": slug,
                "author": author,
                "upvotes": upvotes,
                "url": f"https://www.indiehackers.com{post_path}",
            })

        i += 3

    return results


def _row_val(row, key):
    try:
        return row[key]
    except Exception:
        try:
            return row[0]
        except Exception:
            return None


def _find_existing_founder(conn, author_username):
    """Try to match IH author to existing founder by handle."""
    # Direct handle match: IH username sometimes matches GitHub handle
    for handle_fmt in [f"@{author_username}", author_username]:
        row = conn.execute(
            "SELECT id FROM founders WHERE handle = ?", (handle_fmt,)
        ).fetchone()
        if row:
            fid = _row_val(row, "id")
            return fid

    # Check if they have a GitHub source with matching username
    row = conn.execute(
        "SELECT founder_id FROM founder_sources WHERE source = 'github' AND source_id = ?",
        (author_username,),
    ).fetchone()
    if row:
        return _row_val(row, "founder_id")

    return None


def scrape_indiehackers(conn, pages=None):
    """
    Scrape Indie Hackers for founder signals.

    Returns number of founders processed.
    """
    if pages is None:
        pages = PAGES_TO_SCRAPE

    seen_authors = set()
    processed = 0
    reconciled = 0

    for url in pages:
        html = _fetch_page(url)
        if not html:
            continue

        posts = _parse_posts(html)
        logger.info("IH: found %d notable product posts on %s", len(posts), url)

        for post in posts:
            author = post["author"]
            if author in seen_authors:
                continue
            seen_authors.add(author)

            upvotes = post["upvotes"]
            is_strong = upvotes >= STRONG_UPVOTES
            post_url = post["url"]
            title = post["title"]

            # Try to reconcile with existing founder
            fid = _find_existing_founder(conn, author)
            if fid:
                reconciled += 1
            else:
                # Create new IH-origin founder
                fid = upsert_founder(
                    conn,
                    name=author,
                    handle=f"@ih-{author.lower()}",
                    bio=f"Indie Hacker — {title[:200]}",
                    company=post["slug"].replace("-", " ").title(),
                    entity_type="startup",
                )

            # Add IH as a source
            add_source(
                conn, fid, "indiehackers",
                source_id=author,
                profile_url=f"https://www.indiehackers.com/{author}",
            )

            # Add launch signal
            label = f"{title[:80]} — {upvotes} upvotes"
            add_signal(
                conn, fid, "indiehackers",
                label=label,
                url=post_url,
                strong=is_strong,
            )

            # Basic stats — ph_upvotes reused for IH upvotes as proxy
            save_stats(conn, fid, ph_upvotes=upvotes, ph_launches=1)

            processed += 1
            time.sleep(0.2)

        time.sleep(1)  # Polite pause between page fetches

    logger.info(
        "IH scraper done: %d founders processed (%d reconciled, %d new)",
        processed, reconciled, processed - reconciled,
    )
    return processed
