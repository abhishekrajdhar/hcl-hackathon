from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.resource import Resource, ResourcePrerequisite, ResourceSkill
from app.models.skill import Skill
from app.repositories.base import BaseRepository


class ResourceRepository(BaseRepository[Resource]):
    model = Resource

    def _base_select(self) -> Select[tuple[Resource]]:
        # Both nested collections are serialised in every resource response, so
        # eager-load them; a lazy load during serialisation raises on the async
        # session.
        return select(Resource).options(
            selectinload(Resource.skills)
            .joinedload(ResourceSkill.skill)
            .joinedload(Skill.category),
            selectinload(Resource.prerequisites)
            .joinedload(ResourcePrerequisite.skill)
            .joinedload(Skill.category),
        )

    @staticmethod
    def search_filter(term: str) -> Any:
        pattern = f"%{term}%"
        return or_(Resource.title.ilike(pattern), Resource.description.ilike(pattern))

    @staticmethod
    def teaches_skill_filter(skill_id: uuid.UUID) -> Any:
        return Resource.id.in_(
            select(ResourceSkill.resource_id).where(ResourceSkill.skill_id == skill_id)
        )

    async def semantic_search(
        self,
        embedding: list[float],
        *,
        top_k: int,
        filters: Sequence[Any] = (),
    ) -> list[tuple[Resource, float]]:
        """Cosine nearest-neighbour search over stored embeddings.

        Uses pgvector's `<=>` (cosine distance) operator; only rows that have an
        embedding are considered. Returns (resource, distance) ordered nearest
        first. Similarity is 1 - distance for these L2-normalised vectors.
        """
        distance = Resource.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            self._base_select()
            .add_columns(distance)
            .where(Resource.embedding.isnot(None), *filters)
            .order_by(distance)
            .limit(top_k)
        )
        rows = (await self.session.execute(stmt)).unique().all()
        return [(row[0], float(row[1])) for row in rows]

    async def list_missing_embeddings(self, *, limit: int, offset: int = 0) -> list[Resource]:
        stmt = (
            self._base_select()
            .where(Resource.embedding.is_(None))
            .order_by(Resource.created_at)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def count_missing_embeddings(self) -> int:
        return await self.count([Resource.embedding.is_(None)])

    async def get_many(self, resource_ids: Sequence[uuid.UUID]) -> list[Resource]:
        if not resource_ids:
            return []
        stmt = self._base_select().where(Resource.id.in_(list(resource_ids)))
        return list((await self.session.execute(stmt)).scalars().unique().all())


class ResourceSkillRepository(BaseRepository[ResourceSkill]):
    model = ResourceSkill

    def _base_select(self) -> Select[tuple[ResourceSkill]]:
        return select(ResourceSkill).options(
            joinedload(ResourceSkill.skill).joinedload(Skill.category)
        )

    async def get_link(self, resource_id: uuid.UUID, skill_id: uuid.UUID) -> ResourceSkill | None:
        stmt = self._base_select().where(
            ResourceSkill.resource_id == resource_id, ResourceSkill.skill_id == skill_id
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def list_for_resource(self, resource_id: uuid.UUID) -> list[ResourceSkill]:
        stmt = self._base_select().where(ResourceSkill.resource_id == resource_id)
        return list((await self.session.execute(stmt)).scalars().unique().all())



class ResourcePrerequisiteRepository(BaseRepository[ResourcePrerequisite]):
    model = ResourcePrerequisite

    def _base_select(self) -> Select[tuple[ResourcePrerequisite]]:
        return select(ResourcePrerequisite).options(
            joinedload(ResourcePrerequisite.skill).joinedload(Skill.category)
        )

    async def get_link(
        self, resource_id: uuid.UUID, skill_id: uuid.UUID
    ) -> ResourcePrerequisite | None:
        stmt = self._base_select().where(
            ResourcePrerequisite.resource_id == resource_id,
            ResourcePrerequisite.skill_id == skill_id,
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def list_for_resource(self, resource_id: uuid.UUID) -> list[ResourcePrerequisite]:
        stmt = self._base_select().where(ResourcePrerequisite.resource_id == resource_id)
        return list((await self.session.execute(stmt)).scalars().unique().all())

