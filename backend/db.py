"""
Database layer — supports both local SQLite and Turso (HTTP API) for production.

Mode selection via environment:
  - TURSO_DATABASE_URL + TURSO_AUTH_TOKEN set → Turso over HTTP (via httpx)
  - Otherwise → plain local SQLite (dev mode)
"""

import os
import sqlite3
from contextlib import contextmanager

import httpx

from backend.config import DB_PATH

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

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
    incubator       TEXT DEFAULT '',
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
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id          INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    founder_quality     REAL DEFAULT 0,
    execution_velocity  REAL DEFAULT 0,
    market_conviction   REAL DEFAULT 0,
    early_traction      REAL DEFAULT 0,
    deal_availability   REAL DEFAULT 0,
    composite           REAL DEFAULT 0,
    scored_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

CREATE TABLE IF NOT EXISTS founder_embeddings (
    founder_id      INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE PRIMARY KEY,
    vector          BLOB NOT NULL,
    content_hash    TEXT NOT NULL,
    embedded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS themes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    emergence_score INTEGER DEFAULT 0,
    builder_count   INTEGER DEFAULT 0,
    weekly_velocity REAL DEFAULT 0,
    pain_summary    TEXT DEFAULT '',
    unlock_summary  TEXT DEFAULT '',
    founder_origin  TEXT DEFAULT '',
    first_detected  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS founder_themes (
    founder_id  INTEGER NOT NULL REFERENCES founders(id) ON DELETE CASCADE,
    theme_id    INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    similarity  REAL DEFAULT 0,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (founder_id, theme_id)
);

CREATE TABLE IF NOT EXISTS theme_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id        INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    emergence_score INTEGER,
    builder_count   INTEGER,
    captured_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emergence_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    entity_id   INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    signal      TEXT NOT NULL,
    delta_before REAL,
    delta_after  REAL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emergence_detected ON emergence_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_theme_history ON theme_history(theme_id, captured_at DESC);
"""


# ── Turso HTTP wrapper ──────────────────────────────────────


class _TursoRow:
    """Dict-like row supporting both row['col'] and row[0] access."""

    def __init__(self, columns, values):
        self._cols = columns
        self._vals = values
        self._map = dict(zip(columns, values))

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._map[key]
        return self._vals[key]

    def __contains__(self, key):
        return key in self._map

    def get(self, key, default=None):
        return self._map.get(key, default)

    def keys(self):
        return self._cols


class _TursoCursor:
    def __init__(self, columns, rows, last_insert_rowid=None):
        self._rows = [_TursoRow(columns, r) for r in rows]
        self.lastrowid = last_insert_rowid

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


def _encode_arg(val):
    """Encode a Python value to a Turso HTTP API argument."""
    if val is None:
        return {"type": "null"}
    if isinstance(val, bool):
        return {"type": "integer", "value": str(int(val))}
    if isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    if isinstance(val, float):
        return {"type": "float", "value": val}
    if isinstance(val, (bytes, bytearray)):
        import base64
        return {"type": "blob", "base64": base64.b64encode(val).decode("ascii")}
    return {"type": "text", "value": str(val)}


def _decode_row(raw_row):
    """Decode a row from Turso HTTP API response."""
    import base64 as _b64
    vals = []
    for cell in raw_row:
        t = cell.get("type", "null")
        if t == "null":
            vals.append(None)
        elif t == "integer":
            vals.append(int(cell["value"]))
        elif t == "float":
            vals.append(float(cell["value"]))
        elif t == "blob":
            vals.append(_b64.b64decode(cell.get("base64", "")))
        else:
            vals.append(cell.get("value"))
    return vals


class _TursoConnection:
    """sqlite3-compatible connection that talks to Turso over HTTP."""

    def __init__(self, url, token):
        # Convert libsql:// to https://
        http_url = url.replace("libsql://", "https://").rstrip("/")
        self._url = f"{http_url}/v3/pipeline"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.Client(timeout=30)

    def _pipeline(self, requests):
        resp = self._client.post(
            self._url,
            json={"requests": requests},
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()["results"]

    def execute(self, sql, params=None):
        args = [_encode_arg(p) for p in params] if params else []
        results = self._pipeline([
            {"type": "execute", "stmt": {"sql": sql, "args": args}},
            {"type": "close"},
        ])
        r = results[0]
        if r["type"] == "error":
            raise RuntimeError(r["error"]["message"])
        res = r["response"]["result"]
        columns = [c["name"] for c in res.get("cols", [])]
        rows = [_decode_row(raw) for raw in res.get("rows", [])]
        last_id = res.get("last_insert_rowid")
        return _TursoCursor(columns, rows, last_id)

    def execute_batch(self, queries):
        """Execute multiple queries in a single HTTP pipeline call.

        queries: list of (sql, params) tuples
        Returns: list of _TursoCursor
        """
        requests = []
        for sql, params in queries:
            args = [_encode_arg(p) for p in params] if params else []
            requests.append({"type": "execute", "stmt": {"sql": sql, "args": args}})
        requests.append({"type": "close"})
        results = self._pipeline(requests)
        cursors = []
        for r in results:
            if r.get("type") == "error":
                raise RuntimeError(r["error"]["message"])
            if r.get("type") == "ok":
                res = r.get("response", {}).get("result")
                if res is None:
                    continue  # skip "close" responses
                columns = [c["name"] for c in res.get("cols", [])]
                rows = [_decode_row(raw) for raw in res.get("rows", [])]
                last_id = res.get("last_insert_rowid")
                cursors.append(_TursoCursor(columns, rows, last_id))
        return cursors

    def executescript(self, sql):
        stmts = [s.strip() for s in sql.split(";") if s.strip()]
        requests = [{"type": "execute", "stmt": {"sql": s}} for s in stmts]
        requests.append({"type": "close"})
        results = self._pipeline(requests)
        for r in results:
            if r.get("type") == "error":
                raise RuntimeError(r["error"]["message"])

    def commit(self):
        pass  # Each HTTP request is auto-committed

    def rollback(self):
        pass  # No transaction support in HTTP pipeline mode

    def close(self):
        self._client.close()

    def sync(self):
        pass  # Not an embedded replica


# ── Connection management ────────────────────────────────────


def _use_turso():
    return bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)


def get_connection():
    if _use_turso():
        return _TursoConnection(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)

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
        _migrate_scores_columns(conn)


# Column mapping: old name → new name
_SCORE_COLUMN_RENAMES = [
    ("momentum", "founder_quality"),
    ("domain_score", "execution_velocity"),
    ("team", "market_conviction"),
    ("traction", "early_traction"),
    ("ycfit", "deal_availability"),
]


def _migrate_scores_columns(conn):
    """Rename legacy score columns if they exist (one-time migration).

    Uses ALTER TABLE RENAME COLUMN (supported since SQLite 3.25 / libsql).
    Each rename is wrapped in try/except so it's safe to run repeatedly.
    """
    for old_name, new_name in _SCORE_COLUMN_RENAMES:
        try:
            conn.execute(f"ALTER TABLE scores RENAME COLUMN {old_name} TO {new_name}")
        except Exception:
            pass  # Column already renamed, doesn't exist, or table is new

    # Add incubator column if missing
    try:
        conn.execute("ALTER TABLE founders ADD COLUMN incubator TEXT DEFAULT ''")
    except Exception:
        pass  # Column already exists

    # Add notes column if missing
    try:
        conn.execute("ALTER TABLE founders ADD COLUMN notes TEXT DEFAULT ''")
    except Exception:
        pass

    # entity_type column — 'startup' | 'individual'
    try:
        conn.execute("ALTER TABLE founders ADD COLUMN entity_type TEXT DEFAULT 'individual'")
    except Exception:
        pass
    # Back-fill: anyone with an incubator set is a startup
    try:
        conn.execute("UPDATE founders SET entity_type = 'startup' WHERE incubator != '' AND incubator IS NOT NULL AND entity_type = 'individual'")
    except Exception:
        pass

    # Enrichment columns
    for col, definition in [
        ("enriched_at", "TIMESTAMP"),
        ("twitter_handle", "TEXT DEFAULT ''"),
        ("twitter_followers", "INTEGER DEFAULT 0"),
        ("twitter_engagement_rate", "REAL DEFAULT 0"),
        ("linkedin_url", "TEXT DEFAULT ''"),
        ("linkedin_summary", "TEXT DEFAULT ''"),
        ("is_serial_founder", "BOOLEAN DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE founders ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already exists


# ── Data helpers ─────────────────────────────────────────────


def upsert_founder(conn, *, name, handle, **kwargs):
    """Insert or update a founder by handle. Returns founder id."""
    existing = conn.execute(
        "SELECT id FROM founders WHERE handle = ?", (handle,)
    ).fetchone()
    if existing:
        fid = existing["id"] if isinstance(existing, (dict, _TursoRow, sqlite3.Row)) else existing[0]
        filtered = {k: v for k, v in kwargs.items() if v is not None}
        if filtered:
            sets = ", ".join(f"{k} = ?" for k in filtered)
            vals = list(filtered.values())
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


def save_score(conn, founder_id, founder_quality, execution_velocity, market_conviction, early_traction, deal_availability, composite):
    conn.execute(
        """INSERT INTO scores (founder_id, founder_quality, execution_velocity, market_conviction, early_traction, deal_availability, composite)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (founder_id, founder_quality, execution_velocity, market_conviction, early_traction, deal_availability, composite),
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
