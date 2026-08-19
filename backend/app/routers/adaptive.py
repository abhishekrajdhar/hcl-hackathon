"""Adaptive-learning endpoint.

Runs the deterministic post-event pipeline (update skill -> recalc gaps ->
recalc recommendations -> update path -> next action). No LLM is involved.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.models.enums import UserRole
from app.schemas.adaptive import AdaptiveUpdateRequest, AdaptiveUpdateResponse
from app.services.adaptive_service import AdaptiveLearningService

router = APIRouter(prefix="/adaptive", tags=["adaptive"])


@router.post(
    "/update",
    response_model=AdaptiveUpdateResponse,
    summary="Adapt the learner's path from a progress event (deterministic)",
)
async def adaptive_update(
    payload: AdaptiveUpdateRequest, session: SessionDep, current_user: CurrentUser
) -> AdaptiveUpdateResponse:
    return await AdaptiveLearningService(session).update(
        payload,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
