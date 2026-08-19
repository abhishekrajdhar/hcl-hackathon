"""Skill-gap analysis endpoint.

All computation is deterministic (see SkillGapService / the gap engine); the LLM
is never involved in gap arithmetic or prerequisite ordering.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.models.enums import UserRole
from app.schemas.skill_gap import SkillGapAnalyzeRequest, SkillGapAnalyzeResponse
from app.services.skill_gap_service import SkillGapService

router = APIRouter(prefix="/skill-gap", tags=["skill-gap"])


@router.post(
    "/analyze",
    response_model=SkillGapAnalyzeResponse,
    summary="Analyse the gap between a learner and a target goal",
)
async def analyze_skill_gap(
    payload: SkillGapAnalyzeRequest, session: SessionDep, current_user: CurrentUser
) -> SkillGapAnalyzeResponse:
    # Ownership (self-or-admin) is enforced inside the service, before any of a
    # target learner's skills are read — so goal- and user_id-derived analyses
    # cannot leak another learner's data.
    service = SkillGapService(session)
    return await service.analyze(
        payload,
        requesting_user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
