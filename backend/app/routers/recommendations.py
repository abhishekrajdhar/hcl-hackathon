"""Recommendation CRUD.

Generation/ranking is intentionally absent — see the architecture's
recommendation engine phase. These endpoints only read and transition
recommendations that already exist.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import (
    AdminUser,
    CurrentUser,
    EmbeddingCacheDep,
    EmbeddingProviderDep,
    PaginationDep,
    SessionDep,
)
from app.models.enums import RecommendationStatus
from app.schemas.common import Page
from app.schemas.recommendation import (
    RecommendationCreate,
    RecommendationRead,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationStatusUpdate,
)
from app.services.recommendation_engine_service import RecommendationEngineService
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "",
    response_model=RecommendationResponse,
    summary="Generate ranked, prerequisite-aware resource recommendations",
)
async def generate_recommendations(
    payload: RecommendationRequest,
    session: SessionDep,
    provider: EmbeddingProviderDep,
    cache: EmbeddingCacheDep,
    current_user: CurrentUser,
) -> RecommendationResponse:
    """Hybrid ranking over the learner's gaps, semantic similarity, prerequisite
    readiness, difficulty, preferences, quality and history. Ownership (self or
    admin) is enforced inside the service before any of the learner's data is
    read."""
    from app.models.enums import UserRole

    service = RecommendationEngineService(session, provider, cache)
    return await service.recommend_resources(
        payload,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )


@router.get("", response_model=Page[RecommendationRead])
async def list_recommendations(
    session: SessionDep,
    pagination: PaginationDep,
    current_user: CurrentUser,
    status_filter: RecommendationStatus | None = None,
) -> Page[RecommendationRead]:
    items, total = await RecommendationService(session).list_for_user(
        current_user.id,
        limit=pagination.limit,
        offset=pagination.offset,
        status=status_filter,
    )
    return Page[RecommendationRead](
        items=[RecommendationRead.model_validate(r) for r in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{recommendation_id}", response_model=RecommendationRead)
async def get_recommendation(
    recommendation_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> RecommendationRead:
    entry = await RecommendationService(session).get_owned(recommendation_id, current_user.id)
    return RecommendationRead.model_validate(entry)


@router.patch("/{recommendation_id}/status", response_model=RecommendationRead)
async def set_status(
    recommendation_id: uuid.UUID,
    payload: RecommendationStatusUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> RecommendationRead:
    entry = await RecommendationService(session).set_status(
        recommendation_id, current_user.id, payload.status
    )
    return RecommendationRead.model_validate(entry)


@router.delete("/{recommendation_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_recommendation(
    recommendation_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    await RecommendationService(session).delete(recommendation_id, current_user.id)


admin_router = APIRouter(prefix="/users/{user_id}/recommendations", tags=["recommendations"])


@admin_router.post(
    "",
    response_model=RecommendationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Seed a recommendation for a learner (admin)",
)
async def create_for_user(
    user_id: uuid.UUID,
    payload: RecommendationCreate,
    session: SessionDep,
    _: AdminUser,
) -> RecommendationRead:
    entry = await RecommendationService(session).create_for_user(user_id, payload)
    return RecommendationRead.model_validate(entry)
