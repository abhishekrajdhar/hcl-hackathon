from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.resource import Resource, ResourceSkill
from app.repositories.base import BaseRepository


class ResourceRepository(BaseRepository[Resource]):
    model = Resource

    def _base_select(self) -> Select[tuple[Resource]]:
        return select(Resource).options(
            selectinload(Resource.skills).joinedload(ResourceSkill.skill)
        )

    @staticmethod
    def search_filter(term: str) -> Any:
        pattern = f"%{term}%"
        return or_(Resource.title.ilike(pattern), Resource.description.ilike(pattern))

    async def list_by_skill(
        self, skill_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Resource]:
        stmt = (
            self._base_select()
            .join(ResourceSkill, ResourceSkill.resource_id == Resource.id)
            .where(ResourceSkill.skill_id == skill_id, Resource.is_active.is_(True))
            .order_by(Resource.rating.desc().nullslast(), Resource.id)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def get_many(self, resource_ids: Sequence[uuid.UUID]) -> list[Resource]:
        if not resource_ids:
            return []
        stmt = self._base_select().where(Resource.id.in_(list(resource_ids)))
        return list((await self.session.execute(stmt)).scalars().unique().all())


class ResourceSkillRepository(BaseRepository[ResourceSkill]):
    model = ResourceSkill

    async def get_link(self, resource_id: uuid.UUID, skill_id: uuid.UUID) -> ResourceSkill | None:
        return await self.get_by(resource_id=resource_id, skill_id=skill_id)

    async def list_for_resource(self, resource_id: uuid.UUID) -> list[ResourceSkill]:
        stmt = (
            select(ResourceSkill)
            .options(joinedload(ResourceSkill.skill))
            .where(ResourceSkill.resource_id == resource_id)
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())
