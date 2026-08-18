"""Assessment catalogue and deterministic grading.

Grading is exact-match scoring against the stored answer key. Adaptive item
selection and mastery updating (IRT) arrive in a later phase; nothing here
delegates a decision to a model.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.assessment import Assessment, AssessmentQuestion, AssessmentResult
from app.models.enums import AssessmentType, QuestionType
from app.repositories.assessment import (
    AssessmentQuestionRepository,
    AssessmentRepository,
    AssessmentResultRepository,
)
from app.repositories.skill import SkillRepository
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentSubmission,
    AssessmentUpdate,
    QuestionCreate,
    QuestionUpdate,
)
from app.services.base import BaseService


class AssessmentService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.assessments = AssessmentRepository(session)
        self.questions = AssessmentQuestionRepository(session)
        self.results = AssessmentResultRepository(session)
        self.skills = SkillRepository(session)

    # --- assessments ------------------------------------------------------
    async def get(self, assessment_id: uuid.UUID) -> Assessment:
        assessment = await self.assessments.get_with_questions(assessment_id)
        if assessment is None:
            raise NotFoundError("Assessment", assessment_id)
        return assessment

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        skill_id: uuid.UUID | None = None,
        assessment_type: AssessmentType | None = None,
        is_active: bool | None = True,
    ) -> tuple[list[Assessment], int]:
        filters: list[Any] = []
        if skill_id:
            filters.append(Assessment.skill_id == skill_id)
        if assessment_type:
            filters.append(Assessment.type == assessment_type)
        if is_active is not None:
            filters.append(Assessment.is_active.is_(is_active))

        items = await self.assessments.list(
            limit=limit, offset=offset, filters=filters, order_by=(Assessment.created_at.desc(),)
        )
        total = await self.assessments.count(filters)
        return items, total

    async def create(self, payload: AssessmentCreate) -> Assessment:
        if payload.skill_id is not None and await self.skills.get(payload.skill_id) is None:
            raise NotFoundError("Skill", payload.skill_id)

        assessment = await self.assessments.create(payload.model_dump(exclude={"questions"}))
        seen: set[int] = set()
        for question in payload.questions:
            if question.order_index in seen:
                raise ValidationError(
                    f"Duplicate order_index {question.order_index} in questions",
                    error_code="duplicate_order_index",
                )
            seen.add(question.order_index)
            self._validate_question(question)
            self.questions.add(
                AssessmentQuestion(assessment_id=assessment.id, **question.model_dump())
            )
        await self.session.flush()
        await self.commit()
        return await self.get(assessment.id)

    @staticmethod
    def _validate_question(question: QuestionCreate) -> None:
        choice_types = {
            QuestionType.SINGLE_CHOICE,
            QuestionType.MULTIPLE_CHOICE,
            QuestionType.TRUE_FALSE,
        }
        if question.question_type in choice_types and len(question.options) < 2:
            raise ValidationError(
                "Choice questions need at least two options", error_code="insufficient_options"
            )
        if question.question_type in choice_types and "value" not in question.correct_answer:
            raise ValidationError(
                "correct_answer must contain a 'value' key", error_code="missing_answer_key"
            )

    async def update(self, assessment_id: uuid.UUID, payload: AssessmentUpdate) -> Assessment:
        assessment = await self.get(assessment_id)
        await self.assessments.update(assessment, payload.model_dump(exclude_unset=True))
        await self.commit()
        return await self.get(assessment_id)

    async def delete(self, assessment_id: uuid.UUID) -> None:
        assessment = await self.get(assessment_id)
        await self.assessments.delete(assessment)
        await self.commit()

    async def question_count(self, assessment_id: uuid.UUID) -> int:
        counts = await self.assessments.question_counts([assessment_id])
        return counts.get(assessment_id, 0)

    # --- questions --------------------------------------------------------
    async def list_questions(self, assessment_id: uuid.UUID) -> list[AssessmentQuestion]:
        await self.get(assessment_id)
        return await self.questions.list_for_assessment(assessment_id)

    async def add_question(
        self, assessment_id: uuid.UUID, payload: QuestionCreate
    ) -> AssessmentQuestion:
        await self.get(assessment_id)
        self._validate_question(payload)
        clash = await self.questions.get_by(
            assessment_id=assessment_id, order_index=payload.order_index
        )
        if clash is not None:
            raise ConflictError(
                f"order_index {payload.order_index} is already used in this assessment",
                error_code="duplicate_order_index",
            )
        question = await self.questions.create(
            {**payload.model_dump(), "assessment_id": assessment_id}
        )
        await self.commit()
        return question

    async def update_question(
        self, assessment_id: uuid.UUID, question_id: uuid.UUID, payload: QuestionUpdate
    ) -> AssessmentQuestion:
        question = await self.questions.get(question_id)
        if question is None or question.assessment_id != assessment_id:
            raise NotFoundError("Assessment question", question_id)
        await self.questions.update(question, payload.model_dump(exclude_unset=True))
        await self.commit()
        return question

    async def delete_question(self, assessment_id: uuid.UUID, question_id: uuid.UUID) -> None:
        question = await self.questions.get(question_id)
        if question is None or question.assessment_id != assessment_id:
            raise NotFoundError("Assessment question", question_id)
        await self.questions.delete(question)
        await self.commit()

    # --- grading ----------------------------------------------------------
    async def submit(
        self, assessment_id: uuid.UUID, user_id: uuid.UUID, payload: AssessmentSubmission
    ) -> AssessmentResult:
        assessment = await self.get(assessment_id)
        questions = {q.id: q for q in assessment.questions}
        if not questions:
            raise ValidationError(
                "This assessment has no questions to grade", error_code="empty_assessment"
            )

        responses: list[dict[str, Any]] = []
        score = 0.0
        for answer in payload.answers:
            question = questions.get(answer.question_id)
            if question is None:
                raise ValidationError(
                    f"Question {answer.question_id} does not belong to this assessment",
                    error_code="unknown_question",
                )
            is_correct = self._grade(question, answer.response)
            if is_correct:
                score += question.points
            responses.append(
                {
                    "question_id": str(question.id),
                    "skill_id": str(question.skill_id) if question.skill_id else None,
                    "response": answer.response,
                    "is_correct": is_correct,
                    "points_awarded": question.points if is_correct else 0.0,
                    "points_possible": question.points,
                    "time_spent_ms": answer.time_spent_ms,
                }
            )

        max_score = sum(q.points for q in questions.values())
        percentage = (score / max_score) if max_score else 0.0

        result = await self.results.create(
            {
                "user_id": user_id,
                "assessment_id": assessment_id,
                "path_item_id": payload.path_item_id,
                "started_at": payload.started_at,
                "submitted_at": datetime.now(timezone.utc),
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "passed": percentage >= assessment.passing_score,
                "duration_seconds": payload.duration_seconds,
                "responses": responses,
            }
        )
        await self.commit()
        return result

    @staticmethod
    def _grade(question: AssessmentQuestion, response: Any) -> bool:
        """Exact match against the answer key.

        Short-answer questions are never auto-marked correct — they are left for
        a reviewer (or a later grading stage) rather than guessed at here.
        """
        if question.question_type == QuestionType.SHORT_ANSWER:
            return False

        expected = question.correct_answer.get("value")
        if expected is None:
            return False

        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            if not isinstance(response, list) or not isinstance(expected, list):
                return False
            return sorted(map(str, response)) == sorted(map(str, expected))

        return str(response) == str(expected)

    async def list_results(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[AssessmentResult], int]:
        items = await self.results.list_for_user(user_id, limit=limit, offset=offset)
        total = await self.results.count([AssessmentResult.user_id == user_id])
        return items, total

    async def get_result(self, result_id: uuid.UUID, user_id: uuid.UUID) -> AssessmentResult:
        result = await self.results.get(result_id)
        if result is None or result.user_id != user_id:
            raise NotFoundError("Assessment result", result_id)
        return result
