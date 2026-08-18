from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, PaginationDep, SessionDep
from app.schemas.common import Page
from app.schemas.progress import ProgressEventCreate, ProgressEventRead, ProgressSummary
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("/events", response_model=ProgressEventRead, status_code=status.HTTP_201_CREATED)
async def record_event(
    payload: ProgressEventCreate, session: SessionDep, current_user: CurrentUser
) -> ProgressEventRead:
    event = await ProgressService(session).record(current_user.id, payload)
    return ProgressEventRead.model_validate(event)


@router.get("/events", response_model=Page[ProgressEventRead])
async def list_events(
    session: SessionDep, pagination: PaginationDep, current_user: CurrentUser
) -> Page[ProgressEventRead]:
    items, total = await ProgressService(session).list_for_user(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[ProgressEventRead](
        items=[ProgressEventRead.model_validate(e) for e in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/summary",
    response_model=ProgressSummary,
    summary="Derived progress summary for the current learner",
)
async def summary(session: SessionDep, current_user: CurrentUser) -> ProgressSummary:
    return await ProgressService(session).summary(current_user.id)
