"""Provider-agnostic embedding transport.

`EmbeddingProvider` is the swappable seam: Sentence Transformers in production,
a dependency-free mock everywhere else. Providers turn text into fixed-width
unit vectors and know nothing about resources or the database. Similarity is
computed by pgvector, never here and never by an LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Provider transport/loading failure (missing model, missing dependency)."""


class EmbeddingProvider(ABC):
    name: str = "abstract"

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector width. Must equal the pgvector column dimension."""
        raise NotImplementedError

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch. Returns one L2-normalised vector per input, in order."""
        raise NotImplementedError

    async def embed_text(self, text: str) -> list[float]:
        (vector,) = await self.embed_texts([text])
        return vector
