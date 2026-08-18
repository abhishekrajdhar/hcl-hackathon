"""Semantic search endpoints.

Vector retrieval only — similarity is computed by pgvector, never an LLM.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.core.deps import (
    CurrentUser,
    EmbeddingCacheDep,
    EmbeddingProviderDep,
    SessionDep,
)
from app.schemas.resource import ResourceRead
from app.schemas.search import (
    GoalSearchRequest,
    ResourceSearchResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.search_service import ScoredResource, SemanticSearchService

router = APIRouter(prefix="/search", tags=["search"])


def _to_response(
    query: str, provider: str, scored: list[ScoredResource]
) -> SemanticSearchResponse:
    return SemanticSearchResponse(
        query=query,
        provider=provider,
        count=len(scored),
        results=[
            ResourceSearchResult(
                resource=ResourceRead.model_validate(s.resource),
                similarity=s.similarity,
                distance=s.distance,
            )
            for s in scored
        ],
    )


@router.post(
    "/semantic",
    response_model=SemanticSearchResponse,
    summary="Find the most semantically relevant resources for a query",
)
async def semantic_search(
    payload: SemanticSearchRequest,
    session: SessionDep,
    provider: EmbeddingProviderDep,
    cache: EmbeddingCacheDep,
    _: CurrentUser,
) -> SemanticSearchResponse:
    service = SemanticSearchService(session, provider, cache)
    scored = await service.semantic_search(
        payload.query,
        top_k=payload.top_k,
        resource_type=payload.resource_type,
        max_difficulty=payload.max_difficulty,
        skill_id=payload.skill_id,
    )
    return _to_response(payload.query, provider.name, scored)


@router.post(
    "/for-goal",
    response_model=SemanticSearchResponse,
    summary="Resources relevant to a goal (search_resources_for_goal)",
)
async def search_for_goal(
    payload: GoalSearchRequest,
    session: SessionDep,
    provider: EmbeddingProviderDep,
    cache: EmbeddingCacheDep,
    current_user: CurrentUser,
) -> SemanticSearchResponse:
    service = SemanticSearchService(session, provider, cache)
    scored = await service.search_resources_for_goal(
        goal_id=payload.goal_id,
        goal_text=payload.goal_text,
        user_id=current_user.id,
        top_k=payload.top_k,
    )
    label = payload.goal_text or str(payload.goal_id)
    return _to_response(label, provider.name, scored)


@router.get(
    "/for-skill/{skill_id}",
    response_model=SemanticSearchResponse,
    summary="Resources relevant to a skill (search_resources_for_skill)",
)
async def search_for_skill(
    skill_id: uuid.UUID,
    session: SessionDep,
    provider: EmbeddingProviderDep,
    cache: EmbeddingCacheDep,
    _: CurrentUser,
    top_k: int = Query(default=10, ge=1, le=100),
    teaches_only: bool = Query(default=False),
) -> SemanticSearchResponse:
    service = SemanticSearchService(session, provider, cache)
    scored = await service.search_resources_for_skill(
        skill_id, top_k=top_k, teaches_only=teaches_only
    )
    return _to_response(str(skill_id), provider.name, scored)


@router.get(
    "/for-profile",
    response_model=SemanticSearchResponse,
    summary="Resources relevant to the current learner (search_resources_for_profile)",
)
async def search_for_profile(
    session: SessionDep,
    provider: EmbeddingProviderDep,
    cache: EmbeddingCacheDep,
    current_user: CurrentUser,
    top_k: int = Query(default=10, ge=1, le=100),
) -> SemanticSearchResponse:
    service = SemanticSearchService(session, provider, cache)
    scored = await service.search_resources_for_profile(current_user.id, top_k=top_k)
    return _to_response("profile", provider.name, scored)
