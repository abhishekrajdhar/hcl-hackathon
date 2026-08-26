"""Learning-path generation and roadmap endpoints.

The roadmap is built by deterministic algorithms (see PathGeneratorService and
the path engine); the LLM is not involved in constructing it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, SessionDep, get_llm_provider_dep
from app.llm.base import LLMProvider
from app.models.enums import UserRole
from app.schemas.learning_path import (
    GeneratePathRequest,
    LearningPathRoadmap,
    RegeneratePathRequest,
)
from app.services.path_generator_service import PathGeneratorService

router = APIRouter(prefix="/learning-path", tags=["learning-path"])


@router.post(
    "/generate",
    response_model=LearningPathRoadmap,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a prerequisite-aware, phased roadmap",
)
async def generate_path(
    payload: GeneratePathRequest,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMProvider = Depends(get_llm_provider_dep),
) -> LearningPathRoadmap:
    return await PathGeneratorService(session, llm).generate(
        payload,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )


@router.get(
    "/{user_id}",
    response_model=LearningPathRoadmap,
    summary="The learner's active roadmap",
)
async def get_path(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> LearningPathRoadmap:
    return await PathGeneratorService(session).get_active_roadmap(
        user_id,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )


@router.post(
    "/{path_id}/regenerate",
    response_model=LearningPathRoadmap,
    summary="Rebuild a roadmap from the latest gaps and constraints",
)
async def regenerate_path(
    path_id: uuid.UUID,
    payload: RegeneratePathRequest,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMProvider = Depends(get_llm_provider_dep),
) -> LearningPathRoadmap:
    return await PathGeneratorService(session, llm).regenerate(
        path_id,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
        weekly_hours=payload.weekly_hours,
        target_deadline=payload.target_deadline,
    )
