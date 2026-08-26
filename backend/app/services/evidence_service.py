"""Evidence behind a skill-twin entry.

A proficiency number without its receipts invites blind trust in self-report.
This service assembles, per skill, everything the system actually knows: the
recorded entry itself, every assessment attempt that measured the skill, and
every completed resource that taught it. Read-only; nothing here scores or
weighs — presentation of evidence, not judgement of it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.assessment import Assessment, AssessmentResult
from app.models.enums import ProgressEventType
from app.models.progress import UserProgress
from app.models.resource import Resource, ResourceSkill
from app.models.skill import Skill, UserSkill
from app.schemas.evidence import EvidenceItem, SkillEvidenceRead
from app.services.base import BaseService


class EvidenceService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def for_skill(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> SkillEvidenceRead:
        entry = (
            await self.session.execute(
                select(UserSkill, Skill)
                .join(Skill, Skill.id == UserSkill.skill_id)
                .where(UserSkill.user_id == user_id, UserSkill.skill_id == skill_id)
            )
        ).first()
        if entry is None:
            raise NotFoundError("Skill proficiency for this user", skill_id)
        user_skill, skill = entry

        items: list[EvidenceItem] = [
            EvidenceItem(
                kind=user_skill.evidence_source.value,
                label={
                    "self_report": "Self-reported",
                    "assessment": "Set by assessment evidence",
                    "completion": "Set by completed material",
                    "inferred": "Inferred by the engine",
                }.get(user_skill.evidence_source.value, user_skill.evidence_source.value),
                detail=user_skill.notes
                or f"Recorded at {user_skill.proficiency:.0%} "
                   f"(confidence {user_skill.confidence:.0%})",
                occurred_at=user_skill.updated_at,
            )
        ]

        # --- assessment attempts that measured this skill -------------------
        results = (
            await self.session.execute(
                select(AssessmentResult, Assessment)
                .join(Assessment, Assessment.id == AssessmentResult.assessment_id)
                .where(
                    AssessmentResult.user_id == user_id,
                    Assessment.skill_id == skill_id,
                )
                .order_by(AssessmentResult.submitted_at.desc())
                .limit(10)
            )
        ).all()
        for result, assessment in results:
            items.append(
                EvidenceItem(
                    kind="assessment",
                    label=f"{'Passed' if result.passed else 'Attempted'}: {assessment.title}",
                    detail=f"Scored {result.percentage:.0f}%",
                    occurred_at=result.submitted_at,
                )
            )

        # --- completed resources that teach this skill ----------------------
        completions = (
            await self.session.execute(
                select(UserProgress, Resource)
                .join(Resource, Resource.id == UserProgress.resource_id)
                .join(ResourceSkill, ResourceSkill.resource_id == Resource.id)
                .where(
                    UserProgress.user_id == user_id,
                    UserProgress.event_type == ProgressEventType.COMPLETED,
                    ResourceSkill.skill_id == skill_id,
                )
                .order_by(UserProgress.occurred_at.desc())
                .limit(10)
            )
        ).unique().all()
        for event, resource in completions:
            spent = f" · {event.time_spent_minutes}m logged" if event.time_spent_minutes else ""
            items.append(
                EvidenceItem(
                    kind="completion",
                    label=f"Completed: {resource.title}",
                    detail=f"{resource.provider or 'resource'}{spent}",
                    occurred_at=event.occurred_at,
                )
            )

        items.sort(key=lambda i: (i.occurred_at is None, i.occurred_at), reverse=True)
        return SkillEvidenceRead(
            skill_id=skill.id,
            skill_name=skill.name,
            skill_slug=skill.slug,
            proficiency=user_skill.proficiency,
            confidence=user_skill.confidence,
            evidence=items,
        )
