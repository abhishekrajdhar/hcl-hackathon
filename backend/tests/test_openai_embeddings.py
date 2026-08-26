"""Unit tests for the OpenAI embedding provider.

No network and no key: a stub client stands in for the SDK, so the batching,
ordering and normalisation logic is verified on its own.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.embeddings.base import EmbeddingError
from app.embeddings.providers.openai import OpenAIEmbeddingProvider


class _StubEmbeddings:
    def __init__(self, recorder: list[dict]) -> None:
        self._recorder = recorder

    async def create(self, *, model: str, input: list[str], dimensions: int):  # noqa: A002
        self._recorder.append({"model": model, "input": input, "dimensions": dimensions})
        # Returned deliberately OUT OF ORDER to prove the provider sorts by index.
        data = [
            SimpleNamespace(index=i, embedding=[float(i + 1)] * dimensions)
            for i in range(len(input))
        ]
        return SimpleNamespace(data=list(reversed(data)))


class _StubClient:
    def __init__(self, recorder: list[dict]) -> None:
        self.embeddings = _StubEmbeddings(recorder)


def _provider(recorder: list[dict], **kwargs) -> OpenAIEmbeddingProvider:
    p = OpenAIEmbeddingProvider(api_key="sk-test", **kwargs)
    p._client = lambda: _StubClient(recorder)  # type: ignore[method-assign]
    return p


async def test_requests_the_configured_width_so_no_migration_is_needed() -> None:
    calls: list[dict] = []
    provider = _provider(calls, dimension=384)
    vectors = await provider.embed_texts(["hello"])
    assert calls[0]["dimensions"] == 384
    assert len(vectors[0]) == 384
    assert provider.dimension == 384


async def test_vectors_are_l2_normalised() -> None:
    vectors = await _provider([]).embed_texts(["a", "b"])
    for v in vectors:
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-9)


async def test_results_are_returned_in_input_order() -> None:
    # The stub answers in reverse; index ordering must still be honoured.
    vectors = await _provider([]).embed_texts(["first", "second", "third"])
    firsts = [round(v[0], 6) for v in vectors]
    assert firsts == sorted(firsts), "embeddings must line up with their inputs"


async def test_batches_respect_the_configured_size() -> None:
    calls: list[dict] = []
    from app.core.config import settings

    provider = _provider(calls)
    await provider.embed_texts([f"text-{i}" for i in range(settings.EMBEDDING_BATCH_SIZE + 3)])
    assert len(calls) == 2, "a batch larger than the limit must be split"


async def test_blank_input_keeps_positions_stable() -> None:
    calls: list[dict] = []
    vectors = await _provider(calls).embed_texts(["real text", "   "])
    assert calls[0]["input"][1] == " ", "empty strings are substituted, not dropped"
    assert len(vectors) == 2


async def test_empty_batch_makes_no_request() -> None:
    calls: list[dict] = []
    assert await _provider(calls).embed_texts([]) == []
    assert calls == []


async def test_missing_key_is_a_clear_error_not_a_crash() -> None:
    provider = OpenAIEmbeddingProvider(api_key=None)
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        await provider.embed_texts(["x"])


async def test_transport_failure_surfaces_as_embedding_error() -> None:
    provider = OpenAIEmbeddingProvider(api_key="sk-test")

    class _Boom:
        class embeddings:  # noqa: N801
            @staticmethod
            async def create(**_kwargs):
                raise RuntimeError("connection reset")

    provider._client = lambda: _Boom()  # type: ignore[method-assign]
    with pytest.raises(EmbeddingError, match="OpenAI embedding request failed"):
        await provider.embed_texts(["x"])
