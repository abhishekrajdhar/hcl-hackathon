"""Learning resource catalogue: CRUD, filtering, taught-skills and prerequisites.

Kept provider-agnostic on purpose — the same code path serves today's seeded
mock rows and a future ingested catalogue. All validation is deterministic; no
model is involved.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.enums import ResourceType
from app.models.resource import Resource, ResourcePrerequisite, ResourceSkill
from app.repositories.resource import (
    ResourcePrerequisiteRepository,
    ResourceRepository,
    ResourceSkillRepository,
)
from app.repositories.skill import SkillRepository
from app.schemas.resource import (
    ResourceCreate,
    ResourcePrerequisiteCreate,
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
        self.resource_prereqs = ResourcePrerequisiteRepository(session)
        self.skills = SkillRepository(session)

    # --- read ------------------------------------------------------------
    async def get(self, resource_id: uuid.UUID) -> Resource:
        """Load a resource with skills and prerequisites eagerly attached."""
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
        difficulty: int | None = None,
        min_difficulty: int | None = None,
        max_difficulty: int | None = None,
        min_hours: float | None = None,
        max_hours: float | None = None,
        min_quality: float | None = None,
        skill_id: uuid.UUID | None = None,
        is_active: bool | None = True,
    ) -> tuple[list[Resource], int]:
        filters: list[Any] = []
        if search:
            filters.append(ResourceRepository.search_filter(search))
        if resource_type:
            filters.append(Resource.resource_type == resource_type)
        if provider:
            filters.append(Resource.provider == provider)
        if language:
            filters.append(Resource.language == language)
        if difficulty is not None:
            filters.append(Resource.difficulty == difficulty)
        if min_difficulty is not None:
            filters.append(Resource.difficulty >= min_difficulty)
        if max_difficulty is not None:
            filters.append(Resource.difficulty <= max_difficulty)
        if min_hours is not None:
            filters.append(Resource.estimated_hours >= min_hours)
        if max_hours is not None:
            filters.append(Resource.estimated_hours <= max_hours)
        if min_quality is not None:
            filters.append(Resource.quality_score >= min_quality)
        if is_active is not None:
            filters.append(Resource.is_active.is_(is_active))
        if skill_id is not None:
            filters.append(ResourceRepository.teaches_skill_filter(skill_id))

        items = await self.resources.list(
            limit=limit,
            offset=offset,
            filters=filters,
            # Best quality first (nulls last), then newest.
            order_by=(Resource.quality_score.desc().nullslast(), Resource.created_at.desc()),
        )
        total = await self.resources.count(filters)
        return items, total

    # --- create ----------------------------------------------------------
    async def create(self, payload: ResourceCreate) -> Resource:
        data = payload.model_dump(exclude={"skills", "prerequisites"})
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

        # Validate links first, then build the object graph on a transient
        # instance so its collections are set before the first flush — appending
        # to a relationship on an already-flushed object would lazy-load it and
        # raise MissingGreenlet on the async session.
        skills = await self._build_skills(payload.skills)
        prerequisites = await self._build_prerequisites(payload.prerequisites)
        resource = Resource(**data, skills=skills, prerequisites=prerequisites)
        self.resources.add(resource)
        await self.session.flush()
        await self.commit()
        return await self.get(resource.id)

    # --- update / replace ------------------------------------------------
    async def update(self, resource_id: uuid.UUID, payload: ResourceUpdate) -> Resource:
        resource = await self.get(resource_id)
        data = payload.model_dump(exclude={"skills", "prerequisites"}, exclude_unset=True)
        if "url" in data and data["url"] is not None:
            data["url"] = str(data["url"])
        if data:
            await self.resources.update(resource, data)

        # On PUT, an explicitly-supplied collection replaces the existing one.
        # Mutating through the relationship lets delete-orphan remove the old
        # rows cleanly (a separate DELETE conflicts with the loaded collection).
        if payload.skills is not None:
            new_skills = await self._build_skills(payload.skills)
            resource.skills.clear()
            await self.session.flush()  # let delete-orphan remove the old rows
            resource.skills.extend(new_skills)
        if payload.prerequisites is not None:
            new_prereqs = await self._build_prerequisites(payload.prerequisites)
            resource.prerequisites.clear()
            await self.session.flush()
            resource.prerequisites.extend(new_prereqs)

        await self.session.flush()
        await self.commit()
        return await self.get(resource_id)

    async def delete(self, resource_id: uuid.UUID) -> None:
        resource = await self.get(resource_id)
        await self.resources.delete(resource)
        await self.commit()

    # --- taught skills ----------------------------------------------------
    async def _validate_skill_link(self, link: ResourceSkillCreate) -> None:
        if link.teaches_level_to <= link.teaches_level_from:
            raise ValidationError(
                "teaches_level_to must be greater than teaches_level_from",
                error_code="invalid_level_band",
            )
        if await self.skills.get(link.skill_id) is None:
            raise NotFoundError("Skill", link.skill_id)

    async def _build_skills(self, links: list[ResourceSkillCreate]) -> list[ResourceSkill]:
        seen: set[uuid.UUID] = set()
        built: list[ResourceSkill] = []
        for link in links:
            if link.skill_id in seen:
                raise ValidationError(
                    "Duplicate skill in resource skills", error_code="duplicate_skill"
                )
            seen.add(link.skill_id)
            await self._validate_skill_link(link)
            built.append(ResourceSkill(**link.model_dump()))
        return built

    async def add_skill(
        self, resource_id: uuid.UUID, payload: ResourceSkillCreate
    ) -> ResourceSkill:
        await self.get(resource_id)
        await self._validate_skill_link(payload)
        if await self.resource_skills.get_link(resource_id, payload.skill_id) is not None:
            raise ConflictError(
                "This skill is already linked to the resource", error_code="resource_skill_exists"
            )
        self.resource_skills.add(ResourceSkill(resource_id=resource_id, **payload.model_dump()))
        await self.session.flush()
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

    # --- prerequisites ----------------------------------------------------
    async def _build_prerequisites(
        self, links: list[ResourcePrerequisiteCreate]
    ) -> list[ResourcePrerequisite]:
        seen: set[uuid.UUID] = set()
        built: list[ResourcePrerequisite] = []
        for link in links:
            if link.skill_id in seen:
                raise ValidationError(
                    "Duplicate skill in resource prerequisites",
                    error_code="duplicate_prerequisite",
                )
            seen.add(link.skill_id)
            if await self.skills.get(link.skill_id) is None:
                raise NotFoundError("Skill", link.skill_id)
            built.append(ResourcePrerequisite(**link.model_dump()))
        return built

    async def add_prerequisite(
        self, resource_id: uuid.UUID, payload: ResourcePrerequisiteCreate
    ) -> ResourcePrerequisite:
        await self.get(resource_id)
        if await self.skills.get(payload.skill_id) is None:
            raise NotFoundError("Skill", payload.skill_id)
        if await self.resource_prereqs.get_link(resource_id, payload.skill_id) is not None:
            raise ConflictError(
                "This skill is already a prerequisite of the resource",
                error_code="resource_prerequisite_exists",
            )
        self.resource_prereqs.add(
            ResourcePrerequisite(resource_id=resource_id, **payload.model_dump())
        )
        await self.session.flush()
        await self.commit()
        link = await self.resource_prereqs.get_link(resource_id, payload.skill_id)
        assert link is not None
        return link

    async def remove_prerequisite(self, resource_id: uuid.UUID, skill_id: uuid.UUID) -> None:
        link = await self.resource_prereqs.get_link(resource_id, skill_id)
        if link is None:
            raise NotFoundError("Resource prerequisite link", skill_id)
        await self.resource_prereqs.delete(link)
        await self.commit()

    async def list_prerequisites(self, resource_id: uuid.UUID) -> list[ResourcePrerequisite]:
        await self.get(resource_id)
        return await self.resource_prereqs.list_for_resource(resource_id)
