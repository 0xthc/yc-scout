"""
YC Batch Scraper — pulls companies from YC's Algolia index (full 199+) with
fallback to the public YC API (~40 companies).
"""

import logging
import os
import time
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

YC_API = "https://api.ycombinator.com/v0.1/companies"

ALGOLIA_APP_ID = "45BWZJ1SGC"
ALGOLIA_URL = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"

# Batch code → Algolia display name mapping
ALGOLIA_BATCH_NAMES = {
    "S26": "Spring 2026",
    "W26": "Winter 2026",
    "S25": "Fall 2025",
    "W25": "Spring 2025",
}

# S26/W26 = primary signal, S25 = context only. Older batches excluded.
TARGET_BATCHES = ["S26", "W26", "S25"]

# Tech/AI tags we care about — filter to keep Precognition focused
RELEVANT_TAGS = {
    "artificial intelligence", "ai", "developer tools", "saas", "infrastructure",
    "generative ai", "machine learning", "fintech", "enterprise software",
    "robotics", "cybersecurity", "open source", "api", "data engineering",
    "climate tech", "biotech", "hardware", "applied ai", "llm", "agents",
}


def _fetch_batch(batch: str) -> list[dict]:
    """Fetch all companies for a given YC batch. Uses Algolia if key set, else public API."""
    algolia_key = os.environ.get("YC_ALGOLIA_KEY", "")
    if algolia_key:
        return _algolia_fetch_batch(batch, algolia_key)
    return _api_fetch_batch(batch)


def _algolia_fetch_batch(batch_code: str, api_key: str) -> list[dict]:
    """Fetch all companies via Algolia (up to 200 per page)."""
    batch_name = ALGOLIA_BATCH_NAMES.get(batch_code, batch_code)
    companies = []
    page = 0
    while True:
        payload = json.dumps({"requests": [{
            "indexName": "YCCompany_production",
            "params": f"query=&facetFilters=%5B%5B%22batch%3A{urllib.parse.quote(batch_name)}%22%5D%5D&hitsPerPage=200&page={page}&attributesToRetrieve=name,one_liner,batch,website,slug,tags,industries,team_size,status,long_description,city,country,locations,regions",
        }]}).encode()
        req = urllib.request.Request(
            ALGOLIA_URL, data=payload,
            headers={
                "x-algolia-application-id": ALGOLIA_APP_ID,
                "x-algolia-api-key": api_key,
                "Content-Type": "application/json",
                "Referer": "https://www.ycombinator.com/",
                "Origin": "https://www.ycombinator.com",
            }
        )
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=15).read())
        except Exception as e:
            logger.error("Algolia fetch failed for %s page %d: %s", batch_name, page, e)
            break
        hits = r["results"][0].get("hits", [])
        nb = r["results"][0].get("nbHits", 0)
        # Normalize Algolia fields to match public API format
        for h in hits:
            h.setdefault("oneLiner", h.pop("one_liner", "") or "")
            h.setdefault("longDescription", h.pop("long_description", "") or "")
            h.setdefault("teamSize", h.pop("team_size", 0) or 0)
            h.setdefault("batch", batch_code)
        companies.extend(hits)
        logger.info("Algolia %s page %d: %d/%d companies", batch_name, page, len(companies), nb)
        if len(hits) < 200 or (page + 1) * 200 >= nb:
            break
        page += 1
        time.sleep(0.3)
    return companies


def _api_fetch_batch(batch: str) -> list[dict]:
    """Fallback: public YC API (returns ~40 companies max)."""
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
        logger.info("YC API %s page %d: %d companies", batch, page, len(batch_companies))
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

    slug = company.get("slug") or name.lower().replace(" ", "-")
    batch_lower = batch.lower()
    return {
        "name": name,
        "handle": f"@yc-{batch_lower}-{slug}",
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
        if queries:
            sql = queries[0][0]
            for q in queries:
                conn.execute(sql, q[1])

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
        if queries:
            sql = queries[0][0]
            for q in queries:
                conn.execute(sql, q[1])

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
        [conn.execute(q[0], q[1]) for q in tag_queries[i:i + CHUNK]]

    added = len(to_insert)
    logger.info("YC scraper: %d new companies added, %d updated", added, len(to_update))
    return added
