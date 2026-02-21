"""
Pipeline orchestrator — scrape → score → alert.

Can run as:
  1. One-shot: `python -m backend.pipeline`
  2. Scheduled: `python -m backend.pipeline --schedule`
  3. API trigger: POST /api/pipeline/run
"""

import argparse
import logging
import time

from backend.alerts import check_alerts
from backend.config import PIPELINE_INTERVAL_MINUTES
from backend.db import get_db, init_db
from backend.scoring import score_founder
from backend.scrapers import scrape_github, scrape_hn, scrape_producthunt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline():
    """Execute a full pipeline run: scrape all sources, score, alert."""
    logger.info("Pipeline run starting")
    init_db()

    founders_scraped = 0
    founders_scored = 0
    alerts_sent = 0

    # Phase 1: Scrape
    with get_db() as conn:
        logger.info("Phase 1: Scraping sources")
        try:
            founders_scraped += scrape_hn(conn)
        except Exception as e:
            logger.error("HN scraper failed: %s", e)

        try:
            founders_scraped += scrape_github(conn)
        except Exception as e:
            logger.error("GitHub scraper failed: %s", e)

        try:
            founders_scraped += scrape_producthunt(conn)
        except Exception as e:
            logger.error("Product Hunt scraper failed: %s", e)

    # Phase 2: Score all founders
    with get_db() as conn:
        logger.info("Phase 2: Scoring founders")
        founders = conn.execute("SELECT * FROM founders").fetchall()

        for f in founders:
            fid = f["id"]
            founder_info = dict(f)

            # Get signals for scoring
            signals = conn.execute(
                "SELECT source, label, strong FROM signals WHERE founder_id = ?",
                (fid,),
            ).fetchall()
            signals_list = [dict(s) for s in signals]

            try:
                scores = score_founder(conn, fid, founder_info, signals_list)
                founders_scored += 1
            except Exception as e:
                logger.error("Scoring failed for founder %d: %s", fid, e)
                continue

            # Phase 3: Check alerts for this founder
            try:
                def log_alert(founder_id, alert_type, channel, message):
                    conn.execute(
                        "INSERT INTO alert_log (founder_id, alert_type, channel, message) VALUES (?, ?, ?, ?)",
                        (founder_id, alert_type, channel, message),
                    )

                sent = check_alerts(
                    conn, fid, f["name"], f["handle"], scores, log_alert
                )
                alerts_sent += sent
            except Exception as e:
                logger.error("Alert check failed for founder %d: %s", fid, e)

    logger.info(
        "Pipeline complete: scraped=%d, scored=%d, alerts=%d",
        founders_scraped, founders_scored, alerts_sent,
    )
    return {
        "founders_scraped": founders_scraped,
        "founders_scored": founders_scored,
        "alerts_sent": alerts_sent,
    }


def run_scheduled():
    """Run the pipeline on a recurring schedule."""
    logger.info("Starting scheduled pipeline (every %d minutes)", PIPELINE_INTERVAL_MINUTES)
    while True:
        try:
            run_pipeline()
        except Exception as e:
            logger.error("Pipeline run failed: %s", e)
        logger.info("Next run in %d minutes", PIPELINE_INTERVAL_MINUTES)
        time.sleep(PIPELINE_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SCOUT Pipeline")
    parser.add_argument("--schedule", action="store_true", help="Run on a recurring schedule")
    args = parser.parse_args()

    if args.schedule:
        run_scheduled()
    else:
        run_pipeline()
