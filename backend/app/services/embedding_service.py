"""Resource embedding generation and storage.

Builds a canonical text for a resource (title, description, taught skills,
prerequisites), embeds it through the configured provider, and stores the vector
in pgvector. The stored vectors ARE the durable embedding cache; query
embeddings are cached separately in-process. No similarity maths and no LLM here
— this module only produces and persists vectors.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.embeddings.base import EmbeddingProvider
from app.embeddings.cache import EmbeddingCache
from app.embeddings.text import canonical_resource_text
from app.models.resource import Resource
from app.repositories.resource import ResourceRepository
from app.services.base import BaseService

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EmbedResult:
    resource_id: uuid.UUID
    embedded: bool
    dimension: int
    text: str


@dataclass(frozen=True, slots=True)
class EmbedAllResult:
    embedded: int
    skipped: int
    total: int
    dimension: int


class EmbeddingService(BaseService):
    def __init__(
        self,
        session: AsyncSession,
        provider: EmbeddingProvider,
        cache: EmbeddingCache | None = None,
    ) -> None:
        super().__init__(session)
        self.provider = provider
        self.cache = cache
        self.resources = ResourceRepository(session)

    # --- canonical text --------------------------------------------------
    @staticmethod
    def canonical_text(resource: Resource) -> str:
        return canonical_resource_text(
            title=resource.title,
            description=resource.description,
            resource_type=resource.resource_type.value,
            taught_skill_names=[
                link.skill.name for link in resource.skills if link.skill is not None
            ],
            prerequisite_skill_names=[
                link.skill.name for link in resource.prerequisites if link.skill is not None
            ],
        )

    # --- single resource -------------------------------------------------
    async def embed_resource(self, resource_id: uuid.UUID) -> EmbedResult:
        resource = await self._get(resource_id)
        text = self.canonical_text(resource)
        vector = await self.provider.embed_text(text)
        resource.embedding = vector
        await self.session.flush()
        await self.commit()
        return EmbedResult(
            resource_id=resource.id, embedded=True, dimension=len(vector), text=text
        )

    async def _get(self, resource_id: uuid.UUID) -> Resource:
        results = await self.resources.list(limit=1, filters=[Resource.id == resource_id])
        if not results:
            raise NotFoundError("Resource", resource_id)
        return results[0]

    # --- bulk ------------------------------------------------------------
    async def embed_all(self, *, only_missing: bool = True, batch_size: int = 64) -> EmbedAllResult:
        """(Re)embed the catalogue in batches.

        `only_missing` re-embeds just resources without a vector — the common
        case after ingesting new rows. Set it false to re-embed everything (e.g.
        after changing the model).
        """
        filters = [Resource.embedding.is_(None)] if only_missing else []
        total = await self.resources.count(filters)
        embedded = 0
        offset = 0

        while True:
            batch = await self.resources.list(
                limit=batch_size,
                offset=0 if only_missing else offset,
                filters=filters,
                order_by=(Resource.created_at,),
            )
            if not batch:
                break

            texts = [self.canonical_text(r) for r in batch]
            vectors = await self.provider.embed_texts(texts)
            for resource, vector in zip(batch, vectors, strict=True):
                resource.embedding = vector
            embedded += len(batch)
            await self.session.flush()
            await self.commit()

            if only_missing:
                # Rows just got a vector, so the filtered set shrank; re-query
                # from the top rather than paging.
                continue
            offset += batch_size
            if offset >= total:
                break

        logger.info(
            "embedded resources",
            extra={"embedded": embedded, "only_missing": only_missing, "provider": self.provider.name},
        )
        return EmbedAllResult(
            embedded=embedded,
            skipped=0,
            total=total,
            dimension=self.provider.dimension,
        )

    # --- query embedding (cached) ----------------------------------------
    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query, served from the in-process cache when possible."""
        cleaned = " ".join(text.split())
        if self.cache is not None:
            cached = self.cache.get(self.provider.name, self.provider.dimension, cleaned)
            if cached is not None:
                return cached
        vector = await self.provider.embed_text(cleaned)
        if self.cache is not None:
            self.cache.put(self.provider.name, self.provider.dimension, cleaned, vector)
        return vector
