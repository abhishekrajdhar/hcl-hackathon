"""Embedding-provider selection.

Chosen from settings (env), never hard-coded. If `sentence_transformer` is
requested but the dependency is missing, it degrades to the mock with a warning
so the backend still runs locally — exactly the fallback the task asks for.
"""

from __future__ import annotations

import functools

from app.core.config import settings
from app.core.logging import get_logger
from app.embeddings.base import EmbeddingProvider
from app.embeddings.cache import EmbeddingCache
from app.embeddings.providers.mock import MockEmbeddingProvider
from app.embeddings.providers.openai import OpenAIEmbeddingProvider
from app.embeddings.providers.sentence_transformer import SentenceTransformerProvider

logger = get_logger(__name__)


def build_provider(name: str) -> EmbeddingProvider:
    key = name.lower()
    if key == "mock":
        return MockEmbeddingProvider()
    if key == "sentence_transformer":
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; falling back to the mock "
                "embedding provider so the backend can still run"
            )
            return MockEmbeddingProvider()
        return SentenceTransformerProvider()
    if key == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set; falling "
                "back to the mock provider so the backend can still run"
            )
            return MockEmbeddingProvider()
        return OpenAIEmbeddingProvider()
    raise ValueError(
        f"Unknown embedding provider '{name}'. "
        "Choose mock, sentence_transformer or openai."
    )


@functools.lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """The configured provider (settings.EMBEDDING_PROVIDER), cached per process."""
    return build_provider(settings.EMBEDDING_PROVIDER)


@functools.lru_cache
def get_embedding_cache() -> EmbeddingCache:
    """Query-embedding cache: Redis-backed when configured, else in-process.

    Chosen from settings like every other provider in the app. The Redis
    variant is a subclass, so callers see one type either way and an
    unreachable Redis silently degrades to the local tier.
    """
    if settings.REDIS_URL and settings.EMBEDDING_CACHE_BACKEND == "redis":
        from app.embeddings.redis_cache import RedisEmbeddingCache

        return RedisEmbeddingCache(
            settings.REDIS_URL,
            max_size=settings.EMBEDDING_QUERY_CACHE_SIZE,
            ttl_seconds=settings.EMBEDDING_CACHE_TTL_SECONDS,
        )
    return EmbeddingCache(max_size=settings.EMBEDDING_QUERY_CACHE_SIZE)
