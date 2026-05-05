#!/usr/bin/env python3
"""
Backfill Product Hunt taglines into bio/notes for existing PH founders.

Run directly: python backfill_ph_descriptions.py
Output logged to /tmp/ph_backfill_desc.log
"""

import re
import sys
import time
import logging
from datetime import date, timedelta

# Ensure project root is on path
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.scrapers.producthunt_jina import scrape_producthunt_daily
from backend.db import get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/ph_backfill_desc.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)

START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 5, 4)

def slug_for_name(name: str) -> str:
    """Convert product name to handle slug: lowercase, non-alphanum → '-'."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug[:40]

def main():
    logger.info("Starting PH description backfill from %s to %s", START_DATE, END_DATE)

    total_checked = 0
    total_updated = 0
    total_skipped = 0

    current = START_DATE
    while current <= END_DATE:
        date_str = current.strftime("%Y-%m-%d")
        logger.info("Scraping %s ...", date_str)

        try:
            products = scrape_producthunt_daily(date_str)
        except Exception as e:
            logger.error("Failed to scrape %s: %s", date_str, e)
            current += timedelta(days=1)
            time.sleep(0.8)
            continue

        if not products:
            logger.info("  No products (filtered or empty)")
            current += timedelta(days=1)
            time.sleep(0.8)
            continue

        with get_db() as conn:
            for product in products:
                tagline = product.get("tagline", "").strip()
                if not tagline:
                    total_skipped += 1
                    continue

                slug = slug_for_name(product["name"])
                handle = f"@ph-daily-{slug}"
                total_checked += 1

                result = conn.execute(
                    "SELECT id, bio FROM founders WHERE handle=?",
                    (handle,)
                ).fetchone()

                if result is None:
                    logger.debug("  %s — no founder found, skipping", handle)
                    total_skipped += 1
                    continue

                bio = result["bio"] if isinstance(result, dict) else result[1]
                if bio and bio.strip():
                    logger.debug("  %s — already has bio, skipping", handle)
                    continue

                conn.execute(
                    "UPDATE founders SET bio=?, notes=? WHERE handle=? AND (bio IS NULL OR bio='')",
                    (tagline, tagline, handle),
                )
                conn.commit()
                total_updated += 1
                logger.info("  Updated %s: %s", handle, tagline[:80])

        current += timedelta(days=1)
        time.sleep(0.8)

    logger.info(
        "Backfill complete: checked=%d, updated=%d, skipped=%d",
        total_checked, total_updated, total_skipped
    )
    print(f"\nSUMMARY: {total_updated} PH founders updated with descriptions.")

if __name__ == "__main__":
    main()
