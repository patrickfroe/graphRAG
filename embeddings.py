"""Utilities for creating text embeddings with OpenAI.

This module exposes a single public helper, ``embed_texts``, which:
- initializes an OpenAI client,
- supports batching to keep payloads manageable,
- retries failed requests with exponential backoff.
"""

from __future__ import annotations

import os
import random
import time
from typing import Iterable

from openai import OpenAI

DEFAULT_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_BATCH_SIZE = int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "100"))
DEFAULT_MAX_RETRIES = int(os.getenv("OPENAI_EMBEDDING_MAX_RETRIES", "5"))
DEFAULT_BACKOFF_SECONDS = float(os.getenv("OPENAI_EMBEDDING_BACKOFF_SECONDS", "1.0"))


def _chunked(items: list[str], batch_size: int) -> Iterable[list[str]]:
    """Yield ``items`` in chunks of ``batch_size``."""
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def _init_client() -> OpenAI:
    """Initialize and return the OpenAI client.

    The OpenAI SDK reads ``OPENAI_API_KEY`` (and related settings) from the
    environment by default.
    """
    return OpenAI()


def _embed_batch(
    client: OpenAI,
    batch: list[str],
    model: str,
    max_retries: int,
    backoff_seconds: float,
) -> list[list[float]]:
    """Embed a single batch with retries and exponential backoff."""
    attempt = 0
    while True:
        attempt += 1
        try:
            response = client.embeddings.create(model=model, input=batch)
            return [item.embedding for item in response.data]
        except Exception:
            if attempt >= max_retries:
                raise

            # Exponential backoff with small jitter to avoid synchronized retries.
            delay = backoff_seconds * (2 ** (attempt - 1))
            jitter = random.uniform(0, backoff_seconds)
            time.sleep(delay + jitter)


def embed_texts(
    texts: list[str],
    *,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> list[list[float]]:
    """Embed a list of texts.

    Args:
        texts: Input texts to embed.
        model: Embedding model name.
        batch_size: Number of texts per API request.
        max_retries: Maximum attempts per batch.
        backoff_seconds: Base delay used for exponential backoff.

    Returns:
        A list of embedding vectors in the same order as ``texts``.
    """
    if not texts:
        return []

    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    if max_retries <= 0:
        raise ValueError("max_retries must be > 0")

    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be >= 0")

    client = _init_client()
    embeddings: list[list[float]] = []

    for batch in _chunked(texts, batch_size):
        embeddings.extend(
            _embed_batch(
                client=client,
                batch=batch,
                model=model,
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
        )

    return embeddings
