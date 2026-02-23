"""
Clustering engine — detects emerging theme clusters from founder embeddings.

Algorithm: HDBSCAN (density-based, no predefined k).
A theme is declared when >= 3 founders cluster with high cosine similarity.

Each run:
  1. Load all embeddings
  2. Run HDBSCAN
  3. For each cluster: upsert theme, link founders via founder_themes
  4. Compute emergence score per theme
  5. Snapshot to theme_history
  6. Generate human-readable theme name from dominant domain/tag words
"""

import logging
from collections import Counter

import numpy as np

logger = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 3       # Minimum founders to form a theme
MIN_SAMPLES = 2            # HDBSCAN min_samples


# ── Emergence scoring ────────────────────────────────────────


def _compute_emergence_score(conn, theme_id: int, founder_ids: list[int]) -> int:
    """
    Compute 0-100 emergence score for a theme.

    Factors:
    - Builder count (30%) — more unrelated founders = stronger signal
    - Signal velocity (40%) — signals per founder per day over last 7 days
    - WoW growth (30%) — builder count delta vs prior snapshot
    """
    # Builder count score (log-scaled, 10 founders = ~80)
    import math
    count = len(founder_ids)
    count_score = min(math.log1p(count) / math.log1p(10) * 80, 80)

    # Signal velocity: signals in last 7 days across cluster founders
    if founder_ids:
        ph = ",".join("?" for _ in founder_ids)
        sig_rows = conn.execute(
            f"SELECT COUNT(*) as c FROM signals WHERE founder_id IN ({ph}) "
            f"AND detected_at > datetime('now', '-7 days')",
            founder_ids,
        ).fetchone()
        recent_signals = sig_rows["c"] if sig_rows else 0
        velocity = recent_signals / max(count, 1)
        velocity_score = min(velocity * 10, 40)  # cap at 40
    else:
        velocity_score = 0

    # WoW builder count growth
    prior = conn.execute(
        "SELECT builder_count FROM theme_history WHERE theme_id = ? ORDER BY captured_at DESC LIMIT 1",
        (theme_id,),
    ).fetchone()
    if prior and prior["builder_count"] and prior["builder_count"] > 0:
        growth = (count - prior["builder_count"]) / prior["builder_count"]
        growth_score = min(max(growth * 100, 0), 30)
    else:
        growth_score = 15  # new theme gets a baseline

    return round(count_score + velocity_score + growth_score)


# ── Theme naming ─────────────────────────────────────────────


def _generate_theme_name(conn, founder_ids: list[int]) -> str:
    """
    Generate a theme name from the most common domain/tag words across founders.
    Falls back to 'Emerging Theme #{cluster_id}' if no good signal.
    """
    words: list[str] = []

    for fid in founder_ids:
        row = conn.execute("SELECT domain FROM founders WHERE id = ?", (fid,)).fetchone()
        if row and row["domain"]:
            words.extend(row["domain"].lower().replace("-", " ").split())

        tags = conn.execute(
            "SELECT tag FROM founder_tags WHERE founder_id = ?", (fid,)
        ).fetchall()
        for t in tags:
            words.extend(t["tag"].lower().replace("-", " ").split())

    # Filter stop words
    stop = {"the", "and", "for", "with", "that", "this", "from", "are", "has", "have", "its", "in", "of", "a", "an", "to"}
    words = [w for w in words if w not in stop and len(w) > 2]

    if not words:
        return "Emerging Theme"

    counter = Counter(words)
    top = counter.most_common(3)
    return " + ".join(w.title() for w, _ in top)


# ── Founder origin classification ────────────────────────────


def _classify_founder_origin(conn, founder_ids: list[int]) -> str:
    """Summarize where the founders in a cluster are coming from."""
    faang = 0
    researchers = 0
    operators = 0
    serial = 0

    faang_kw = ["google", "meta", "amazon", "apple", "microsoft", "stripe", "airbnb", "openai", "deepmind", "netflix"]
    research_kw = ["phd", "researcher", "research", "university", "professor", "lab"]
    serial_kw = ["serial founder", "exits", "previously founded", "co-founded"]
    operator_kw = ["cto", "vp", "director", "led", "head of", "principal", "staff engineer"]

    for fid in founder_ids:
        row = conn.execute("SELECT bio FROM founders WHERE id = ?", (fid,)).fetchone()
        bio = (row["bio"] or "").lower() if row else ""
        if any(k in bio for k in faang_kw):
            faang += 1
        if any(k in bio for k in research_kw):
            researchers += 1
        if any(k in bio for k in serial_kw):
            serial += 1
        if any(k in bio for k in operator_kw):
            operators += 1

    parts = []
    total = len(founder_ids)
    if faang:
        parts.append(f"{faang}/{total} ex-FAANG")
    if researchers:
        parts.append(f"{researchers}/{total} researchers")
    if serial:
        parts.append(f"{serial}/{total} serial founders")
    if operators:
        parts.append(f"{operators}/{total} operators")
    return ", ".join(parts) if parts else "Mixed backgrounds"


