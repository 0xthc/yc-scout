"""
Non-YC Accelerator Scraper — two layers:

Layer 1: Curated seed file (seeds.json) — manually maintained batch lists
Layer 2: HN "Launch HN" watcher — catches companies as they announce

Supported: Techstars · 500 Global · Plug and Play · a16z Speedrun · HF0 · Pioneer
"""

import json
import logging
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

SEEDS_FILE = Path(__file__).parent / "accelerator_seeds.json"

# HN search patterns per accelerator — matches against Launch HN titles
HN_PATTERNS = {
    "Techstars":    ["Techstars", "(Techstars)"],
    "500 Global":   ["(500)", "500 Global", "500 Startups"],
    "Plug and Play": ["Plug and Play", "(PnP)"],
    "a16z Speedrun": ["Speedrun", "a16z Speedrun", "(Speedrun)"],
    "HF0":          ["(HF0)", "HF0"],
    "Pioneer":      ["(Pioneer)", "Pioneer.app"],
}

# How far back to look for new HN posts (seconds)
HN_LOOKBACK = 90 * 24 * 3600  # 90 days


def _hn_search(query: str, since_ts: int = None) -> list[dict]:
    """Search HN for Launch HN posts matching query."""
    params = {
        "query": f"Launch HN {query}",
        "tags": "story",
        "hitsPerPage": "50",
    }
    if since_ts:
        params["numericFilters"] = f"created_at_i>{since_ts}"

    url = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Precognition/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return data.get("hits", [])
    except Exception as e:
        logger.warning("HN search error for '%s': %s", query, e)
        return []


def _parse_hn_hit(hit: dict, incubator: str) -> dict | None:
    """Extract company info from a HN Launch post."""
    title = hit.get("title", "")
    url = hit.get("url") or ""

    # "Launch HN: CompanyName (Accelerator) – One liner"
    import re
    m = re.match(r"Launch HN:\s*([^(–—]+?)\s*(?:\([^)]+\))?\s*[–—]\s*(.+)", title)
    if not m:
        return None

    name = m.group(1).strip()
    one_liner = m.group(2).strip()

    domain = ""
    if url:
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]

    handle = re.sub(r"[^a-z0-9]", "", name.lower())[:40] or "co"
    inc_slug = re.sub(r"[^a-z0-9]", "", incubator.lower())[:10]
    return {
        "name": name,
        "handle": f"{handle}_{inc_slug}" if inc_slug else handle,
        "bio": one_liner,
        "domain": domain,
        "company": name,
        "incubator": incubator,
        "sources": [],
        "tags": [],
        "location": "",
        "stage": "Seed",
        "founded": "",
        "notes": f"Launched on HN: {title[:200]}",
    }


def _load_seeds() -> list[dict]:
    """Load curated seed companies from JSON file."""
    if not SEEDS_FILE.exists():
        return []
    try:
        with open(SEEDS_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load seeds: %s", e)
        return []


def _upsert_founder(conn, f: dict) -> int:
    """Insert/update a company. Returns 1 if new."""
    existing = conn.execute(
        "SELECT id FROM founders WHERE name = ? AND incubator = ?",
        (f["name"], f["incubator"]),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE founders SET
               bio = COALESCE(NULLIF(bio,''), ?),
               domain = COALESCE(NULLIF(domain,''), ?),
               notes = COALESCE(NULLIF(notes,''), ?),
               updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (f["bio"], f["domain"], f["notes"], existing["id"]),
        )
        founder_id = existing["id"]
        inserted = 0
    else:
        # Generate a unique handle by slugifying the company name
        base_handle = re.sub(r"[^a-z0-9]", "", f["name"].lower())[:40] or "co"
        # Ensure uniqueness by appending incubator slug if needed
        inc_slug = re.sub(r"[^a-z0-9]", "", f["incubator"].lower())[:10]
        handle = f"{base_handle}_{inc_slug}" if inc_slug else base_handle

        conn.execute(
            """INSERT INTO founders
               (name, handle, avatar, bio, domain, company, location, stage,
                incubator, founded, notes, status, entity_type, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'to_contact','startup', CURRENT_TIMESTAMP)""",
            (
                f["name"],
                handle,
                f["name"][:2].upper(),
                f.get("bio", ""),
                f.get("domain", ""),
                f["name"],
                f.get("location", ""),
                f.get("stage", "Seed"),
                f["incubator"],
                f.get("founded", ""),
                f.get("notes", ""),
            ),
        )
        founder_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        inserted = 1

    VALID_SOURCES = {"github", "hn", "producthunt"}
    for src in f.get("sources", []):
        if src not in VALID_SOURCES:
            continue
        exists = conn.execute(
            "SELECT 1 FROM founder_sources WHERE founder_id = ? AND source = ?",
            (founder_id, src),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO founder_sources (founder_id, source) VALUES (?,?)",
                (founder_id, src),
            )

    for tag in f.get("tags", []):
        exists = conn.execute(
            "SELECT 1 FROM founder_tags WHERE founder_id = ? AND tag = ?",
            (founder_id, tag),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO founder_tags (founder_id, tag) VALUES (?,?)",
                (founder_id, tag),
            )

    return inserted


def scrape_accelerators(conn) -> int:
    """
    Scrape non-YC accelerators via seeds + HN watcher.
    Returns number of new companies added.
    """
    added = 0
    import time as _time
    since = int(_time.time()) - HN_LOOKBACK

    # Layer 1: Seed file
    seeds = _load_seeds()
    logger.info("Accelerators: loading %d seeded companies", len(seeds))
    for company in seeds:
        added += _upsert_founder(conn, company)

    # Layer 2: HN watcher
    for incubator, patterns in HN_PATTERNS.items():
        for pattern in patterns[:1]:  # one pattern per accelerator to avoid duplication
            hits = _hn_search(pattern, since_ts=since)
            logger.info("HN '%s' (%s): %d hits", pattern, incubator, len(hits))
            for hit in hits:
                company = _parse_hn_hit(hit, incubator)
                if company:
                    added += _upsert_founder(conn, company)
            time.sleep(0.3)

    logger.info("Accelerators: %d new companies added", added)
    return added
