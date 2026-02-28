"""Simple SQLite-backed vector store for chunk embeddings.

Collection schema (`chunks`):
- chunk_id PRIMARY KEY
- doc_id
- text
- embedding (stored as JSON array of floats)
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping, Sequence

_DB_PATH = Path(__file__).with_name("vectorstore.db")
_EXPECTED_DIM: int | None = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_embedding(values: Sequence[float], *, dim: int | None = None) -> list[float]:
    try:
        embedding = [float(v) for v in values]
    except TypeError as exc:
        raise ValueError("embedding must be a sequence of numbers") from exc

    if dim is not None and len(embedding) != dim:
        raise ValueError(f"embedding dimension mismatch: expected {dim}, got {len(embedding)}")

    return embedding


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("cannot compare vectors with different dimensions")

    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def ensure_collection(dim: int) -> None:
    """Create collection `chunks` if needed and remember the expected embedding dimension."""
    if dim <= 0:
        raise ValueError("dim must be a positive integer")

    global _EXPECTED_DIM
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        row = conn.execute("SELECT value FROM metadata WHERE key='embedding_dim'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO metadata(key, value) VALUES('embedding_dim', ?)",
                (str(dim),),
            )
        else:
            existing = int(row["value"])
            if existing != dim:
                raise ValueError(f"collection already initialized with dim={existing}, not {dim}")

    _EXPECTED_DIM = dim


def _get_expected_dim() -> int:
    global _EXPECTED_DIM
    if _EXPECTED_DIM is not None:
        return _EXPECTED_DIM

    with _connect() as conn:
        row = conn.execute("SELECT value FROM metadata WHERE key='embedding_dim'").fetchone()

    if row is None:
        raise RuntimeError("collection is not initialized; call ensure_collection(dim) first")

    _EXPECTED_DIM = int(row["value"])
    return _EXPECTED_DIM


def upsert_chunks(chunks: Iterable[Mapping[str, object]]) -> int:
    """Insert or update chunk rows.

    Each chunk must include: `chunk_id`, `doc_id`, `text`, `embedding`.
    Returns number of processed rows.
    """
    expected_dim = _get_expected_dim()
    rows_to_write: list[tuple[str, str, str, str]] = []

    for chunk in chunks:
        try:
            chunk_id = str(chunk["chunk_id"])
            doc_id = str(chunk["doc_id"])
            text = str(chunk["text"])
            embedding_raw = chunk["embedding"]
        except KeyError as exc:
            raise ValueError(f"missing required chunk field: {exc.args[0]}") from exc

        embedding = _normalize_embedding(embedding_raw, dim=expected_dim)
        rows_to_write.append((chunk_id, doc_id, text, json.dumps(embedding)))

    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO chunks(chunk_id, doc_id, text, embedding)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                doc_id=excluded.doc_id,
                text=excluded.text,
                embedding=excluded.embedding
            """,
            rows_to_write,
        )

    return len(rows_to_write)


def search(query_embedding: Sequence[float], top_k: int) -> list[dict[str, object]]:
    """Return top_k chunks ranked by cosine similarity to query_embedding."""
    if top_k <= 0:
        return []

    expected_dim = _get_expected_dim()
    query = _normalize_embedding(query_embedding, dim=expected_dim)

    with _connect() as conn:
        rows = conn.execute("SELECT chunk_id, doc_id, text, embedding FROM chunks").fetchall()

    scored: list[dict[str, object]] = []
    for row in rows:
        embedding = json.loads(row["embedding"])
        score = _cosine_similarity(query, embedding)
        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "doc_id": row["doc_id"],
                "text": row["text"],
                "score": score,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