# ── Main clustering function ─────────────────────────────────


def cluster_founders(conn) -> int:
    """
    Run HDBSCAN on all founder embeddings, detect themes, persist results.
    Returns number of themes upserted.
    """
    from backend.embedder import load_embeddings

    founder_ids, matrix = load_embeddings(conn)

    if len(founder_ids) < MIN_CLUSTER_SIZE:
        logger.info("Not enough founders to cluster (%d < %d)", len(founder_ids), MIN_CLUSTER_SIZE)
        return 0

    logger.info("Clustering %d founders", len(founder_ids))

    # Normalize for cosine similarity
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    normed = matrix / norms

    try:
        from sklearn.cluster import HDBSCAN
        clusterer = HDBSCAN(
            min_cluster_size=MIN_CLUSTER_SIZE,
            min_samples=MIN_SAMPLES,
            metric="euclidean",   # euclidean on L2-normed = cosine
            cluster_selection_method="eom",
        )
        labels = clusterer.fit_predict(normed)
    except Exception as e:
        logger.error("HDBSCAN clustering failed: %s", e)
        return 0

    # Group founders by cluster label (-1 = noise, skip)
    clusters: dict[int, list[int]] = {}
    for fid, label in zip(founder_ids, labels):
        if label == -1:
            continue
        clusters.setdefault(label, []).append(fid)

    logger.info("Detected %d clusters (noise: %d)", len(clusters), sum(1 for l in labels if l == -1))

    themes_upserted = 0

    for label, members in clusters.items():
        if len(members) < MIN_CLUSTER_SIZE:
            continue

        name = _generate_theme_name(conn, members)
        origin = _classify_founder_origin(conn, members)

        # Check if a theme with these members already exists
        # Simple heuristic: match by majority member overlap
        existing_theme_id = _find_matching_theme(conn, members)

        if existing_theme_id:
            theme_id = existing_theme_id
            # Update
            conn.execute(
                """UPDATE themes SET name=?, builder_count=?, founder_origin=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (name, len(members), origin, theme_id),
            )
        else:
            # Insert new theme
            cur = conn.execute(
                """INSERT INTO themes (name, builder_count, founder_origin)
                   VALUES (?, ?, ?)""",
                (name, len(members), origin),
            )
            theme_id = cur.lastrowid

        # Compute and update emergence score
        score = _compute_emergence_score(conn, theme_id, members)
        weekly_velocity = _compute_weekly_velocity(conn, theme_id, len(members))

        conn.execute(
            "UPDATE themes SET emergence_score=?, weekly_velocity=? WHERE id=?",
            (score, weekly_velocity, theme_id),
        )

        # Link founders to theme (replace stale links)
        conn.execute("DELETE FROM founder_themes WHERE theme_id = ?", (theme_id,))
        for fid in members:
            conn.execute(
                """INSERT INTO founder_themes (founder_id, theme_id, similarity)
                   VALUES (?, ?, ?)
                   ON CONFLICT(founder_id, theme_id) DO UPDATE SET similarity=excluded.similarity""",
                (fid, theme_id, 1.0),  # TODO: real per-pair similarity
            )

        themes_upserted += 1
        logger.info("Theme '%s' (id=%d): %d founders, score=%d", name, theme_id, len(members), score)

    # Snapshot to history
    update_theme_history(conn)

    return themes_upserted


def _find_matching_theme(conn, member_ids: list[int]) -> int | None:
    """Find an existing theme that shares > 50% members with the given list."""
    if not member_ids:
        return None
    ph = ",".join("?" for _ in member_ids)
    rows = conn.execute(
        f"""SELECT theme_id, COUNT(*) as overlap
            FROM founder_themes
            WHERE founder_id IN ({ph})
            GROUP BY theme_id
            ORDER BY overlap DESC
            LIMIT 1""",
        member_ids,
    ).fetchone()
    if rows and rows["overlap"] >= len(member_ids) * 0.5:
        return rows["theme_id"]
    return None


def _compute_weekly_velocity(conn, theme_id: int, current_count: int) -> float:
    """Compute week-over-week builder count change as a percentage."""
    prior = conn.execute(
        """SELECT builder_count FROM theme_history
           WHERE theme_id = ? AND captured_at < datetime('now', '-7 days')
           ORDER BY captured_at DESC LIMIT 1""",
        (theme_id,),
    ).fetchone()
    if prior and prior["builder_count"]:
        return (current_count - prior["builder_count"]) / prior["builder_count"]
    return 0.0


def update_theme_history(conn) -> None:
    """Snapshot current theme state into theme_history."""
    themes = conn.execute("SELECT id, emergence_score, builder_count FROM themes").fetchall()
    for t in themes:
        conn.execute(
            "INSERT INTO theme_history (theme_id, emergence_score, builder_count) VALUES (?, ?, ?)",
            (t["id"], t["emergence_score"], t["builder_count"]),
        )
    logger.info("Snapshotted %d theme histories", len(list(themes)))
