"""
Anomaly detection — watches for momentum inflections across founders.
"""

import logging

logger = logging.getLogger(__name__)

# Thresholds
COMMIT_VELOCITY_MULTIPLIER = 2.0   # 2x WoW = anomaly
STAR_SPIKE_MIN = 10                # stars gained in 24h
STAR_SPIKE_MAX_BASE = 300          # only flag if total stars below this base
HN_SCORE_SPIKE = 50                # new HN post with score > this = spike


def _get_prior_snapshot(conn, founder_id: int) -> dict | None:
    """Get the second-most-recent stats snapshot for a founder."""
    rows = conn.execute(
        """SELECT * FROM stats_snapshots
           WHERE founder_id = ?
           ORDER BY captured_at DESC
           LIMIT 2""",
        (founder_id,),
    ).fetchall()
    if len(rows) < 2:
        return None
    row = rows[1]
    return dict(zip(row.keys(), [row[k] for k in row.keys()])) if hasattr(row, "keys") else None


def _get_latest_snapshot(conn, founder_id: int) -> dict | None:
    """Get the most recent stats snapshot for a founder."""
    row = conn.execute(
        "SELECT * FROM stats_snapshots WHERE founder_id = ? ORDER BY captured_at DESC LIMIT 1",
        (founder_id,),
    ).fetchone()
    if not row:
        return None
    return {k: row[k] for k in row.keys()} if hasattr(row, "keys") else None


def _already_fired(conn, entity_id: int, entity_type: str, event_type: str, window_hours: int = 24) -> bool:
    """Prevent duplicate events within a time window."""
    row = conn.execute(
        """SELECT id FROM emergence_events
           WHERE entity_id = ? AND entity_type = ? AND event_type = ?
             AND detected_at > datetime('now', ?)""",
        (entity_id, entity_type, event_type, f"-{window_hours} hours"),
    ).fetchone()
    return row is not None


def _fire_event(conn, event_type: str, entity_id: int, entity_type: str,
                signal: str, before: float | None = None, after: float | None = None) -> None:
    conn.execute(
        """INSERT INTO emergence_events (event_type, entity_id, entity_type, signal, delta_before, delta_after)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, entity_id, entity_type, signal, before, after),
    )
    logger.info("Emergence event [%s] %s #%d: %s", event_type, entity_type, entity_id, signal)


# ── Per-founder anomaly checks ───────────────────────────────


def _check_commit_velocity(conn, founder_id: int, latest: dict, prior: dict) -> None:
    """Flag if commit velocity doubled week-over-week."""
    now_commits = latest.get("github_commits_90d", 0) or 0
    prior_commits = prior.get("github_commits_90d", 0) or 0

    if prior_commits < 5:
        return  # Too low a base to be meaningful

    ratio = now_commits / prior_commits if prior_commits > 0 else 0

    if ratio >= COMMIT_VELOCITY_MULTIPLIER:
        if not _already_fired(conn, founder_id, "founder", "commit_spike"):
            _fire_event(
                conn, "commit_spike", founder_id, "founder",
                f"Commit velocity {ratio:.1f}× WoW ({prior_commits} → {now_commits} commits/90d)",
                float(prior_commits), float(now_commits),
            )


def _check_star_spike(conn, founder_id: int, latest: dict, prior: dict) -> None:
    """Flag repos that gained stars quickly while still below a capped base."""
    now_stars = latest.get("github_stars", 0) or 0
    prior_stars = prior.get("github_stars", 0) or 0

    gained = now_stars - prior_stars
    if gained >= STAR_SPIKE_MIN and prior_stars < STAR_SPIKE_MAX_BASE:
        if not _already_fired(conn, founder_id, "founder", "star_spike"):
            _fire_event(
                conn, "star_spike", founder_id, "founder",
                f"Star spike: +{gained} stars in 24h ({prior_stars} → {now_stars} total)",
                float(prior_stars), float(now_stars),
            )


def _check_hn_spike(conn, founder_id: int, latest: dict, prior: dict) -> None:
    """Flag if a founder just landed a high-scoring HN post."""
    now_top = latest.get("hn_top_score", 0) or 0
    prior_top = prior.get("hn_top_score", 0) or 0

    if now_top >= HN_SCORE_SPIKE and now_top > prior_top:
        if not _already_fired(conn, founder_id, "founder", "hn_spike"):
            _fire_event(
                conn, "hn_spike", founder_id, "founder",
                f"HN post hit {now_top} points (prev best: {prior_top})",
                float(prior_top), float(now_top),
            )


def _check_score_threshold(conn, founder_id, latest_score, prior_score):
    # Fire if composite score just crossed 60 for first time
    if prior_score is not None and prior_score < 60 and latest_score >= 60:
        if not _already_fired(conn, founder_id, "founder", "score_threshold", window_hours=168):
            _fire_event(conn, "score_threshold", founder_id, "founder",
                f"Score crossed 60 for first time ({prior_score:.0f} -> {latest_score:.0f})",
                float(prior_score), float(latest_score))


def _check_cross_platform(conn, founder_id):
    # Fire if founder has both github and hn sources and was created in last 7 days
    sources = conn.execute(
        "SELECT DISTINCT source FROM founder_sources WHERE founder_id = ?", (founder_id,)
    ).fetchall()
    source_list = [s["source"] for s in sources]
    if "github" in source_list and "hn" in source_list:
        founder = conn.execute(
            "SELECT created_at FROM founders WHERE id = ?", (founder_id,)
        ).fetchone()
        if founder:
            if not _already_fired(conn, founder_id, "founder", "cross_platform", window_hours=168):
                _fire_event(conn, "cross_platform", founder_id, "founder",
                    "Active on both GitHub and HN — cross-platform signal",
                    None, None)


# ── Main entry point ─────────────────────────────────────────


def detect_anomalies(conn) -> int:
    """
    Run anomaly checks across founders.
    Returns total events fired.
    """
    before = conn.execute("SELECT COUNT(*) as c FROM emergence_events").fetchone()["c"]

    founders = conn.execute("SELECT id FROM founders").fetchall()
    for f in founders:
        fid = f["id"]
        latest = _get_latest_snapshot(conn, fid)
        if not latest:
            continue

        prior = _get_prior_snapshot(conn, fid)

        try:
            if prior:
                _check_commit_velocity(conn, fid, latest, prior)
                _check_star_spike(conn, fid, latest, prior)
                _check_hn_spike(conn, fid, latest, prior)

            score_rows = conn.execute(
                "SELECT composite FROM scores WHERE founder_id = ? ORDER BY scored_at DESC LIMIT 2",
                (fid,),
            ).fetchall()
            latest_score = score_rows[0]["composite"] if len(score_rows) >= 1 else None
            prior_score = score_rows[1]["composite"] if len(score_rows) >= 2 else None
            if latest_score is not None:
                _check_score_threshold(conn, fid, latest_score, prior_score)

            _check_cross_platform(conn, fid)
        except Exception as e:
            logger.error("Anomaly check failed for founder %d: %s", fid, e)

    after = conn.execute("SELECT COUNT(*) as c FROM emergence_events").fetchone()["c"]
    fired = after - before
    logger.info("Anomaly detection complete: %d new events", fired)
    return fired
