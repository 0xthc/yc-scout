"""
FastAPI server — serves scored founder data to the React frontend.
Also exposes endpoints to trigger pipeline runs and update founder status.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.db import get_db, init_db
from backend.models import FounderOut, PipelineResult, StatusUpdate
from backend.pipeline import run_pipeline

logger = logging.getLogger(__name__)


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
        "sources": sources,
        "tags": tags,
        "score": round(score_row["composite"]) if score_row else 0,
        "scoreBreakdown": {
            "momentum": round(score_row["momentum"]) if score_row else 0,
            "domain": round(score_row["domain_score"]) if score_row else 0,
            "team": round(score_row["team"]) if score_row else 0,
            "traction": round(score_row["traction"]) if score_row else 0,
            "ycfit": round(score_row["ycfit"]) if score_row else 0,
        },
        "signals": signals,
        "github_stars": stats_row["github_stars"] if stats_row else 0,
        "hn_karma": stats_row["hn_karma"] if stats_row else 0,
        "followers": stats_row["followers"] if stats_row else 0,
    }


@app.get("/api/founders", response_model=list[FounderOut])
def list_founders():
    """List all founders sorted by composite score."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.*
               FROM founders f
               ORDER BY (
                   SELECT composite FROM scores
                   WHERE founder_id = f.id
                   ORDER BY scored_at DESC LIMIT 1
               ) DESC NULLS LAST"""
        ).fetchall()
        return [_build_founder(conn, r) for r in rows]


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
    return {"ok": True, "status": body.status}


@app.post("/api/pipeline/run", response_model=PipelineResult)
def trigger_pipeline():
    """Manually trigger a full pipeline run: scrape → score → alert."""
    result = run_pipeline()
    return result


@app.get("/api/stats")
def dashboard_stats():
    """Aggregate stats for the dashboard header."""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM founders").fetchone()["c"]
        strong = conn.execute(
            """SELECT COUNT(*) as c FROM founders f
               WHERE (SELECT composite FROM scores WHERE founder_id = f.id
                      ORDER BY scored_at DESC LIMIT 1) >= 90"""
        ).fetchone()["c"]
        to_contact = conn.execute(
            "SELECT COUNT(*) as c FROM founders WHERE status = 'to_contact'"
        ).fetchone()["c"]
        avg_row = conn.execute(
            """SELECT AVG(s.composite) as avg_score
               FROM (SELECT founder_id, composite,
                     ROW_NUMBER() OVER (PARTITION BY founder_id ORDER BY scored_at DESC) as rn
                     FROM scores) s
               WHERE s.rn = 1"""
        ).fetchone()
        avg_score = round(avg_row["avg_score"]) if avg_row["avg_score"] else 0

    return {
        "total": total,
        "strong": strong,
        "toContact": to_contact,
        "avgScore": avg_score,
    }
