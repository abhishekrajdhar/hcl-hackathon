from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, PaginationDep, SessionDep
from app.schemas.common import Page
from app.schemas.skill import UserSkillCreate, UserSkillRead, UserSkillUpdate
from app.services.user_skill_service import UserSkillService

router = APIRouter(prefix="/me/skills", tags=["learner-skills"])


@router.get("", response_model=Page[UserSkillRead])
async def list_my_skills(
    session: SessionDep, pagination: PaginationDep, current_user: CurrentUser
) -> Page[UserSkillRead]:
    items, total = await UserSkillService(session).list_for_user(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[UserSkillRead](
        items=[UserSkillRead.model_validate(i) for i in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=UserSkillRead, status_code=status.HTTP_201_CREATED)
async def add_my_skill(
    payload: UserSkillCreate, session: SessionDep, current_user: CurrentUser
) -> UserSkillRead:
    entry = await UserSkillService(session).add(current_user.id, payload)
    return UserSkillRead.model_validate(entry)


@router.put("", response_model=UserSkillRead, summary="Create or update a skill entry")
async def upsert_my_skill(
    payload: UserSkillCreate, session: SessionDep, current_user: CurrentUser
) -> UserSkillRead:
    entry = await UserSkillService(session).upsert(current_user.id, payload)
    return UserSkillRead.model_validate(entry)


@router.get("/{skill_id}", response_model=UserSkillRead)
async def get_my_skill(
    skill_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> UserSkillRead:
    entry = await UserSkillService(session).get(current_user.id, skill_id)
    return UserSkillRead.model_validate(entry)


@router.patch("/{skill_id}", response_model=UserSkillRead)
async def update_my_skill(
    skill_id: uuid.UUID,
    payload: UserSkillUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> UserSkillRead:
    entry = await UserSkillService(session).update(current_user.id, skill_id, payload)
    return UserSkillRead.model_validate(entry)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_my_skill(
    skill_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    await UserSkillService(session).delete(current_user.id, skill_id)
