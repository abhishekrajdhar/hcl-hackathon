"""Skill and category CRUD.

Graph traversal, sequencing and cycle prevention live in
`app.services.skill_graph_service`.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.skill import Skill, SkillCategory
from app.repositories.skill import SkillCategoryRepository, SkillRepository
from app.schemas.skill import (
    SkillCategoryCreate,
    SkillCategoryUpdate,
    SkillCreate,
    SkillUpdate,
)
from app.services.base import BaseService


class SkillCategoryService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.categories = SkillCategoryRepository(session)

    async def get(self, category_id: uuid.UUID) -> SkillCategory:
        category = await self.categories.get(category_id)
        if category is None:
            raise NotFoundError("Skill category", category_id)
        return category

    async def list(self) -> list[SkillCategory]:
        return await self.categories.list_ordered()

    async def create(self, payload: SkillCategoryCreate) -> SkillCategory:
        if await self.categories.get_by_slug(payload.slug) is not None:
            raise ConflictError(
                f"Category slug '{payload.slug}' is already taken", error_code="slug_taken"
            )
        category = await self.categories.create(payload.model_dump())
        await self.commit()
        return category

    async def update(
        self, category_id: uuid.UUID, payload: SkillCategoryUpdate
    ) -> SkillCategory:
        category = await self.get(category_id)
        await self.categories.update(category, payload.model_dump(exclude_unset=True))
        await self.commit()
        return category

    async def delete(self, category_id: uuid.UUID) -> None:
        category = await self.get(category_id)
        # skills.category_id is ON DELETE RESTRICT, so refuse clearly rather
        # than surfacing an IntegrityError.
        skill_count = await SkillRepository(self.session).count(
            [Skill.category_id == category_id]
        )
        if skill_count:
            raise ConflictError(
                f"Category still has {skill_count} skill(s); reassign them first",
                error_code="category_in_use",
            )
        await self.categories.delete(category)
        await self.commit()


class SkillService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.skills = SkillRepository(session)
        self.categories = SkillCategoryRepository(session)

    async def get(self, skill_id: uuid.UUID) -> Skill:
        skill = await self.skills.get(skill_id)
        if skill is None:
            raise NotFoundError("Skill", skill_id)
        return skill

    async def get_by_slug(self, slug: str) -> Skill:
        skill = await self.skills.get_by_slug(slug)
        if skill is None:
            raise NotFoundError("Skill", slug)
        return skill

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        domain: str | None = None,
        min_difficulty: int | None = None,
        max_difficulty: int | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Skill], int]:
        filters: list[Any] = []
        if search:
            filters.append(SkillRepository.search_filter(search))
        if category_id:
            filters.append(Skill.category_id == category_id)
        if category_slug:
            category = await self.categories.get_by_slug(category_slug)
            if category is None:
                raise NotFoundError("Skill category", category_slug)
            filters.append(Skill.category_id == category.id)
        if domain:
            filters.append(Skill.domain == domain)
        if min_difficulty is not None:
            filters.append(Skill.difficulty >= min_difficulty)
        if max_difficulty is not None:
            filters.append(Skill.difficulty <= max_difficulty)
        if is_active is not None:
            filters.append(Skill.is_active.is_(is_active))

        items = await self.skills.list(
            limit=limit,
            offset=offset,
            filters=filters,
            order_by=(Skill.difficulty, Skill.name),
        )
        total = await self.skills.count(filters)
        return items, total

    async def create(self, payload: SkillCreate) -> Skill:
        if await self.skills.get_by_slug(payload.slug) is not None:
            raise ConflictError(
                f"Skill slug '{payload.slug}' is already taken", error_code="slug_taken"
            )
        if await self.categories.get(payload.category_id) is None:
            raise NotFoundError("Skill category", payload.category_id)

        await self.skills.create(payload.model_dump())
        await self.commit()
        return await self.get_by_slug(payload.slug)

    async def update(self, skill_id: uuid.UUID, payload: SkillUpdate) -> Skill:
        skill = await self.get(skill_id)
        data = payload.model_dump(exclude_unset=True)
        if data.get("category_id") and await self.categories.get(data["category_id"]) is None:
            raise NotFoundError("Skill category", data["category_id"])
        await self.skills.update(skill, data)
        await self.commit()
        return await self.get(skill_id)

    async def delete(self, skill_id: uuid.UUID) -> None:
        skill = await self.get(skill_id)
        await self.skills.delete(skill)
        await self.commit()
