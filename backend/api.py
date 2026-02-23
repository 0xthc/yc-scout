"""
FastAPI server — serves scored founder data to the React frontend.
Also exposes endpoints to trigger pipeline runs and update founder status.
"""

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.db import get_db, init_db, _TursoConnection
from backend.models import FounderOut, PaginatedFounders, PipelineResult, StatusUpdate
from backend.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Simple in-memory cache to avoid hammering Turso on health checks + polling
_cache = {}
CACHE_TTL = 30  # seconds


def _cache_get(key):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key, data):
    _cache[key] = {"data": data, "ts": time.time()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SCOUT API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_score(row, new_key, old_key):
    """Get a score value from a row, handling both old and new column names."""
    try:
        return row[new_key]
    except (KeyError, IndexError):
        try:
            return row[old_key]
        except (KeyError, IndexError):
            return 0


def _extract_breakdown(score_row):
    """Extract score breakdown dict, handling both old and new column names."""
    if not score_row:
        return {
            "founder_quality": 0, "execution_velocity": 0,
            "market_conviction": 0, "early_traction": 0,
            "deal_availability": 0,
        }
    return {
        "founder_quality": round(_get_score(score_row, "founder_quality", "momentum")),
        "execution_velocity": round(_get_score(score_row, "execution_velocity", "domain_score")),
        "market_conviction": round(_get_score(score_row, "market_conviction", "team")),
        "early_traction": round(_get_score(score_row, "early_traction", "traction")),
        "deal_availability": round(_get_score(score_row, "deal_availability", "ycfit")),
    }


def _build_founder(conn, row) -> dict:
    """Assemble a full founder response from DB row + related data."""
    fid = row["id"]

    # Sources
    sources = [
        r["source"]
        for r in conn.execute(
            "SELECT source FROM founder_sources WHERE founder_id = ?", (fid,)
        ).fetchall()
    ]

    # Tags
    tags = [
        r["tag"]
        for r in conn.execute(
            "SELECT tag FROM founder_tags WHERE founder_id = ?", (fid,)
        ).fetchall()
    ]

    # Latest scores
    score_row = conn.execute(
        "SELECT * FROM scores WHERE founder_id = ? ORDER BY scored_at DESC LIMIT 1",
        (fid,),
    ).fetchone()

    # Latest stats
    stats_row = conn.execute(
        "SELECT * FROM stats_snapshots WHERE founder_id = ? ORDER BY captured_at DESC LIMIT 1",
        (fid,),
    ).fetchone()

    # Recent signals (last 20)
    signal_rows = conn.execute(
        "SELECT source, label, url, strong, detected_at FROM signals WHERE founder_id = ? ORDER BY detected_at DESC LIMIT 20",
        (fid,),
    ).fetchall()

    signals = []
    for s in signal_rows:
        signals.append({
            "type": s["source"],
            "label": s["label"],
            "url": s["url"],
            "strong": bool(s["strong"]),
            "date": s["detected_at"],
        })

    return {
        "id": fid,
        "name": row["name"],
        "handle": row["handle"],
        "avatar": row["avatar"] or "".join(w[0].upper() for w in row["name"].split()[:2]),
        "location": row["location"] or "",
        "bio": row["bio"] or "",
        "domain": row["domain"] or "",
        "stage": row["stage"] or "Unknown",
        "company": row["company"] or "",
        "founded": row["founded"] or "",
        "status": row["status"] or "to_contact",
        "yc_alumni_connections": row["yc_alumni_connections"] or 0,
        "incubator": row["incubator"] or "",
        "sources": sources,
        "tags": tags,
        "score": round(score_row["composite"]) if score_row else 0,
        "scoreBreakdown": _extract_breakdown(score_row),
        "signals": signals,
        "notes": row["notes"] if "notes" in row.keys() else "",
        "github_stars": stats_row["github_stars"] if stats_row else 0,
        "github_commits_90d": stats_row["github_commits_90d"] if stats_row else 0,
        "github_repos": stats_row["github_repos"] if stats_row else 0,
        "hn_karma": stats_row["hn_karma"] if stats_row else 0,
        "hn_submissions": stats_row["hn_submissions"] if stats_row else 0,
        "hn_top_score": stats_row["hn_top_score"] if stats_row else 0,
        "ph_upvotes": stats_row["ph_upvotes"] if stats_row else 0,
        "ph_launches": stats_row["ph_launches"] if stats_row else 0,
        "followers": stats_row["followers"] if stats_row else 0,
    }


def _execute_batch(conn, queries):
    """Execute multiple queries — batched for Turso, sequential for SQLite."""
    if isinstance(conn, _TursoConnection):
        return conn.execute_batch(queries)
    return [conn.execute(sql, params or []) for sql, params in queries]


def _build_founders_batch(conn, rows):
    """Build founder dicts using batch queries (2 HTTP calls instead of 4N+1)."""
    if not rows:
        return []

    fids = [r["id"] for r in rows]
    ph = ",".join("?" for _ in fids)

    cursors = _execute_batch(conn, [
        (f"SELECT founder_id, source FROM founder_sources WHERE founder_id IN ({ph})", fids),
        (f"SELECT founder_id, tag FROM founder_tags WHERE founder_id IN ({ph})", fids),
        (f"""SELECT s.* FROM scores s
             INNER JOIN (
                 SELECT founder_id, MAX(scored_at) as max_at
                 FROM scores WHERE founder_id IN ({ph})
                 GROUP BY founder_id
             ) latest ON s.founder_id = latest.founder_id AND s.scored_at = latest.max_at""", fids),
        (f"""SELECT ss.* FROM stats_snapshots ss
             INNER JOIN (
                 SELECT founder_id, MAX(captured_at) as max_at
                 FROM stats_snapshots WHERE founder_id IN ({ph})
                 GROUP BY founder_id
             ) latest ON ss.founder_id = latest.founder_id AND ss.captured_at = latest.max_at""", fids),
        (f"""SELECT founder_id, source, label, url, strong, detected_at
             FROM signals WHERE founder_id IN ({ph})
             ORDER BY detected_at DESC""", fids),
    ])

    sources_map = defaultdict(list)
    for r in cursors[0].fetchall():
        sources_map[r["founder_id"]].append(r["source"])

    tags_map = defaultdict(list)
    for r in cursors[1].fetchall():
        tags_map[r["founder_id"]].append(r["tag"])

    scores_map = {}
    for r in cursors[2].fetchall():
        scores_map[r["founder_id"]] = r

    stats_map = {}
    for r in cursors[3].fetchall():
        stats_map[r["founder_id"]] = r

    signals_map = defaultdict(list)
    for r in cursors[4].fetchall():
        fid = r["founder_id"]
        if len(signals_map[fid]) < 20:
            signals_map[fid].append({
                "type": r["source"],
                "label": r["label"],
                "url": r["url"],
                "strong": bool(r["strong"]),
                "date": r["detected_at"],
            })

    founders = []
    for row in rows:
        fid = row["id"]
        score_row = scores_map.get(fid)
        stats_row = stats_map.get(fid)
        founders.append({
            "id": fid,
            "name": row["name"],
            "handle": row["handle"],
            "avatar": row["avatar"] or "".join(w[0].upper() for w in row["name"].split()[:2]),
            "location": row["location"] or "",
            "bio": row["bio"] or "",
            "domain": row["domain"] or "",
            "stage": row["stage"] or "Unknown",
            "company": row["company"] or "",
            "founded": row["founded"] or "",
            "status": row["status"] or "to_contact",
            "yc_alumni_connections": row["yc_alumni_connections"] or 0,
            "incubator": row["incubator"] or "",
            "sources": sources_map.get(fid, []),
            "tags": tags_map.get(fid, []),
            "score": round(score_row["composite"]) if score_row else 0,
            "scoreBreakdown": _extract_breakdown(score_row),
            "signals": signals_map.get(fid, []),
            "github_stars": stats_row["github_stars"] if stats_row else 0,
            "github_commits_90d": stats_row["github_commits_90d"] if stats_row else 0,
            "github_repos": stats_row["github_repos"] if stats_row else 0,
            "hn_karma": stats_row["hn_karma"] if stats_row else 0,
            "hn_submissions": stats_row["hn_submissions"] if stats_row else 0,
            "hn_top_score": stats_row["hn_top_score"] if stats_row else 0,
            "ph_upvotes": stats_row["ph_upvotes"] if stats_row else 0,
            "ph_launches": stats_row["ph_launches"] if stats_row else 0,
            "followers": stats_row["followers"] if stats_row else 0,
        })
    return founders


@app.get("/api/founders", response_model=PaginatedFounders)
def list_founders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str = Query("", description="Search name, company, domain"),
    source: str = Query("", description="Filter by source: github, hn, producthunt"),
    status: str = Query("", description="Filter by status: to_contact, watching, contacted, pass"),
    sort: str = Query("score", description="Sort by: score, stars"),
):
    """List founders with server-side filtering, search, sort, and pagination."""
    cache_key = f"founders:{limit}:{offset}:{search}:{source}:{status}:{sort}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    with get_db() as conn:
        where_clauses = []
        params = []

        if search:
            where_clauses.append(
                "(LOWER(f.name) LIKE ? OR LOWER(f.company) LIKE ? OR LOWER(f.domain) LIKE ?)"
            )
            term = f"%{search.lower()}%"
            params.extend([term, term, term])

        if source:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM founder_sources fs WHERE fs.founder_id = f.id AND fs.source = ?)"
            )
            params.append(source)

        if status:
            where_clauses.append("f.status = ?")
            params.append(status)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        if sort == "stars":
            order_sql = """ORDER BY (
                SELECT ss.github_stars FROM stats_snapshots ss
                WHERE ss.founder_id = f.id ORDER BY ss.captured_at DESC LIMIT 1
            ) DESC NULLS LAST"""
        else:
            order_sql = """ORDER BY (
                SELECT composite FROM scores
                WHERE founder_id = f.id ORDER BY scored_at DESC LIMIT 1
            ) DESC NULLS LAST"""

        total = conn.execute(
            f"SELECT COUNT(*) as c FROM founders f{where_sql}", params
        ).fetchone()["c"]

        rows = conn.execute(
            f"SELECT f.* FROM founders f{where_sql} {order_sql} LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        result = {
            "founders": _build_founders_batch(conn, rows),
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    _cache_set(cache_key, result)
    return result


@app.get("/api/founders/{founder_id}", response_model=FounderOut)
def get_founder(founder_id: int):
    """Get a single founder by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM founders WHERE id = ?", (founder_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Founder not found")
        return _build_founder(conn, row)


@app.patch("/api/founders/{founder_id}/status")
def update_status(founder_id: int, body: StatusUpdate):
    """Update a founder's pipeline status."""
    valid = {"to_contact", "watching", "contacted", "pass"}
    if body.status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    with get_db() as conn:
        row = conn.execute("SELECT id FROM founders WHERE id = ?", (founder_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Founder not found")
        conn.execute(
            "UPDATE founders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (body.status, founder_id),
        )
    _cache.clear()
    return {"ok": True, "status": body.status}


@app.post("/api/pipeline/run", response_model=PipelineResult)
def trigger_pipeline():
    """Manually trigger a full pipeline run: scrape → score → alert."""
    result = run_pipeline()
    _cache.clear()
    return result


@app.get("/api/themes")
def list_themes():
    """List all detected theme clusters sorted by emergence score."""
    cached = _cache_get("themes")
    if cached:
        return cached

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM themes ORDER BY emergence_score DESC"
        ).fetchall()

        themes = []
        for t in rows:
            theme_id = t["id"]
            founders = conn.execute(
                """SELECT f.id, f.name, f.handle, f.company, f.domain, f.bio,
                          (SELECT composite FROM scores WHERE founder_id = f.id ORDER BY scored_at DESC LIMIT 1) as score
                   FROM founders f
                   JOIN founder_themes ft ON ft.founder_id = f.id
                   WHERE ft.theme_id = ?
                   ORDER BY score DESC""",
                (theme_id,),
            ).fetchall()

            themes.append({
                "id": theme_id,
                "name": t["name"],
                "emergenceScore": t["emergence_score"],
                "builderCount": t["builder_count"],
                "weeklyVelocity": t["weekly_velocity"],
                "painSummary": t["pain_summary"],
                "unlockSummary": t["unlock_summary"],
                "founderOrigin": t["founder_origin"],
                "firstDetected": t["first_detected"],
                "updatedAt": t["updated_at"],
                "founders": [
                    {
                        "id": f["id"],
                        "name": f["name"],
                        "handle": f["handle"],
                        "company": f["company"] or "",
                        "domain": f["domain"] or "",
                        "bio": f["bio"] or "",
                        "score": round(f["score"]) if f["score"] else 0,
                    }
                    for f in founders
                ],
            })

    _cache_set("themes", themes)
    return themes


@app.get("/api/themes/{theme_id}")
def get_theme(theme_id: int):
    """Get a single theme with full founder details."""
    with get_db() as conn:
        t = conn.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
        if not t:
            raise HTTPException(404, "Theme not found")

        founders = conn.execute(
            """SELECT f.* FROM founders f
               JOIN founder_themes ft ON ft.founder_id = f.id
               WHERE ft.theme_id = ?""",
            (theme_id,),
        ).fetchall()

        return {
            "id": t["id"],
            "name": t["name"],
            "emergenceScore": t["emergence_score"],
            "builderCount": t["builder_count"],
            "weeklyVelocity": t["weekly_velocity"],
            "painSummary": t["pain_summary"],
            "unlockSummary": t["unlock_summary"],
            "founderOrigin": t["founder_origin"],
            "firstDetected": t["first_detected"],
            "founders": _build_founders_batch(conn, founders),
        }


@app.get("/api/emergence")
def get_emergence(hours: int = Query(168, description="Look-back window in hours (default 7 days)")):
    """Return recent emergence events split by new themes and inflection founders."""
    cache_key = f"emergence:{hours}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    with get_db() as conn:
        events = conn.execute(
            """SELECT * FROM emergence_events
               WHERE detected_at > datetime('now', ?)
               ORDER BY detected_at DESC""",
            (f"-{hours} hours",),
        ).fetchall()

        new_themes = []
        inflection_founders = []

        for e in events:
            entry = {
                "id": e["id"],
                "eventType": e["event_type"],
                "entityId": e["entity_id"],
                "entityType": e["entity_type"],
                "signal": e["signal"],
                "deltaBefore": e["delta_before"],
                "deltaAfter": e["delta_after"],
                "detectedAt": e["detected_at"],
            }

            if e["entity_type"] == "theme":
                # Enrich with theme info
                t = conn.execute("SELECT name, emergence_score, builder_count FROM themes WHERE id = ?", (e["entity_id"],)).fetchone()
                if t:
                    entry["themeName"] = t["name"]
                    entry["emergenceScore"] = t["emergence_score"]
                    entry["builderCount"] = t["builder_count"]
                new_themes.append(entry)
            else:
                # Enrich with founder info
                f = conn.execute(
                    """SELECT f.name, f.handle, f.company, f.domain,
                              (SELECT composite FROM scores WHERE founder_id = f.id ORDER BY scored_at DESC LIMIT 1) as score
                       FROM founders f WHERE f.id = ?""",
                    (e["entity_id"],),
                ).fetchone()
                if f:
                    entry["founderName"] = f["name"]
                    entry["founderHandle"] = f["handle"]
                    entry["company"] = f["company"] or ""
                    entry["domain"] = f["domain"] or ""
                    entry["score"] = round(f["score"]) if f["score"] else 0
                inflection_founders.append(entry)

    result = {"newThemes": new_themes, "inflectionFounders": inflection_founders}
    _cache_set(cache_key, result)
    return result


@app.get("/api/pulse")
def get_pulse(hours: int = Query(48, description="Look-back window in hours")):
    """Return raw chronological signal feed for the last N hours."""
    cache_key = f"pulse:{hours}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    with get_db() as conn:
        signals = conn.execute(
            """SELECT s.*, f.name as founder_name, f.handle, f.company
               FROM signals s
               JOIN founders f ON f.id = s.founder_id
               WHERE s.detected_at > datetime('now', ?)
               ORDER BY s.detected_at DESC
               LIMIT 200""",
            (f"-{hours} hours",),
        ).fetchall()

        result = [
            {
                "id": s["id"],
                "founderId": s["founder_id"],
                "founderName": s["founder_name"],
                "founderHandle": s["handle"],
                "company": s["company"] or "",
                "source": s["source"],
                "label": s["label"],
                "url": s["url"] or "",
                "strong": bool(s["strong"]),
                "detectedAt": s["detected_at"],
            }
            for s in signals
        ]

    _cache_set(cache_key, result)
    return result


@app.patch("/api/founders/{founder_id}/notes")
def update_notes(founder_id: int, body: dict):
    """Update private notes on a founder."""
    notes = body.get("notes", "")
    with get_db() as conn:
        row = conn.execute("SELECT id FROM founders WHERE id = ?", (founder_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Founder not found")
        conn.execute(
            "UPDATE founders SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (notes, founder_id),
        )
    _cache.clear()
    return {"ok": True}


@app.get("/api/stats")
def dashboard_stats():
    """Aggregate stats for the dashboard header. Cached for 30s to reduce Turso calls."""
    cached = _cache_get("stats")
    if cached:
        return cached

    with get_db() as conn:
        queries = [
            ("SELECT COUNT(*) as c FROM founders", []),
            ("""SELECT COUNT(*) as c FROM founders f
                WHERE (SELECT composite FROM scores WHERE founder_id = f.id
                       ORDER BY scored_at DESC LIMIT 1) >= 90""", []),
            ("SELECT COUNT(*) as c FROM founders WHERE status = 'to_contact'", []),
            ("""SELECT AVG(s.composite) as avg_score
                FROM (SELECT founder_id, composite,
                      ROW_NUMBER() OVER (PARTITION BY founder_id ORDER BY scored_at DESC) as rn
                      FROM scores) s
                WHERE s.rn = 1""", []),
        ]
        cursors = _execute_batch(conn, queries)
        total = cursors[0].fetchone()["c"]
        strong = cursors[1].fetchone()["c"]
        to_contact = cursors[2].fetchone()["c"]
        avg_row = cursors[3].fetchone()
        avg_score = round(avg_row["avg_score"]) if avg_row["avg_score"] else 0

    result = {
        "total": total,
        "strong": strong,
        "toContact": to_contact,
        "avgScore": avg_score,
    }
    _cache_set("stats", result)
    return result
