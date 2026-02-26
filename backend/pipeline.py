"""
Pipeline orchestrator — scrape → enrich → score → alert.

Can run as:
  1. One-shot: `python -m backend.pipeline`
  2. Scheduled: `python -m backend.pipeline --schedule`
  3. API trigger: POST /api/pipeline/run

Phases:
  1. Scrape — discover founders from HN, GitHub, Product Hunt (90-day windows)
  2. Enrich — cross-platform lookup: for each founder, check platforms they
     weren't discovered on (e.g. found on HN → also check GitHub & PH)
  3. Score — compute 5-dimension scores for every founder
  4. Alert — check score thresholds, send notifications
"""

import argparse
import logging
import time

from backend.alerts import check_alerts
from backend.anomaly import detect_anomalies
from backend.clustering import cluster_founders
from backend.config import PIPELINE_INTERVAL_MINUTES
from backend.db import get_db, init_db
from backend.embedder import embed_all_founders
from backend.enrichment import enrich_qualified_founders
from backend.scoring import score_founder
from backend.scrapers import scrape_github, scrape_hn, scrape_producthunt, scrape_indiehackers, enrich_founders, scrape_yc, scrape_accelerators

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

        try:
            founders_scraped += scrape_indiehackers(conn)
        except Exception as e:
            logger.error("Indie Hackers scraper failed: %s", e)

        # YC batch scraper — runs every time but upserts are idempotent (fast after first run)
        try:
            yc_added = scrape_yc(conn)
            founders_scraped += yc_added
            logger.info("YC scraper: %d new companies added", yc_added)
        except Exception as e:
            logger.error("YC scraper failed: %s", e)

        # Other accelerators — curated seeds + HN watcher
        try:
            acc_added = scrape_accelerators(conn)
            founders_scraped += acc_added
            logger.info("Accelerators scraper: %d new companies added", acc_added)
        except Exception as e:
            logger.error("Accelerators scraper failed: %s", e)

    # Phase 1.5: Embed founder content
    with get_db() as conn:
        logger.info("Phase 1.5: Embedding founders")
        try:
            embedded = embed_all_founders(conn)
            logger.info("Embedded %d founders", embedded)
        except Exception as e:
            logger.error("Embedding phase failed: %s", e)

    # Phase 1.6: Cluster founders into themes
    with get_db() as conn:
        logger.info("Phase 1.6: Clustering founders into themes")
        try:
            themes = cluster_founders(conn)
            logger.info("Upserted %d themes", themes)
        except Exception as e:
            logger.error("Clustering phase failed: %s", e)

    # Phase 2: Cross-platform enrichment
    with get_db() as conn:
        logger.info("Phase 2: Cross-platform enrichment")
        try:
            enriched = enrich_founders(conn)
            logger.info("Enrichment added %d new source links", enriched)
        except Exception as e:
            logger.error("Enrichment failed: %s", e)

    # Phase 3: Score all founders
    with get_db() as conn:
        logger.info("Phase 3: Scoring founders")
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

            # Phase 4: Check alerts for this founder
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

    # Phase 3.5: External enrichment (Apify + Proxycurl) — gate applies score threshold
    with get_db() as conn:
        logger.info("Phase 3.5: External enrichment (Twitter + LinkedIn)")
        try:
            enriched = enrich_qualified_founders(conn)
            logger.info("Enriched %d founders", enriched)
        except Exception as e:
            logger.error("Enrichment phase failed: %s", e)

    # Phase 3.7: Anomaly detection
    with get_db() as conn:
        logger.info("Phase 3.5: Detecting anomalies")
        try:
            anomalies = detect_anomalies(conn)
            logger.info("Detected %d emergence events", anomalies)
        except Exception as e:
            logger.error("Anomaly detection failed: %s", e)

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
