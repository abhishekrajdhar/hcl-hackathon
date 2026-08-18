from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import selectinload

from app.models.assessment import Assessment, AssessmentQuestion, AssessmentResult
from app.repositories.base import BaseRepository


class AssessmentRepository(BaseRepository[Assessment]):
    model = Assessment

    def with_questions(self) -> Select[tuple[Assessment]]:
        return select(Assessment).options(selectinload(Assessment.questions))

    async def get_with_questions(self, assessment_id: uuid.UUID) -> Assessment | None:
        stmt = self.with_questions().where(Assessment.id == assessment_id)
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def question_counts(self, assessment_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not assessment_ids:
            return {}
        stmt = (
            select(AssessmentQuestion.assessment_id, func.count())
            .where(AssessmentQuestion.assessment_id.in_(assessment_ids))
            .group_by(AssessmentQuestion.assessment_id)
        )
        return {row[0]: int(row[1]) for row in await self.session.execute(stmt)}


class AssessmentQuestionRepository(BaseRepository[AssessmentQuestion]):
    model = AssessmentQuestion

    async def list_for_assessment(self, assessment_id: uuid.UUID) -> list[AssessmentQuestion]:
        stmt = (
            select(AssessmentQuestion)
            .where(AssessmentQuestion.assessment_id == assessment_id)
            .order_by(AssessmentQuestion.order_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def max_order_index(self, assessment_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(AssessmentQuestion.order_index), -1)).where(
            AssessmentQuestion.assessment_id == assessment_id
        )
        return int((await self.session.execute(stmt)).scalar_one())


class AssessmentResultRepository(BaseRepository[AssessmentResult]):
    model = AssessmentResult

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[AssessmentResult]:
        stmt = (
            select(AssessmentResult)
            .where(AssessmentResult.user_id == user_id)
            .order_by(AssessmentResult.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())
