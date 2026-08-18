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
    raise ValueError(f"Unknown embedding provider '{name}'. Choose mock or sentence_transformer.")


@functools.lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    """The configured provider (settings.EMBEDDING_PROVIDER), cached per process."""
    return build_provider(settings.EMBEDDING_PROVIDER)


@functools.lru_cache
def get_embedding_cache() -> EmbeddingCache:
    """Process-wide query-embedding cache."""
    return EmbeddingCache(max_size=settings.EMBEDDING_QUERY_CACHE_SIZE)
