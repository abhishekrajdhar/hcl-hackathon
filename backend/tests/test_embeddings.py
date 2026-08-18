"""Unit tests for the embedding layer: providers, canonical text, cache.

No database and no network — the mock provider is deterministic.
"""

from __future__ import annotations

import math

import pytest

from app.embeddings.base import EmbeddingProvider
from app.embeddings.cache import EmbeddingCache
from app.embeddings.factory import build_provider, get_embedding_provider
from app.embeddings.providers.mock import MockEmbeddingProvider
from app.embeddings.providers.sentence_transformer import SentenceTransformerProvider
from app.embeddings.text import (
    canonical_goal_query_text,
    canonical_profile_query_text,
    canonical_resource_text,
    canonical_skill_query_text,
)


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


# --- provider selection ----------------------------------------------------
def test_default_provider_is_mock() -> None:
    assert isinstance(get_embedding_provider(), MockEmbeddingProvider)


def test_build_known_providers() -> None:
    assert isinstance(build_provider("mock"), MockEmbeddingProvider)


def test_build_unknown_provider_raises() -> None:
    with pytest.raises(ValueError):
        build_provider("word2vec")


def test_sentence_transformer_falls_back_to_mock_when_missing() -> None:
    # sentence-transformers is not installed in the test env, so selecting it
    # must degrade to the mock rather than crash — the required local fallback.
    provider = build_provider("sentence_transformer")
    assert isinstance(provider, (MockEmbeddingProvider, SentenceTransformerProvider))


def test_provider_conforms_to_interface() -> None:
    provider = MockEmbeddingProvider()
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension == 384


# --- mock embedding properties ---------------------------------------------
@pytest.mark.asyncio
async def test_embedding_has_correct_dimension() -> None:
    provider = MockEmbeddingProvider(dimension=384)
    vec = await provider.embed_text("machine learning")
    assert len(vec) == 384


@pytest.mark.asyncio
async def test_embedding_is_deterministic() -> None:
    provider = MockEmbeddingProvider()
    a = await provider.embed_text("deep learning with pytorch")
    b = await provider.embed_text("deep learning with pytorch")
    assert a == b


@pytest.mark.asyncio
async def test_embedding_is_unit_normalised() -> None:
    provider = MockEmbeddingProvider()
    vec = await provider.embed_text("computer vision object detection")
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-6)


@pytest.mark.asyncio
async def test_similar_texts_are_closer_than_unrelated() -> None:
    provider = MockEmbeddingProvider()
    base = await provider.embed_text("deep learning neural networks course")
    similar = await provider.embed_text("a course on neural networks and deep learning")
    unrelated = await provider.embed_text("italian pasta cooking recipes")
    assert _cos(base, similar) > _cos(base, unrelated)


@pytest.mark.asyncio
async def test_batch_matches_individual() -> None:
    provider = MockEmbeddingProvider()
    texts = ["python", "statistics", "transformers"]
    batch = await provider.embed_texts(texts)
    for text, vector in zip(texts, batch, strict=True):
        assert vector == await provider.embed_text(text)


@pytest.mark.asyncio
async def test_empty_text_yields_zero_vector() -> None:
    provider = MockEmbeddingProvider()
    vec = await provider.embed_text("")
    assert vec == [0.0] * provider.dimension


# --- canonical text --------------------------------------------------------
def test_canonical_resource_text_includes_all_parts() -> None:
    text = canonical_resource_text(
        title="Deep Learning Specialization",
        description="Neural networks and optimization",
        resource_type="course",
        taught_skill_names=["Deep Learning", "Neural Networks"],
        prerequisite_skill_names=["Machine Learning"],
    )
    assert "Title: Deep Learning Specialization" in text
    assert "Type: course" in text
    assert "Description: Neural networks and optimization" in text
    assert "Teaches: Deep Learning, Neural Networks" in text
    assert "Prerequisites: Machine Learning" in text


def test_canonical_resource_text_is_order_independent() -> None:
    a = canonical_resource_text(
        title="X", description=None, resource_type="course",
        taught_skill_names=["B", "A"], prerequisite_skill_names=[],
    )
    b = canonical_resource_text(
        title="X", description=None, resource_type="course",
        taught_skill_names=["A", "B"], prerequisite_skill_names=[],
    )
    assert a == b  # skills are sorted, so link order does not change embedding


def test_canonical_query_texts_build() -> None:
    assert "Target role" in canonical_goal_query_text(target_role="ML Engineer")
    assert canonical_skill_query_text(name="Python", aliases=["py"]).startswith("Python")
    assert "Interests" in canonical_profile_query_text(interests=["nlp"])


# --- cache -----------------------------------------------------------------
def test_cache_hit_and_miss() -> None:
    cache = EmbeddingCache(max_size=8)
    assert cache.get("mock", 384, "q") is None
    assert cache.misses == 1
    cache.put("mock", 384, "q", [0.1, 0.2])
    assert cache.get("mock", 384, "q") == [0.1, 0.2]
    assert cache.hits == 1


def test_cache_is_keyed_by_provider_and_dimension() -> None:
    cache = EmbeddingCache()
    cache.put("mock", 384, "q", [1.0])
    assert cache.get("other", 384, "q") is None
    assert cache.get("mock", 128, "q") is None


def test_cache_evicts_least_recently_used() -> None:
    cache = EmbeddingCache(max_size=2)
    cache.put("m", 8, "a", [1.0])
    cache.put("m", 8, "b", [2.0])
    cache.get("m", 8, "a")  # touch a -> b is now LRU
    cache.put("m", 8, "c", [3.0])  # evicts b
    assert cache.get("m", 8, "b") is None
    assert cache.get("m", 8, "a") == [1.0]
    assert cache.get("m", 8, "c") == [3.0]
