"""Career readiness — how close the learner is to the target role, broken
into evidenced dimensions. Derived on demand; nothing is stored."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.readiness import (
    ReadinessDimensionRead,
    ReadinessReportRead,
    ReadinessSkillRead,
)
from app.services.readiness_service import ReadinessService

router = APIRouter(prefix="/readiness", tags=["readiness"])


@router.get("", response_model=ReadinessReportRead)
async def my_readiness(session: SessionDep, current_user: CurrentUser) -> ReadinessReportRead:
    report = await ReadinessService(session).report(current_user.id)
    return ReadinessReportRead(
        overall=report.overall,
        weakest=report.weakest,
        dimensions=[
            ReadinessDimensionRead(key=d.key, label=d.label, score=d.score, detail=d.detail)
            for d in report.dimensions
        ],
        skills=[
            ReadinessSkillRead(
                skill_id=t.skill_id,
                name=t.name,
                required_level=t.required_level,
                current_level=t.current_level,
                readiness=round(t.readiness, 4),
            )
            for t in report.skills
        ],
    )
