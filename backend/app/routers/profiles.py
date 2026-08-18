from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, SessionDep
from app.schemas.profile import (
    LearnerProfileCreate,
    LearnerProfileRead,
    LearnerProfileUpdate,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["learner-profile"])


@router.get("", response_model=LearnerProfileRead)
async def get_profile(session: SessionDep, current_user: CurrentUser) -> LearnerProfileRead:
    profile = await ProfileService(session).get_for_user(current_user.id)
    return LearnerProfileRead.model_validate(profile)


@router.post("", response_model=LearnerProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: LearnerProfileCreate, session: SessionDep, current_user: CurrentUser
) -> LearnerProfileRead:
    profile = await ProfileService(session).create_for_user(current_user.id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.put("", response_model=LearnerProfileRead, summary="Create or replace the profile")
async def upsert_profile(
    payload: LearnerProfileCreate, session: SessionDep, current_user: CurrentUser
) -> LearnerProfileRead:
    profile = await ProfileService(session).upsert_for_user(current_user.id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.patch("", response_model=LearnerProfileRead)
async def update_profile(
    payload: LearnerProfileUpdate, session: SessionDep, current_user: CurrentUser
) -> LearnerProfileRead:
    profile = await ProfileService(session).update_for_user(current_user.id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_profile(session: SessionDep, current_user: CurrentUser) -> None:
    await ProfileService(session).delete_for_user(current_user.id)
