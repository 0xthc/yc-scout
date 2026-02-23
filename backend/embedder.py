"""
Embedder — converts founder content into vector embeddings for clustering.

Uses OpenAI text-embedding-3-small (1536 dims) when OPENAI_API_KEY is set.
Falls back to a simple TF-IDF-based vector when key is absent (dev mode).

Embedded content = bio + domain + tags + recent signal labels.
Content hash (sha256) is stored alongside the vector to enable cache invalidation.
"""

import hashlib
import logging
import os
import struct

import numpy as np

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_DIM = 1536  # text-embedding-3-small


# ── Content builder ──────────────────────────────────────────


def _build_founder_text(conn, founder_id: int) -> str:
    """Assemble embeddable text for a founder."""
    row = conn.execute("SELECT bio, domain, company FROM founders WHERE id = ?", (founder_id,)).fetchone()
    if not row:
        return ""

    parts = []
    if row["bio"]:
        parts.append(row["bio"])
    if row["domain"]:
        parts.append(f"domain: {row['domain']}")
    if row["company"]:
        parts.append(f"company: {row['company']}")

    tags = conn.execute(
        "SELECT tag FROM founder_tags WHERE founder_id = ?", (founder_id,)
    ).fetchall()
    if tags:
        parts.append("tags: " + " ".join(t["tag"] for t in tags))

    signals = conn.execute(
        "SELECT label FROM signals WHERE founder_id = ? ORDER BY detected_at DESC LIMIT 20",
        (founder_id,),
    ).fetchall()
    if signals:
        parts.append("signals: " + ". ".join(s["label"] for s in signals))

    return " | ".join(parts)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ── Vector serialization ─────────────────────────────────────


def _serialize(vec: np.ndarray) -> bytes:
    """Serialize float32 numpy array to bytes."""
    return struct.pack(f"{len(vec)}f", *vec.tolist())


def _deserialize(blob: bytes) -> np.ndarray:
    """Deserialize bytes back to float32 numpy array."""
    n = len(blob) // 4
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


# ── OpenAI embedding ─────────────────────────────────────────


def _embed_openai(texts: list[str]) -> list[np.ndarray]:
    """Call OpenAI text-embedding-3-small for a batch of texts."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [np.array(item.embedding, dtype=np.float32) for item in response.data]


# ── Fallback: TF-IDF bag-of-words (dev mode) ────────────────


_tfidf_vocab: dict[str, int] = {}
_tfidf_dim = 256


def _embed_tfidf(texts: list[str]) -> list[np.ndarray]:
    """Simple bag-of-words fallback when no OpenAI key is available."""
    global _tfidf_vocab
    results = []
    for text in texts:
        words = text.lower().split()
        vec = np.zeros(_tfidf_dim, dtype=np.float32)
        for word in words:
            if word not in _tfidf_vocab and len(_tfidf_vocab) < _tfidf_dim:
                _tfidf_vocab[word] = len(_tfidf_vocab)
            idx = _tfidf_vocab.get(word)
            if idx is not None:
                vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        # Pad to EMBEDDING_DIM for consistency
        padded = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        padded[:_tfidf_dim] = vec
        results.append(padded)
    return results


def _embed_texts(texts: list[str]) -> list[np.ndarray]:
    if OPENAI_API_KEY:
        return _embed_openai(texts)
    logger.warning("OPENAI_API_KEY not set — using TF-IDF fallback embeddings (low quality)")
    return _embed_tfidf(texts)


# ── Public API ───────────────────────────────────────────────

BATCH_SIZE = 100


def embed_founder(conn, founder_id: int) -> np.ndarray | None:
    """Embed a single founder. Returns the vector or None on error."""
    text = _build_founder_text(conn, founder_id)
    if not text.strip():
        logger.debug("Founder %d has no embeddable content — skipping", founder_id)
        return None

    chash = _content_hash(text)

    # Check cache
    existing = conn.execute(
        "SELECT content_hash FROM founder_embeddings WHERE founder_id = ?", (founder_id,)
    ).fetchone()
    if existing and existing["content_hash"] == chash:
        logger.debug("Founder %d embedding up to date", founder_id)
        blob = conn.execute(
            "SELECT vector FROM founder_embeddings WHERE founder_id = ?", (founder_id,)
        ).fetchone()
        return _deserialize(blob["vector"]) if blob else None

    try:
        vecs = _embed_texts([text])
        vec = vecs[0]
    except Exception as e:
        logger.error("Embedding failed for founder %d: %s", founder_id, e)
        return None

    blob = _serialize(vec)
    conn.execute(
        """INSERT INTO founder_embeddings (founder_id, vector, content_hash)
           VALUES (?, ?, ?)
           ON CONFLICT(founder_id) DO UPDATE SET
             vector = excluded.vector,
             content_hash = excluded.content_hash,
             embedded_at = CURRENT_TIMESTAMP""",
        (founder_id, blob, chash),
    )
    logger.info("Embedded founder %d (%d chars)", founder_id, len(text))
    return vec


def embed_all_founders(conn) -> int:
    """Embed all founders with missing or stale embeddings. Returns count embedded."""
    founders = conn.execute("SELECT id FROM founders").fetchall()
    to_embed = []

    for f in founders:
        fid = f["id"]
        text = _build_founder_text(conn, fid)
        if not text.strip():
            continue
        chash = _content_hash(text)
        existing = conn.execute(
            "SELECT content_hash FROM founder_embeddings WHERE founder_id = ?", (fid,)
        ).fetchone()
        if existing and existing["content_hash"] == chash:
            continue
        to_embed.append((fid, text, chash))

    if not to_embed:
        logger.info("All founder embeddings up to date")
        return 0

    logger.info("Embedding %d founders in batches of %d", len(to_embed), BATCH_SIZE)
    embedded = 0

    for i in range(0, len(to_embed), BATCH_SIZE):
        batch = to_embed[i: i + BATCH_SIZE]
        texts = [b[1] for b in batch]
        try:
            vecs = _embed_texts(texts)
        except Exception as e:
            logger.error("Batch embedding failed: %s", e)
            continue

        for (fid, _, chash), vec in zip(batch, vecs):
            blob = _serialize(vec)
            conn.execute(
                """INSERT INTO founder_embeddings (founder_id, vector, content_hash)
                   VALUES (?, ?, ?)
                   ON CONFLICT(founder_id) DO UPDATE SET
                     vector = excluded.vector,
                     content_hash = excluded.content_hash,
                     embedded_at = CURRENT_TIMESTAMP""",
                (fid, blob, chash),
            )
            embedded += 1

    logger.info("Embedded %d founders", embedded)
    return embedded


def load_embeddings(conn) -> tuple[list[int], np.ndarray]:
    """Load all stored embeddings. Returns (founder_ids, matrix of shape [N, dim])."""
    rows = conn.execute(
        "SELECT founder_id, vector FROM founder_embeddings"
    ).fetchall()
    if not rows:
        return [], np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    ids = [r["founder_id"] for r in rows]
    matrix = np.stack([_deserialize(r["vector"]) for r in rows])
    return ids, matrix
