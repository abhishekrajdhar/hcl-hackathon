from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import AdminUser, CurrentUser, PaginationDep, SessionDep
from app.models.enums import ResourceType
from app.schemas.common import Page
from app.schemas.resource import (
    ResourceCreate,
    ResourcePrerequisiteCreate,
    ResourcePrerequisiteRead,
    ResourceRead,
    ResourceSkillCreate,
    ResourceSkillRead,
    ResourceSkillUpdate,
    ResourceUpdate,
)
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=Page[ResourceRead])
async def list_resources(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    search: str | None = Query(default=None, min_length=1, max_length=256),
    skill_id: uuid.UUID | None = Query(default=None, description="Filter by taught skill"),
    resource_type: ResourceType | None = Query(default=None),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    min_difficulty: int | None = Query(default=None, ge=1, le=5),
    max_difficulty: int | None = Query(default=None, ge=1, le=5),
    min_hours: float | None = Query(default=None, ge=0, description="Min estimated hours"),
    max_hours: float | None = Query(default=None, ge=0, description="Max estimated hours"),
    min_quality: float | None = Query(default=None, ge=0, le=1),
    provider: str | None = None,
    language: str | None = None,
    is_active: bool | None = True,
) -> Page[ResourceRead]:
    items, total = await ResourceService(session).list(
        limit=pagination.limit,
        offset=pagination.offset,
        search=search,
        skill_id=skill_id,
        resource_type=resource_type,
        difficulty=difficulty,
        min_difficulty=min_difficulty,
        max_difficulty=max_difficulty,
        min_hours=min_hours,
        max_hours=max_hours,
        min_quality=min_quality,
        provider=provider,
        language=language,
        is_active=is_active,
    )
    return Page[ResourceRead](
        items=[ResourceRead.model_validate(r) for r in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
async def create_resource(
    payload: ResourceCreate, session: SessionDep, _: AdminUser
) -> ResourceRead:
    return ResourceRead.model_validate(await ResourceService(session).create(payload))


@router.get("/{resource_id}", response_model=ResourceRead)
async def get_resource(
    resource_id: uuid.UUID, session: SessionDep, _: CurrentUser
) -> ResourceRead:
    return ResourceRead.model_validate(await ResourceService(session).get(resource_id))


@router.put(
    "/{resource_id}",
    response_model=ResourceRead,
    summary="Update a resource (replaces skills/prerequisites when supplied)",
)
async def update_resource(
    resource_id: uuid.UUID, payload: ResourceUpdate, session: SessionDep, _: AdminUser
) -> ResourceRead:
    return ResourceRead.model_validate(
        await ResourceService(session).update(resource_id, payload)
    )


# PATCH kept as an alias of PUT for partial scalar updates.
@router.patch("/{resource_id}", response_model=ResourceRead, include_in_schema=False)
async def patch_resource(
    resource_id: uuid.UUID, payload: ResourceUpdate, session: SessionDep, _: AdminUser
) -> ResourceRead:
    return ResourceRead.model_validate(
        await ResourceService(session).update(resource_id, payload)
    )


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_resource(resource_id: uuid.UUID, session: SessionDep, _: AdminUser) -> None:
    await ResourceService(session).delete(resource_id)


# --- taught skills ---------------------------------------------------------
@router.get("/{resource_id}/skills", response_model=list[ResourceSkillRead])
async def list_resource_skills(
    resource_id: uuid.UUID, session: SessionDep, _: CurrentUser
) -> list[ResourceSkillRead]:
    links = await ResourceService(session).list_skills(resource_id)
    return [ResourceSkillRead.model_validate(link) for link in links]


@router.post(
    "/{resource_id}/skills", response_model=ResourceSkillRead, status_code=status.HTTP_201_CREATED
)
async def add_resource_skill(
    resource_id: uuid.UUID, payload: ResourceSkillCreate, session: SessionDep, _: AdminUser
) -> ResourceSkillRead:
    link = await ResourceService(session).add_skill(resource_id, payload)
    return ResourceSkillRead.model_validate(link)


@router.put("/{resource_id}/skills/{skill_id}", response_model=ResourceSkillRead)
async def update_resource_skill(
    resource_id: uuid.UUID,
    skill_id: uuid.UUID,
    payload: ResourceSkillUpdate,
    session: SessionDep,
    _: AdminUser,
) -> ResourceSkillRead:
    link = await ResourceService(session).update_skill(resource_id, skill_id, payload)
    return ResourceSkillRead.model_validate(link)


@router.delete(
    "/{resource_id}/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def remove_resource_skill(
    resource_id: uuid.UUID, skill_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> None:
    await ResourceService(session).remove_skill(resource_id, skill_id)


# --- prerequisites ---------------------------------------------------------
@router.get("/{resource_id}/prerequisites", response_model=list[ResourcePrerequisiteRead])
async def list_resource_prerequisites(
    resource_id: uuid.UUID, session: SessionDep, _: CurrentUser
) -> list[ResourcePrerequisiteRead]:
    links = await ResourceService(session).list_prerequisites(resource_id)
    return [ResourcePrerequisiteRead.model_validate(link) for link in links]


@router.post(
    "/{resource_id}/prerequisites",
    response_model=ResourcePrerequisiteRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_resource_prerequisite(
    resource_id: uuid.UUID,
    payload: ResourcePrerequisiteCreate,
    session: SessionDep,
    _: AdminUser,
) -> ResourcePrerequisiteRead:
    link = await ResourceService(session).add_prerequisite(resource_id, payload)
    return ResourcePrerequisiteRead.model_validate(link)


@router.delete(
    "/{resource_id}/prerequisites/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def remove_resource_prerequisite(
    resource_id: uuid.UUID, skill_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> None:
    await ResourceService(session).remove_prerequisite(resource_id, skill_id)
