"""Sentence Transformers embedding provider.

`sentence-transformers` (and its torch dependency) is heavy, so it is imported
lazily and the model is loaded once on first use. Encoding is CPU-bound and
synchronous, so it runs in a worker thread to avoid blocking the event loop.
Vectors are L2-normalised at encode time so pgvector cosine distance is exact.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings
from app.embeddings.base import EmbeddingError, EmbeddingProvider


class SentenceTransformerProvider(EmbeddingProvider):
    name = "sentence_transformer"

    def __init__(self, model_name: str | None = None, dimension: int | None = None) -> None:
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._dimension = dimension or settings.EMBEDDING_DIM
        self._model: Any | None = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional heavy dep
            raise EmbeddingError(
                "sentence-transformers is not installed; install it or set "
                "EMBEDDING_PROVIDER=mock"
            ) from exc
        try:
            model = SentenceTransformer(self._model_name)
        except Exception as exc:  # pragma: no cover - model download/load failure
            raise EmbeddingError(f"could not load embedding model '{self._model_name}': {exc}") from exc

        actual = int(model.get_sentence_embedding_dimension())
        if actual != self._dimension:
            raise EmbeddingError(
                f"model '{self._model_name}' produces {actual}-d vectors but "
                f"EMBEDDING_DIM is {self._dimension}"
            )
        self._model = model
        return model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(
            texts,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [v.tolist() for v in vectors]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._encode, texts)
