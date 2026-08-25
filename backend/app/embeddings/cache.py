"""Bounded in-process cache for query-text embeddings.

Resource embeddings are cached durably in Postgres; this covers the other side —
repeated *query* strings — so an identical search does not recompute a vector.
Keyed by (provider, dimension, sha256(text)) so switching providers or models
never returns a stale vector. In-memory and per-process by design; a Redis-
backed cache can replace it behind the same interface if cross-process sharing
is ever needed.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict


class EmbeddingCache:
    def __init__(self, max_size: int = 512) -> None:
        self._store: OrderedDict[str, list[float]] = OrderedDict()
        self._max_size = max(1, max_size)
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(provider: str, dimension: int, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{provider}:{dimension}:{digest}"

    def get(self, provider: str, dimension: int, text: str) -> list[float] | None:
        key = self._key(provider, dimension, text)
        vector = self._store.get(key)
        if vector is None:
            self.misses += 1
            return None
        self._store.move_to_end(key)  # LRU touch
        self.hits += 1
        return vector

    def put(self, provider: str, dimension: int, text: str, vector: list[float]) -> None:
        key = self._key(provider, dimension, text)
        self._store[key] = vector
        self._store.move_to_end(key)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)  # evict least-recently-used

    def clear(self) -> None:
        self._store.clear()

    # --- async surface ---------------------------------------------------
    # The local cache needs no awaiting, but callers use the async form so a
    # shared tier (see `redis_cache.py`) can slot in without touching them.
    async def aget(self, provider: str, dimension: int, text: str) -> list[float] | None:
        return self.get(provider, dimension, text)

    async def aput(
        self, provider: str, dimension: int, text: str, vector: list[float]
    ) -> None:
        self.put(provider, dimension, text, vector)

    async def aclose(self) -> None:
        return None
