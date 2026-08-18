from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import AdminUser, CurrentUser, PaginationDep, SessionDep
from app.models.enums import ResourceType
from app.schemas.common import Page
from app.schemas.resource import (
    ResourceCreate,
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
    type: ResourceType | None = None,
    provider: str | None = None,
    language: str | None = None,
    max_difficulty: int | None = Query(default=None, ge=1, le=5),
    skill_id: uuid.UUID | None = None,
    is_active: bool | None = True,
) -> Page[ResourceRead]:
    items, total = await ResourceService(session).list(
        limit=pagination.limit,
        offset=pagination.offset,
        search=search,
        resource_type=type,
        provider=provider,
        language=language,
        max_difficulty=max_difficulty,
        is_active=is_active,
        skill_id=skill_id,
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


@router.patch("/{resource_id}", response_model=ResourceRead)
async def update_resource(
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


@router.patch("/{resource_id}/skills/{skill_id}", response_model=ResourceSkillRead)
async def update_resource_skill(
    resource_id: uuid.UUID,
    skill_id: uuid.UUID,
    payload: ResourceSkillUpdate,
    session: SessionDep,
    _: AdminUser,
) -> ResourceSkillRead:
    link = await ResourceService(session).update_skill(resource_id, skill_id, payload)
    return ResourceSkillRead.model_validate(link)


@router.delete("/{resource_id}/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_resource_skill(
    resource_id: uuid.UUID, skill_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> None:
    await ResourceService(session).remove_skill(resource_id, skill_id)
