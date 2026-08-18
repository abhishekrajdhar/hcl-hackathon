"""Semantic embedding layer: swappable providers, canonical text, query cache."""

from app.embeddings.base import EmbeddingError, EmbeddingProvider
from app.embeddings.cache import EmbeddingCache
from app.embeddings.factory import build_provider, get_embedding_provider
from app.embeddings.text import (
    canonical_goal_query_text,
    canonical_profile_query_text,
    canonical_resource_text,
    canonical_skill_query_text,
)

__all__ = [
    "EmbeddingCache",
    "EmbeddingError",
    "EmbeddingProvider",
    "build_provider",
    "canonical_goal_query_text",
    "canonical_profile_query_text",
    "canonical_resource_text",
    "canonical_skill_query_text",
    "get_embedding_provider",
]
