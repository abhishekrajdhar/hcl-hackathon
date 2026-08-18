"""Deterministic, dependency-free embedding provider.

Uses signed feature hashing over word tokens: every token is hashed to a
dimension and a sign, contributions are summed and the vector is L2-normalised.
This is not a neural embedding, but it is fully deterministic and — crucially —
its cosine similarity reflects real token overlap, so semantic-retrieval tests
are meaningful (a query about "deep learning" ranks deep-learning resources
first) without pulling in torch. Same text always yields the same vector.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.core.config import settings
from app.embeddings.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class MockEmbeddingProvider(EmbeddingProvider):
    name = "mock"

    def __init__(self, dimension: int | None = None) -> None:
        self._dimension = dimension or settings.EMBEDDING_DIM

    @property
    def dimension(self) -> int:
        return self._dimension

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dimension
        for token in _tokenize(text):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[index] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec  # empty/no-token text -> zero vector
        return [v / norm for v in vec]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]
