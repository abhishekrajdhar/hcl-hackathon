from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, PaginationDep, SessionDep
from app.schemas.common import Page
from app.schemas.feedback import FeedbackCreate, FeedbackRead, FeedbackUpdate
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate, session: SessionDep, current_user: CurrentUser
) -> FeedbackRead:
    entry = await FeedbackService(session).create(current_user.id, payload)
    return FeedbackRead.model_validate(entry)


@router.get("", response_model=Page[FeedbackRead])
async def list_feedback(
    session: SessionDep, pagination: PaginationDep, current_user: CurrentUser
) -> Page[FeedbackRead]:
    items, total = await FeedbackService(session).list_for_user(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[FeedbackRead](
        items=[FeedbackRead.model_validate(f) for f in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{feedback_id}", response_model=FeedbackRead)
async def get_feedback(
    feedback_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> FeedbackRead:
    entry = await FeedbackService(session).get_owned(feedback_id, current_user.id)
    return FeedbackRead.model_validate(entry)


@router.patch("/{feedback_id}", response_model=FeedbackRead)
async def update_feedback(
    feedback_id: uuid.UUID,
    payload: FeedbackUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> FeedbackRead:
    entry = await FeedbackService(session).update(feedback_id, current_user.id, payload)
    return FeedbackRead.model_validate(entry)


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_feedback(
    feedback_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> None:
    await FeedbackService(session).delete(feedback_id, current_user.id)
