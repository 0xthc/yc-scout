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
    Returns number of new companies added.
    """
    if batches is None:
        batches = TARGET_BATCHES

    added = 0
    for batch in batches:
        logger.info("Scraping YC batch: %s", batch)
        companies = _fetch_batch(batch)
        logger.info("YC %s: %d total companies fetched", batch, len(companies))

        relevant = [c for c in companies if _is_relevant(c)]
        logger.info("YC %s: %d relevant companies after filter", batch, len(relevant))

        for company in relevant:
            founder = _company_to_founder(company)
            added += _upsert_founder(conn, founder)
            time.sleep(0.05)

    logger.info("YC scraper: %d new companies added", added)
    return added


def _upsert_founder(conn, f: dict) -> int:
    """Insert founder if not already present (match on name + incubator). Returns 1 if inserted."""
    existing = conn.execute(
        "SELECT id FROM founders WHERE name = ? AND incubator = ?",
        (f["name"], f["incubator"]),
    ).fetchone()

    if existing:
        # Update bio/notes if blank
        conn.execute(
            """UPDATE founders SET
               bio = COALESCE(NULLIF(bio,''), ?),
               domain = COALESCE(NULLIF(domain,''), ?),
               location = COALESCE(NULLIF(location,''), ?),
               notes = COALESCE(NULLIF(notes,''), ?),
               updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (f["bio"], f["domain"], f["location"], f["notes"], existing["id"]),
        )
        founder_id = existing["id"]
        inserted = 0
    else:
        conn.execute(
            """INSERT INTO founders
               (name, handle, avatar, bio, domain, company, location, stage,
                incubator, founded, notes, status, entity_type, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'to_contact','startup', CURRENT_TIMESTAMP)""",
            (
                f["name"], f["handle"], f["avatar"], f["bio"],
                f["domain"], f["company"], f["location"],
                f["stage"], f["incubator"], f["founded"], f["notes"],
            ),
        )
        founder_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        inserted = 1

    # YC companies are identified by incubator field — no signal source insertion needed

    # Upsert tags
    existing_tags = {
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM founder_tags WHERE founder_id = ?", (founder_id,)
        ).fetchall()
    }
    for tag in f.get("tags", []):
        if tag not in existing_tags:
            conn.execute(
                "INSERT INTO founder_tags (founder_id, tag) VALUES (?,?)",
                (founder_id, tag),
            )

    return inserted
