from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, PaginationDep, SessionDep, get_llm_provider_dep
from app.llm.base import LLMProvider
from app.models.enums import PathStatus, UserRole
from app.schemas.explanation import ExplanationRequest, PathItemExplanationResponse
from app.schemas.common import Page
from app.schemas.path import (
    LearningPathCreate,
    LearningPathDetail,
    LearningPathRead,
    LearningPathUpdate,
    PathItemCreate,
    PathItemRead,
    PathItemUpdate,
)
from app.services.explanation_service import ExplanationService
from app.services.path_service import PathService

router = APIRouter(prefix="/learning-paths", tags=["learning-paths"])


@router.get("", response_model=Page[LearningPathRead])
async def list_paths(
    session: SessionDep,
    pagination: PaginationDep,
    current_user: CurrentUser,
    status_filter: PathStatus | None = None,
) -> Page[LearningPathRead]:
    items, total = await PathService(session).list_for_user(
        current_user.id, limit=pagination.limit, offset=pagination.offset, status=status_filter
    )
    return Page[LearningPathRead](
        items=[LearningPathRead.model_validate(p) for p in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=LearningPathDetail, status_code=status.HTTP_201_CREATED)
async def create_path(
    payload: LearningPathCreate, session: SessionDep, current_user: CurrentUser
) -> LearningPathDetail:
    path = await PathService(session).create(current_user.id, payload)
    return LearningPathDetail.model_validate(path)


@router.get("/active", response_model=LearningPathDetail, summary="The learner's active path")
async def get_active_path(session: SessionDep, current_user: CurrentUser) -> LearningPathDetail:
    path = await PathService(session).get_active(current_user.id)
    return LearningPathDetail.model_validate(path)


@router.get("/{path_id}", response_model=LearningPathDetail)
async def get_path(
    path_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> LearningPathDetail:
    path = await PathService(session).get_owned(path_id, current_user.id)
    return LearningPathDetail.model_validate(path)


@router.patch("/{path_id}", response_model=LearningPathDetail)
async def update_path(
    path_id: uuid.UUID,
    payload: LearningPathUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> LearningPathDetail:
    path = await PathService(session).update(path_id, current_user.id, payload)
    return LearningPathDetail.model_validate(path)


@router.delete("/{path_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_path(path_id: uuid.UUID, session: SessionDep, current_user: CurrentUser) -> None:
    await PathService(session).delete(path_id, current_user.id)


# --- items -----------------------------------------------------------------
@router.get("/{path_id}/items", response_model=list[PathItemRead])
async def list_items(
    path_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> list[PathItemRead]:
    items = await PathService(session).list_items(path_id, current_user.id)
    return [PathItemRead.model_validate(i) for i in items]


@router.post("/{path_id}/items", response_model=PathItemRead, status_code=status.HTTP_201_CREATED)
async def add_item(
    path_id: uuid.UUID,
    payload: PathItemCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> PathItemRead:
    item = await PathService(session).add_item(path_id, current_user.id, payload)
    return PathItemRead.model_validate(item)


@router.patch("/{path_id}/items/{item_id}", response_model=PathItemRead)
async def update_item(
    path_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: PathItemUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> PathItemRead:
    item = await PathService(session).update_item(path_id, item_id, current_user.id, payload)
    return PathItemRead.model_validate(item)


@router.delete("/{path_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_item(
    path_id: uuid.UUID, item_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    await PathService(session).delete_item(path_id, item_id, current_user.id)


@router.post(
    "/{path_id}/items/{item_id}/explanation",
    response_model=PathItemExplanationResponse,
    summary="Why this item is on the learner's path",
)
async def explain_item(
    path_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ExplanationRequest,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMProvider = Depends(get_llm_provider_dep),
) -> PathItemExplanationResponse:
    """Grounded in the item's persisted rationale trace and the learner's
    current proficiency records; the model only rephrases, and its output is
    rejected by the grounding check if it invents a number or skill."""
    return await ExplanationService(session, llm).explain_path_item(
        path_id,
        item_id,
        payload,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
