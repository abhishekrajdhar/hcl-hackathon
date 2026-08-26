"""OpenAI embedding provider — real semantic vectors.

The mock provider hashes tokens, so its similarity only reflects word overlap:
"Backpropagation" and "How neural networks learn" look unrelated to it. This
one embeds meaning, which is what the retrieval half of the recommender is
supposed to be doing.

Width is requested, not assumed. `text-embedding-3-*` accepts a `dimensions`
parameter, so we ask for exactly EMBEDDING_DIM (384 by default) and the vectors
drop straight into the existing pgvector column — no migration, and switching
providers stays a config change.

Works against any OpenAI-compatible endpoint via OPENAI_BASE_URL. The SDK is
imported lazily so the backend still boots without it.
"""

from __future__ import annotations

import math
from typing import Any

from app.core.config import settings
from app.embeddings.base import EmbeddingError, EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.OPENAI_EMBEDDING_MODEL
        self._base_url = base_url or settings.OPENAI_BASE_URL
        self._dimension = dimension or settings.EMBEDDING_DIM

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model(self) -> str:
        return self._model

    def _client(self) -> Any:
        if not self._api_key:
            raise EmbeddingError(
                "OPENAI_API_KEY is not set; configure it or use EMBEDDING_PROVIDER=mock"
            )
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise EmbeddingError(
                "The 'openai' package is not installed; add it or use "
                "EMBEDDING_PROVIDER=mock"
            ) from exc
        return openai.AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # The API rejects empty strings; keep positions stable by substituting a
        # single space and letting the result be a near-zero-information vector
        # rather than dropping the row and misaligning the batch.
        cleaned = [t.strip() or " " for t in texts]
        client = self._client()

        vectors: list[list[float]] = []
        batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
        for start in range(0, len(cleaned), batch_size):
            chunk = cleaned[start : start + batch_size]
            try:
                response = await client.embeddings.create(
                    model=self._model,
                    input=chunk,
                    dimensions=self._dimension,
                )
            except Exception as exc:  # noqa: BLE001 - any transport failure
                raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc

            # Order is not guaranteed by the response shape, so sort by index
            # rather than trusting arrival order.
            ordered = sorted(response.data, key=lambda d: d.index)
            if len(ordered) != len(chunk):
                raise EmbeddingError(
                    f"OpenAI returned {len(ordered)} embeddings for {len(chunk)} inputs"
                )
            vectors.extend(_normalise(list(d.embedding)) for d in ordered)

        return vectors


def _normalise(vector: list[float]) -> list[float]:
    """L2-normalise, as the interface promises.

    OpenAI already returns unit vectors, but asking for a reduced `dimensions`
    truncates before re-normalising, so this is not redundant — and pgvector's
    cosine distance assumes it.
    """
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]
