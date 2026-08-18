from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.enums import ResourceType
from app.models.resource import Resource, ResourceSkill
from app.repositories.resource import ResourceRepository, ResourceSkillRepository
from app.repositories.skill import SkillRepository
from app.schemas.resource import (
    ResourceCreate,
    ResourceSkillCreate,
    ResourceSkillUpdate,
    ResourceUpdate,
)
from app.services.base import BaseService


class ResourceService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.resources = ResourceRepository(session)
        self.resource_skills = ResourceSkillRepository(session)
        self.skills = SkillRepository(session)

    async def get(self, resource_id: uuid.UUID) -> Resource:
        """Loads the resource with its skill links eagerly attached."""
        results = await self.resources.list(limit=1, filters=[Resource.id == resource_id])
        if not results:
            raise NotFoundError("Resource", resource_id)
        return results[0]

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        resource_type: ResourceType | None = None,
        provider: str | None = None,
        language: str | None = None,
        max_difficulty: int | None = None,
        is_active: bool | None = True,
        skill_id: uuid.UUID | None = None,
    ) -> tuple[list[Resource], int]:
        filters: list[Any] = []
        if search:
            filters.append(ResourceRepository.search_filter(search))
        if resource_type:
            filters.append(Resource.type == resource_type)
        if provider:
            filters.append(Resource.provider == provider)
        if language:
            filters.append(Resource.language == language)
        if max_difficulty is not None:
            filters.append(Resource.difficulty <= max_difficulty)
        if is_active is not None:
            filters.append(Resource.is_active.is_(is_active))
        if skill_id is not None:
            filters.append(
                Resource.id.in_(
                    select(ResourceSkill.resource_id).where(ResourceSkill.skill_id == skill_id)
                )
            )

        items = await self.resources.list(
            limit=limit, offset=offset, filters=filters, order_by=(Resource.created_at.desc(),)
        )
        total = await self.resources.count(filters)
        return items, total

    async def create(self, payload: ResourceCreate) -> Resource:
        data = payload.model_dump(exclude={"skills"})
        data["url"] = str(data["url"])

        if data.get("external_id"):
            duplicate = await self.resources.get_by(
                provider=data["provider"], external_id=data["external_id"]
            )
            if duplicate is not None:
                raise ConflictError(
                    "A resource with this provider/external_id already exists",
                    error_code="resource_exists",
                )

        resource = await self.resources.create(data)
        for link in payload.skills:
            await self._validate_link(link)
            self.resource_skills.add(ResourceSkill(resource_id=resource.id, **link.model_dump()))
        await self.session.flush()
        await self.commit()
        return await self.get(resource.id)

    async def update(self, resource_id: uuid.UUID, payload: ResourceUpdate) -> Resource:
        resource = await self.get(resource_id)
        data = payload.model_dump(exclude_unset=True)
        if "url" in data and data["url"] is not None:
            data["url"] = str(data["url"])
        await self.resources.update(resource, data)
        await self.commit()
        return await self.get(resource_id)

    async def delete(self, resource_id: uuid.UUID) -> None:
        resource = await self.get(resource_id)
        await self.resources.delete(resource)
        await self.commit()

    # --- taught skills ----------------------------------------------------
    async def _validate_link(self, link: ResourceSkillCreate) -> None:
        if link.teaches_level_to <= link.teaches_level_from:
            raise ValidationError(
                "teaches_level_to must be greater than teaches_level_from",
                error_code="invalid_level_band",
            )
        if await self.skills.get(link.skill_id) is None:
            raise NotFoundError("Skill", link.skill_id)

    async def add_skill(
        self, resource_id: uuid.UUID, payload: ResourceSkillCreate
    ) -> ResourceSkill:
        await self.get(resource_id)
        await self._validate_link(payload)
        if await self.resource_skills.get_link(resource_id, payload.skill_id) is not None:
            raise ConflictError(
                "This skill is already linked to the resource", error_code="resource_skill_exists"
            )
        await self.resource_skills.create({**payload.model_dump(), "resource_id": resource_id})
        await self.commit()
        link = await self.resource_skills.get_link(resource_id, payload.skill_id)
        assert link is not None
        return link

    async def update_skill(
        self, resource_id: uuid.UUID, skill_id: uuid.UUID, payload: ResourceSkillUpdate
    ) -> ResourceSkill:
        link = await self.resource_skills.get_link(resource_id, skill_id)
        if link is None:
            raise NotFoundError("Resource skill link", skill_id)
        data = payload.model_dump(exclude_unset=True)
        new_from = data.get("teaches_level_from", link.teaches_level_from)
        new_to = data.get("teaches_level_to", link.teaches_level_to)
        if new_to <= new_from:
            raise ValidationError(
                "teaches_level_to must be greater than teaches_level_from",
                error_code="invalid_level_band",
            )
        await self.resource_skills.update(link, data)
        await self.commit()
        return link

    async def remove_skill(self, resource_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        link = await self.resource_skills.get_link(resource_id, skill_id)
        if link is None:
            raise NotFoundError("Resource skill link", skill_id)
        await self.resource_skills.delete(link)
        await self.commit()

    async def list_skills(self, resource_id: uuid.UUID) -> list[ResourceSkill]:
        await self.get(resource_id)
        return await self.resource_skills.list_for_resource(resource_id)
