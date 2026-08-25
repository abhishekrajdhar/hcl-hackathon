"""Redis-backed query-embedding cache — the shared tier above the in-process one.

The local `EmbeddingCache` is per-process, so every worker recomputes the same
query vector once. This puts a shared tier behind it: a hit in Redis is served
by every process, and the local cache still absorbs the repeat traffic without
a round trip.

Two-tier read: local → Redis → compute. Writes go to both.

Redis is treated as strictly optional. If it is not configured, not installed
or not reachable, every method degrades to the local cache and the request
still succeeds — a cache outage must never take out search. Failures are
logged once per process rather than per call, so a downed Redis cannot flood
the logs.
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.embeddings.cache import EmbeddingCache

logger = get_logger(__name__)


class RedisEmbeddingCache(EmbeddingCache):
    """`EmbeddingCache` plus a shared Redis tier. Same key scheme."""

    def __init__(self, url: str, *, max_size: int = 512, ttl_seconds: int = 86_400) -> None:
        super().__init__(max_size=max_size)
        self._url = url
        self._ttl = ttl_seconds
        self._client = None
        self._unavailable = False
        self._warned = False

    # --- connection ------------------------------------------------------
    async def _redis(self):  # type: ignore[no-untyped-def]
        if self._unavailable:
            return None
        if self._client is not None:
            return self._client
        try:
            from redis.asyncio import Redis  # imported lazily: optional dependency
        except ImportError:
            self._disable("redis package not installed")
            return None
        try:
            client = Redis.from_url(self._url, decode_responses=True)
            await client.ping()
        except Exception as exc:  # noqa: BLE001 - any failure means "no cache"
            self._disable(f"connection failed: {exc!s:.120}")
            return None
        self._client = client
        logger.info("redis embedding cache connected")
        return client

    def _disable(self, reason: str) -> None:
        # Flags first: even if logging itself fails, the cache must stay
        # disabled rather than retry-and-raise on every subsequent query.
        self._unavailable = True
        should_warn, self._warned = not self._warned, True
        if should_warn:
            try:
                logger.warning("redis embedding cache disabled: %s", reason)
            except Exception:  # noqa: BLE001, S110 - logging must never break search
                pass

    # --- two-tier access -------------------------------------------------
    async def aget(self, provider: str, dimension: int, text: str) -> list[float] | None:
        local = self.get(provider, dimension, text)
        if local is not None:
            return local

        client = await self._redis()
        if client is None:
            return None
        key = self._key(provider, dimension, text)
        try:
            raw = await client.get(f"emb:{key}")
        except Exception as exc:  # noqa: BLE001
            self._disable(f"read failed: {exc!s:.120}")
            return None
        if not raw:
            return None
        try:
            vector = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(vector, list) or len(vector) != dimension:
            return None  # stale entry from another model width
        # Promote into the local tier so the next hit costs nothing.
        super().put(provider, dimension, text, vector)
        return vector

    async def aput(
        self, provider: str, dimension: int, text: str, vector: list[float]
    ) -> None:
        super().put(provider, dimension, text, vector)
        client = await self._redis()
        if client is None:
            return
        key = self._key(provider, dimension, text)
        try:
            await client.set(f"emb:{key}", json.dumps(vector), ex=self._ttl)
        except Exception as exc:  # noqa: BLE001
            self._disable(f"write failed: {exc!s:.120}")

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # noqa: BLE001, S110 - shutdown is best effort
                pass
            self._client = None
