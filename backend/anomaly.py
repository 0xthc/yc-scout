"""
Anomaly detection — watches for momentum inflections across founders and themes.

An emergence event fires when:
  - Commit velocity >= 2x week-over-week
  - GitHub stars grow > 15 in 24h on a repo with < 100 stars total
  - HN top score spikes (new post enters top)
  - A new theme cluster is detected (>= 3 founders converging)

Events are written to the emergence_events table and surfaced via /api/emergence.
"""

import logging

logger = logging.getLogger(__name__)

# Thresholds
COMMIT_VELOCITY_MULTIPLIER = 2.0   # 2x WoW = anomaly
STAR_SPIKE_MIN = 15                # stars gained in 24h
STAR_SPIKE_MAX_BASE = 100          # only flag if total stars < this (pre-discovery)
HN_SCORE_SPIKE = 100               # new HN post with score > this = spike


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
    """Flag repos that gained 15+ stars in 24h while still under 100 total."""
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


# ── Theme anomaly checks ─────────────────────────────────────


def _check_new_themes(conn) -> None:
    """Flag themes that were created in the last 24h."""
    new_themes = conn.execute(
        """SELECT id, name, builder_count FROM themes
           WHERE first_detected > datetime('now', '-24 hours')""",
    ).fetchall()

    for t in new_themes:
        theme_id = t["id"]
        if not _already_fired(conn, theme_id, "theme", "new_theme", window_hours=72):
            _fire_event(
                conn, "new_theme", theme_id, "theme",
                f"New theme detected: '{t['name']}' ({t['builder_count']} founders converging)",
                None, float(t["builder_count"]),
            )


def _check_theme_velocity(conn) -> None:
    """Flag themes whose builder count grew significantly this week."""
    themes = conn.execute("SELECT id, name, builder_count FROM themes").fetchall()

    for t in themes:
        theme_id = t["id"]
        prior = conn.execute(
            """SELECT builder_count FROM theme_history
               WHERE theme_id = ? AND captured_at < datetime('now', '-7 days')
               ORDER BY captured_at DESC LIMIT 1""",
            (theme_id,),
        ).fetchone()

        if not prior or not prior["builder_count"]:
            continue

        current = t["builder_count"] or 0
        growth = (current - prior["builder_count"]) / prior["builder_count"]

        if growth >= 0.5:  # 50% WoW builder growth
            if not _already_fired(conn, theme_id, "theme", "theme_spike"):
                _fire_event(
                    conn, "theme_spike", theme_id, "theme",
                    f"Theme '{t['name']}' grew {growth*100:.0f}% WoW ({prior['builder_count']} → {current} builders)",
                    float(prior["builder_count"]), float(current),
                )


# ── Main entry point ─────────────────────────────────────────


def detect_anomalies(conn) -> int:
    """
    Run all anomaly checks across founders and themes.
    Returns total events fired.
    """
    before = conn.execute("SELECT COUNT(*) as c FROM emergence_events").fetchone()["c"]

    # Per-founder checks
    founders = conn.execute("SELECT id FROM founders").fetchall()
    for f in founders:
        fid = f["id"]
        latest = _get_latest_snapshot(conn, fid)
        if not latest:
            continue
        prior = _get_prior_snapshot(conn, fid)
        if not prior:
            continue

        try:
            _check_commit_velocity(conn, fid, latest, prior)
            _check_star_spike(conn, fid, latest, prior)
            _check_hn_spike(conn, fid, latest, prior)
        except Exception as e:
            logger.error("Anomaly check failed for founder %d: %s", fid, e)

    # Theme-level checks
    try:
        _check_new_themes(conn)
        _check_theme_velocity(conn)
    except Exception as e:
        logger.error("Theme anomaly check failed: %s", e)

    after = conn.execute("SELECT COUNT(*) as c FROM emergence_events").fetchone()["c"]
    fired = after - before
    logger.info("Anomaly detection complete: %d new events", fired)
    return fired
