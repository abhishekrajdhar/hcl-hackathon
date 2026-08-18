from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, PaginationDep, SessionDep
from app.models.enums import GoalStatus
from app.schemas.common import Page
from app.schemas.goal import (
    GoalSkillCreate,
    GoalSkillRead,
    GoalSkillUpdate,
    LearningGoalCreate,
    LearningGoalRead,
    LearningGoalUpdate,
)
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["learning-goals"])


@router.get("", response_model=Page[LearningGoalRead])
async def list_goals(
    session: SessionDep,
    pagination: PaginationDep,
    current_user: CurrentUser,
    status_filter: GoalStatus | None = None,
) -> Page[LearningGoalRead]:
    items, total = await GoalService(session).list_for_user(
        current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        status=status_filter.value if status_filter else None,
    )
    return Page[LearningGoalRead](
        items=[LearningGoalRead.model_validate(g) for g in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=LearningGoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: LearningGoalCreate, session: SessionDep, current_user: CurrentUser
) -> LearningGoalRead:
    goal = await GoalService(session).create(current_user.id, payload)
    return LearningGoalRead.model_validate(goal)


@router.get("/{goal_id}", response_model=LearningGoalRead)
async def get_goal(
    goal_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> LearningGoalRead:
    goal = await GoalService(session).get_owned(goal_id, current_user.id)
    return LearningGoalRead.model_validate(goal)


@router.patch("/{goal_id}", response_model=LearningGoalRead)
async def update_goal(
    goal_id: uuid.UUID,
    payload: LearningGoalUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> LearningGoalRead:
    goal = await GoalService(session).update(goal_id, current_user.id, payload)
    return LearningGoalRead.model_validate(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_goal(goal_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> None:
    await GoalService(session).delete(goal_id, current_user.id)


# --- target skill vector ---------------------------------------------------
@router.post(
    "/{goal_id}/skills",
    response_model=GoalSkillRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a skill to the goal's target vector",
)
async def add_target_skill(
    goal_id: uuid.UUID,
    payload: GoalSkillCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> GoalSkillRead:
    entry = await GoalService(session).add_target_skill(goal_id, current_user.id, payload)
    return GoalSkillRead.model_validate(entry)


@router.patch("/{goal_id}/skills/{skill_id}", response_model=GoalSkillRead)
async def update_target_skill(
    goal_id: uuid.UUID,
    skill_id: uuid.UUID,
    payload: GoalSkillUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> GoalSkillRead:
    entry = await GoalService(session).update_target_skill(
        goal_id, skill_id, current_user.id, payload
    )
    return GoalSkillRead.model_validate(entry)


@router.delete("/{goal_id}/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_target_skill(
    goal_id: uuid.UUID, skill_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    await GoalService(session).remove_target_skill(goal_id, skill_id, current_user.id)
