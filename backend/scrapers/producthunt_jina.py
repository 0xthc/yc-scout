"""
Product Hunt daily leaderboard scraper — Jina reader edition.

Source: https://www.producthunt.com (daily top products)
Fetched via Jina reader: https://r.jina.ai/https://www.producthunt.com

Strategy:
  - Fetch today's PH leaderboard via Jina (no API key needed)
  - Parse product names + upvote counts from the rendered markdown
  - 2026-only filter: only scrape pages dated in 2026; skip any page whose
    date resolves to a year other than 2026
  - Only keep products with >= 150 upvotes
  - Returns list of dicts: {name, upvotes, source, date}
"""

import logging
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

JINA_BASE = "https://r.jina.ai/https://www.producthunt.com"
MIN_UPVOTES = 150

# 2026-only filter: reject pages/dates outside 2026
_TARGET_YEAR = 2026


def _jina_url_for_date(date: str) -> str:
    """
    Return the Jina reader URL for a specific PH leaderboard date.
    date format: YYYY-MM-DD  e.g. "2026-05-04"
    PH leaderboard URL pattern: https://www.producthunt.com/leaderboard/daily/YYYY/MM/DD
    """
    parts = date.split("-")
    if len(parts) != 3:
        return JINA_BASE
    yyyy, mm, dd = parts
    return f"https://r.jina.ai/https://www.producthunt.com/leaderboard/daily/{yyyy}/{mm}/{dd}"


def _fetch_markdown(url: str) -> str:
    """Fetch a PH page via Jina reader and return the markdown text."""
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": "Precognition/1.0", "Accept": "text/markdown"},
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as e:
        logger.warning("PH Jina fetch failed (%s): %s", url, e)
        return ""


def _parse_products(markdown: str, date: str) -> list[dict]:
    """
    Parse product name + upvote count + tagline from Jina-rendered PH leaderboard markdown.

    Jina renders PH leaderboard like:
      [N. ProductName](https://www.producthunt.com/products/slug)tagline text here
      ![Promoted](...)
      Categories
      <comments_count>
      <upvotes_count>

    We extract ranked entries via the [N. Name](url) link pattern, grab the tagline
    from the text immediately after the closing ')' on the same line, then grab
    the upvote count from the second standalone integer after that line.
    """
    products: dict[str, dict] = {}

    # Match ranked product links: [1. Mindra](https://www.producthunt.com/products/mindra)
    # Capture any trailing text on the same line as the tagline
    entry_re = re.compile(r'^\[(\d+)\.\s+([^\]]+)\]\(https://www\.producthunt\.com/products/[^\)]+\)(.*)')
    lines = markdown.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = entry_re.match(line)
        if m:
            name = m.group(2).strip()
            tagline = m.group(3).strip()
            # Scan ahead up to 8 lines for two consecutive integer-only lines
            # (comments count, then upvotes count)
            int_lines = []
            for j in range(i + 1, min(i + 9, len(lines))):
                candidate = lines[j].strip()
                if re.match(r'^\d+$', candidate):
                    int_lines.append(int(candidate))
                    if len(int_lines) == 2:
                        break
            if len(int_lines) >= 2:
                upvotes = int_lines[1]  # second int = upvotes
            elif len(int_lines) == 1:
                upvotes = int_lines[0]
            else:
                upvotes = 0
            if name not in products or products[name]["upvotes"] < upvotes:
                products[name] = {"upvotes": upvotes, "tagline": tagline}
        i += 1

    results = []
    for name, info in products.items():
        results.append({
            "name": name,
            "upvotes": info["upvotes"],
            "tagline": info["tagline"],
            "source": "producthunt_daily",
            "date": date,
        })
    return results


def scrape_producthunt_daily(date: str = None) -> list[dict]:
    """
    Scrape the Product Hunt daily leaderboard for a given date.

    2026-only filter: Only dates in 2026 are accepted. If the resolved date
    is outside 2026, an empty list is returned immediately.

    Args:
        date: ISO date string "YYYY-MM-DD". Defaults to today (UTC).

    Returns:
        List of dicts with keys: name, upvotes, tagline, source, date
        Only entries with upvotes >= 150 are included.
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 2026-only filter: reject dates outside 2026
    try:
        page_year = int(date.split("-")[0])
    except (ValueError, IndexError):
        page_year = 0
    if page_year != _TARGET_YEAR:
        logger.info("PH daily: skipping date %s — 2026-only filter (year=%s)", date, page_year)
        return []

    url = _jina_url_for_date(date)
    logger.info("PH daily: fetching leaderboard for %s via Jina", date)
    markdown = _fetch_markdown(url)
    if not markdown:
        logger.warning("PH daily: empty response for %s", date)
        return []

    all_products = _parse_products(markdown, date)
    logger.info("PH daily: parsed %d products for %s", len(all_products), date)

    # Filter by minimum upvotes
    filtered = [p for p in all_products if p["upvotes"] >= MIN_UPVOTES]
    logger.info(
        "PH daily: %d products with >= %d upvotes for %s",
        len(filtered), MIN_UPVOTES, date,
    )
    return filtered
