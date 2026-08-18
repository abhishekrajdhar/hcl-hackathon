"""Learner profile HTTP surface.

Two addressing styles share one service:
- `""`            — the authenticated learner's own profile (convenience).
- `/{user_id}`    — an explicit user; allowed for that user or an admin.

Routers stay thin: they authorize, delegate, and serialise. All profile logic
and every deterministic rule live in `ProfileService` and the profile engines.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, LLMProviderDep, SessionDep
from app.core.errors import ForbiddenError
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.extraction import ProfileExtractRequest, ProfileExtractResponse
from app.schemas.profile import (
    FullLearnerProfile,
    LearnerProfileCreate,
    LearnerProfileRead,
    LearnerProfileUpdate,
    ProfileDraftIngestRequest,
    ProfileDraftPreview,
    ProfileValidationRead,
    SkillProficiencyCreate,
    SkillProficiencyRead,
    SkillProficiencyUpdate,
)
from app.services.profile_extraction_service import ProfileExtractionService
from app.services.profile_ingest import default_extractor
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["learner-profile"])


def _authorize(user_id: uuid.UUID, current_user: User) -> None:
    """A learner may act only on their own profile; admins on any.

    Returns 404, not 403, when a non-admin targets someone else — we do not
    confirm whether that user exists.
    """
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError("You may only access your own profile")


# --- self-scoped (authenticated learner) -----------------------------------
@router.get("", response_model=LearnerProfileRead)
async def get_my_profile(session: SessionDep, current_user: CurrentUser) -> LearnerProfileRead:
    profile = await ProfileService(session).get_for_user(current_user.id)
    return LearnerProfileRead.model_validate(profile)


@router.post("", response_model=LearnerProfileRead, status_code=status.HTTP_201_CREATED)
async def create_my_profile(
    payload: LearnerProfileCreate, session: SessionDep, current_user: CurrentUser
) -> LearnerProfileRead:
    profile = await ProfileService(session).create_for_user(current_user.id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.patch("", response_model=LearnerProfileRead)
async def update_my_profile(
    payload: LearnerProfileUpdate, session: SessionDep, current_user: CurrentUser
) -> LearnerProfileRead:
    profile = await ProfileService(session).update_for_user(current_user.id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_my_profile(session: SessionDep, current_user: CurrentUser) -> None:
    await ProfileService(session).delete_for_user(current_user.id)


# --- LLM extraction (message -> validated structured profile) --------------
@router.post(
    "/extract",
    response_model=ProfileExtractResponse,
    summary="Extract a structured profile from a natural-language message",
)
async def extract_profile(
    payload: ProfileExtractRequest,
    session: SessionDep,
    provider: LLMProviderDep,
    current_user: CurrentUser,
) -> ProfileExtractResponse:
    """User message → LLM → validated ProfileExtraction → business validation →
    (optionally) ProfileService. The LLM never writes; only catalogue-resolved
    skills are persisted, and only when `apply` is true."""
    _authorize(payload.user_id, current_user)
    service = ProfileExtractionService(session, provider)
    return await service.extract(payload.user_id, payload.message, apply=payload.apply)


# --- explicit user (self or admin) -----------------------------------------
@router.get(
    "/{user_id}",
    response_model=FullLearnerProfile,
    summary="Full profile: fields, skill proficiencies and assessment history",
)
async def get_profile(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> FullLearnerProfile:
    _authorize(user_id, current_user)
    return await ProfileService(session).get_full_profile(user_id)


@router.put(
    "/{user_id}",
    response_model=LearnerProfileRead,
    summary="Create or replace a learner's profile",
)
async def put_profile(
    user_id: uuid.UUID,
    payload: LearnerProfileCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> LearnerProfileRead:
    _authorize(user_id, current_user)
    profile = await ProfileService(session).upsert_for_user(user_id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.patch("/{user_id}", response_model=LearnerProfileRead)
async def patch_profile(
    user_id: uuid.UUID,
    payload: LearnerProfileUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> LearnerProfileRead:
    _authorize(user_id, current_user)
    profile = await ProfileService(session).update_for_user(user_id, payload)
    return LearnerProfileRead.model_validate(profile)


@router.get(
    "/{user_id}/validate",
    response_model=ProfileValidationRead,
    summary="Run semantic validation over a learner's profile",
)
async def validate_profile(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> ProfileValidationRead:
    _authorize(user_id, current_user)
    return await ProfileService(session).validate(user_id)


# --- skill proficiency (0..1) ----------------------------------------------
@router.get("/{user_id}/skills", response_model=list[SkillProficiencyRead])
async def list_skills(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> list[SkillProficiencyRead]:
    _authorize(user_id, current_user)
    return await ProfileService(session).list_skills(user_id)


@router.post(
    "/{user_id}/skills",
    response_model=SkillProficiencyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a skill proficiency (0..1) to a learner",
)
async def add_skill(
    user_id: uuid.UUID,
    payload: SkillProficiencyCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> SkillProficiencyRead:
    _authorize(user_id, current_user)
    return await ProfileService(session).set_skill_proficiency(user_id, payload)


@router.get("/{user_id}/skills/{skill_id}", response_model=SkillProficiencyRead)
async def get_skill(
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> SkillProficiencyRead:
    _authorize(user_id, current_user)
    return await ProfileService(session).get_skill(user_id, skill_id)


@router.put(
    "/{user_id}/skills/{skill_id}",
    response_model=SkillProficiencyRead,
    summary="Set or update a learner's proficiency in one skill",
)
async def put_skill(
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    payload: SkillProficiencyUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> SkillProficiencyRead:
    _authorize(user_id, current_user)
    return await ProfileService(session).upsert_skill_proficiency(user_id, skill_id, payload)


@router.delete(
    "/{user_id}/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_skill(
    user_id: uuid.UUID,
    skill_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    _authorize(user_id, current_user)
    await ProfileService(session).delete_skill(user_id, skill_id)


# --- populate-from-conversation (LLM-ready abstraction) --------------------
@router.post(
    "/{user_id}/ingest",
    response_model=ProfileDraftPreview,
    summary="Extract a profile draft from free text; optionally apply it",
)
async def ingest_profile(
    user_id: uuid.UUID,
    payload: ProfileDraftIngestRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProfileDraftPreview:
    _authorize(user_id, current_user)
    draft = await default_extractor.extract(payload.text)
    if not payload.apply:
        return ProfileDraftPreview(draft=draft, applied=False)
    return await ProfileService(session).apply_draft(user_id, draft)
