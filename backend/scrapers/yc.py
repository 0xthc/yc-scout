"""
YC Batch Scraper — pulls companies from the public YC API.
Supports any batch (W26, S25, W25, …).
"""

import logging
import time
import urllib.request
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

YC_API = "https://api.ycombinator.com/v0.1/companies"

# Batches to track (most recent first)
TARGET_BATCHES = ["W26", "S25", "W25"]

# Tech/AI tags we care about — filter to keep Precognition focused
RELEVANT_TAGS = {
    "artificial intelligence", "ai", "developer tools", "saas", "infrastructure",
    "generative ai", "machine learning", "fintech", "enterprise software",
    "robotics", "cybersecurity", "open source", "api", "data engineering",
    "climate tech", "biotech", "hardware", "applied ai", "llm", "agents",
}


def _fetch_batch(batch: str) -> list[dict]:
    """Fetch all companies for a given YC batch."""
    companies = []
    page = 1
    while True:
        url = f"{YC_API}?batch={batch}&limit=100&page={page}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Precognition/1.0"})
            data = json.loads(urllib.request.urlopen(req, timeout=15).read())
        except Exception as e:
            logger.warning("YC API error (batch=%s page=%d): %s", batch, page, e)
            break

        batch_companies = data.get("companies", [])
        companies.extend(batch_companies)
        logger.info("YC %s page %d: %d companies", batch, page, len(batch_companies))

        if page >= data.get("totalPages", 1) or not batch_companies:
            break
        page += 1
        time.sleep(0.3)

    return companies


def _is_relevant(company: dict) -> bool:
    """Keep companies with at least one relevant tech/AI tag, or US-based."""
    tags = {t.lower() for t in company.get("tags", [])}
    industries = {i.lower() for i in company.get("industries", [])}

    # Keep if any relevant tag matches
    if tags & RELEVANT_TAGS:
        return True

    # Keep B2B companies (likely tech/SaaS)
    if "b2b" in industries:
        return True

    # Keep US-based regardless
    regions = company.get("regions", [])
    if any("united states" in r.lower() or "america" in r.lower() for r in regions):
        return True

    return False


def _company_to_founder(company: dict) -> dict:
    """Map a YC company dict to our founder schema."""
    name = company.get("name", "").strip()
    website = company.get("website", "").strip()
    one_liner = company.get("oneLiner", "").strip()
    long_desc = (company.get("longDescription") or "").strip()
    batch = company.get("batch", "")
    tags = company.get("tags", [])
    locations = company.get("locations", [])
    location = locations[0] if locations else ""
    team_size = company.get("teamSize") or 0

    # Derive domain from website
    domain = ""
    if website:
        domain = website.replace("https://", "").replace("http://", "").rstrip("/")

    # Truncate long description to ~400 chars for notes
    notes_desc = long_desc[:400] + ("…" if len(long_desc) > 400 else "")

    # Classify stage
    if team_size <= 2:
        stage = "Seed"
    elif team_size <= 10:
        stage = "Early"
    else:
        stage = "Growth"

    return {
        "name": name,
        "handle": f"@{company.get('slug', '')}",
        "avatar": name[:2].upper() if name else "YC",
        "bio": one_liner,
        "domain": domain,
        "company": name,
        "location": location,
        "stage": stage,
        "incubator": f"YC {batch}",
        "founded": batch,
        "sources": ["yc"],
        "tags": [t.lower().replace(" ", "_") for t in tags],
        "yc_url": company.get("url", ""),
        "notes": notes_desc,
    }


def scrape_yc(conn, batches: list[str] = None) -> int:
    """
    Scrape YC companies and upsert into the founders DB.
    Uses batched DB writes to minimise HTTP round-trips to Turso.
    Returns number of new companies added.
    """
    if batches is None:
        batches = TARGET_BATCHES

    # 1. Fetch all companies from YC API (pure HTTP, no DB)
    all_founders: list[dict] = []
    for batch in batches:
        logger.info("Scraping YC batch: %s", batch)
        companies = _fetch_batch(batch)
        relevant = [c for c in companies if _is_relevant(c)]
        logger.info("YC %s: %d/%d relevant", batch, len(relevant), len(companies))
        all_founders.extend(_company_to_founder(c) for c in relevant)

    if not all_founders:
        return 0

    # 2. Fetch all existing YC names in ONE query
    incubators = list({f["incubator"] for f in all_founders})
    ph = ",".join("?" * len(incubators))
    existing_rows = conn.execute(
        f"SELECT id, name, incubator FROM founders WHERE incubator IN ({ph})",
        incubators,
    ).fetchall()
    existing = {(r["name"], r["incubator"]): r["id"] for r in existing_rows}

    # 3. Split into new vs existing
    to_insert = [f for f in all_founders if (f["name"], f["incubator"]) not in existing]
    to_update = [f for f in all_founders if (f["name"], f["incubator"]) in existing]

    # 4. Batch-insert new companies (chunk to stay within Turso pipeline limits)
    CHUNK = 25
    for i in range(0, len(to_insert), CHUNK):
        chunk = to_insert[i:i + CHUNK]
        queries = [
            (
                """INSERT OR IGNORE INTO founders
                   (name, handle, avatar, bio, domain, company, location, stage,
                    incubator, founded, notes, status, entity_type, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'to_contact','startup',CURRENT_TIMESTAMP)""",
                (f["name"], f["handle"], f["avatar"], f["bio"], f["domain"],
                 f["company"], f["location"], f["stage"], f["incubator"],
                 f["founded"], f["notes"]),
            )
            for f in chunk
        ]
        conn.execute_batch(queries)

    # 5. Batch-update bio/domain for existing entries where blank
    for i in range(0, len(to_update), CHUNK):
        chunk = to_update[i:i + CHUNK]
        queries = [
            (
                """UPDATE founders SET
                   bio    = COALESCE(NULLIF(bio,''), ?),
                   domain = COALESCE(NULLIF(domain,''), ?),
                   notes  = COALESCE(NULLIF(notes,''), ?),
                   updated_at = CURRENT_TIMESTAMP
                   WHERE name = ? AND incubator = ?""",
                (f["bio"], f["domain"], f["notes"], f["name"], f["incubator"]),
            )
            for f in chunk
        ]
        conn.execute_batch(queries)

    # 6. Batch-insert tags (use subquery to resolve founder_id)
    tag_queries = []
    for f in all_founders:
        for tag in f.get("tags", []):
            tag_queries.append((
                """INSERT OR IGNORE INTO founder_tags (founder_id, tag)
                   SELECT id, ? FROM founders WHERE name = ? AND incubator = ? LIMIT 1""",
                (tag, f["name"], f["incubator"]),
            ))
    for i in range(0, len(tag_queries), CHUNK):
        conn.execute_batch(tag_queries[i:i + CHUNK])

    added = len(to_insert)
    logger.info("YC scraper: %d new companies added, %d updated", added, len(to_update))
    return added
