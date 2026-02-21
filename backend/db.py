import sqlite3
from contextlib import contextmanager

from backend.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS founders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    handle          TEXT UNIQUE NOT NULL,
    avatar          TEXT DEFAULT '',
    location        TEXT DEFAULT '',
    bio             TEXT DEFAULT '',
    domain          TEXT DEFAULT '',
    stage           TEXT DEFAULT 'Unknown',
    company         TEXT DEFAULT '',
    founded         TEXT DEFAULT '',
    status          TEXT DEFAULT 'to_contact'
                    CHECK(status IN ('to_contact','watching','contacted','pass')),
    yc_alumni_connections INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS founder_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    source      TEXT NOT NULL CHECK(source IN ('github','hn','producthunt')),
    source_id   TEXT DEFAULT '',
    profile_url TEXT DEFAULT '',
    UNIQUE(founder_id, source)
);

CREATE TABLE IF NOT EXISTS founder_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    UNIQUE(founder_id, tag)
);

CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    source      TEXT NOT NULL CHECK(source IN ('github','hn','producthunt')),
    label       TEXT NOT NULL,
    url         TEXT DEFAULT '',
    strong      BOOLEAN DEFAULT 0,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stats_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id      INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    github_stars    INTEGER DEFAULT 0,
    github_commits_90d INTEGER DEFAULT 0,
    github_repos    INTEGER DEFAULT 0,
    hn_karma        INTEGER DEFAULT 0,
    hn_submissions  INTEGER DEFAULT 0,
    hn_top_score    INTEGER DEFAULT 0,
    ph_upvotes      INTEGER DEFAULT 0,
    ph_launches     INTEGER DEFAULT 0,
    followers       INTEGER DEFAULT 0,
    captured_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    momentum    REAL DEFAULT 0,
    domain_score REAL DEFAULT 0,
    team        REAL DEFAULT 0,
    traction    REAL DEFAULT 0,
    ycfit       REAL DEFAULT 0,
    composite   REAL DEFAULT 0,
    scored_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    alert_type  TEXT NOT NULL,
    channel     TEXT NOT NULL,
    message     TEXT NOT NULL,
    sent_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_founder ON signals(founder_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_founder ON scores(founder_id, scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_stats_founder ON stats_snapshots(founder_id, captured_at DESC);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)


def upsert_founder(conn, *, name, handle, **kwargs):
    """Insert or update a founder by handle. Returns founder id."""
    existing = conn.execute(
        "SELECT id FROM founders WHERE handle = ?", (handle,)
    ).fetchone()
    if existing:
        fid = existing["id"]
        sets = ", ".join(f"{k} = ?" for k in kwargs if kwargs[k] is not None)
        vals = [v for v in kwargs.values() if v is not None]
        if sets:
            conn.execute(
                f"UPDATE founders SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                vals + [fid],
            )
        return fid
    cols = ["name", "handle"] + [k for k in kwargs if kwargs[k] is not None]
    placeholders = ", ".join("?" for _ in cols)
    vals = [name, handle] + [v for v in kwargs.values() if v is not None]
    cur = conn.execute(
        f"INSERT INTO founders ({', '.join(cols)}) VALUES ({placeholders})", vals
    )
    return cur.lastrowid


def add_source(conn, founder_id, source, source_id="", profile_url=""):
    conn.execute(
        """INSERT INTO founder_sources (founder_id, source, source_id, profile_url)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(founder_id, source) DO UPDATE SET
             source_id = excluded.source_id,
             profile_url = excluded.profile_url""",
        (founder_id, source, source_id, profile_url),
    )


def add_signal(conn, founder_id, source, label, url="", strong=False):
    # Avoid duplicate signals with the same label in the last 24h
    dup = conn.execute(
        """SELECT id FROM signals
           WHERE founder_id = ? AND label = ?
             AND detected_at > datetime('now', '-1 day')""",
        (founder_id, label),
    ).fetchone()
    if not dup:
        conn.execute(
            "INSERT INTO signals (founder_id, source, label, url, strong) VALUES (?, ?, ?, ?, ?)",
            (founder_id, source, label, url, strong),
        )


def add_tags(conn, founder_id, tags):
    for tag in tags:
        conn.execute(
            """INSERT INTO founder_tags (founder_id, tag) VALUES (?, ?)
               ON CONFLICT(founder_id, tag) DO NOTHING""",
            (founder_id, tag),
        )


def save_stats(conn, founder_id, **stats):
    cols = ["founder_id"] + list(stats.keys())
    placeholders = ", ".join("?" for _ in cols)
    vals = [founder_id] + list(stats.values())
    conn.execute(
        f"INSERT INTO stats_snapshots ({', '.join(cols)}) VALUES ({placeholders})", vals
    )


def save_score(conn, founder_id, momentum, domain_score, team, traction, ycfit, composite):
    conn.execute(
        """INSERT INTO scores (founder_id, momentum, domain_score, team, traction, ycfit, composite)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (founder_id, momentum, domain_score, team, traction, ycfit, composite),
    )


def get_latest_stats(conn, founder_id):
    return conn.execute(
        "SELECT * FROM stats_snapshots WHERE founder_id = ? ORDER BY captured_at DESC LIMIT 1",
        (founder_id,),
    ).fetchone()


def get_previous_score(conn, founder_id):
    """Get the second-most-recent score (the one before the current run)."""
    rows = conn.execute(
        "SELECT * FROM scores WHERE founder_id = ? ORDER BY scored_at DESC LIMIT 2",
        (founder_id,),
    ).fetchall()
    return rows[1] if len(rows) >= 2 else None


def get_all_founders(conn):
    return conn.execute(
        """SELECT f.*,
                  (SELECT composite FROM scores WHERE founder_id = f.id ORDER BY scored_at DESC LIMIT 1) as score
           FROM founders f
           ORDER BY score DESC NULLS LAST"""
    ).fetchall()
