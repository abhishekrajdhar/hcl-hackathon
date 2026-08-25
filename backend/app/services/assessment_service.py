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
    PendingReview,
    QuestionCreate,
    QuestionUpdate,
    ReviewResponseRequest,
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
            # A short answer is not wrong — it is ungraded. Flagging it here is
            # what makes it findable by a reviewer instead of quietly scoring 0.
            needs_review = question.question_type == QuestionType.SHORT_ANSWER
            responses.append(
                {
                    "question_id": str(question.id),
                    "skill_id": str(question.skill_id) if question.skill_id else None,
                    "response": answer.response,
                    "is_correct": is_correct,
                    "points_awarded": question.points if is_correct else 0.0,
                    "points_possible": question.points,
                    "time_spent_ms": answer.time_spent_ms,
                    "needs_review": needs_review,
                    "prompt": question.stem,
                    "reviewed_by": None,
                    "reviewer_note": None,
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

    # --- short-answer review ---------------------------------------------
    async def list_pending_reviews(
        self, *, limit: int, offset: int
    ) -> tuple[list[PendingReview], int]:
        """Every short answer still waiting on a human.

        Grading refuses to auto-mark these, so without somewhere to see them
        they simply sit at zero forever. This is that queue.
        """
        results = await self.results.list_with_pending_review(limit=limit, offset=offset)
        total = await self.results.count_with_pending_review()
        pending = [
            PendingReview(
                result_id=result.id,
                assessment_id=result.assessment_id,
                user_id=result.user_id,
                submitted_at=result.submitted_at,
                question_id=uuid.UUID(response["question_id"]),
                prompt=response.get("prompt") or "",
                response=response.get("response"),
                points_possible=float(response.get("points_possible") or 0.0),
            )
            for result in results
            for response in result.responses
            if response.get("needs_review")
        ]
        return pending, total

    async def review_response(
        self,
        result_id: uuid.UUID,
        payload: ReviewResponseRequest,
        *,
        reviewer_id: uuid.UUID,
    ) -> AssessmentResult:
        """Mark one short answer correct or incorrect and re-score the attempt.

        Re-scoring is a full recomputation from the responses, not an increment,
        so reviewing the same answer twice cannot inflate a score — the same
        rule the rest of the app follows for derived numbers.
        """
        result = await self.results.get(result_id)
        if result is None:
            raise NotFoundError("Assessment result", result_id)

        target = str(payload.question_id)
        responses = [dict(r) for r in result.responses]
        match = next((r for r in responses if r.get("question_id") == target), None)
        if match is None:
            raise NotFoundError("Response for that question on this result", payload.question_id)
        if not match.get("needs_review"):
            raise ValidationError(
                "That response is not awaiting review", error_code="not_reviewable"
            )

        match["is_correct"] = payload.is_correct
        match["points_awarded"] = float(match.get("points_possible") or 0.0) if payload.is_correct else 0.0
        match["needs_review"] = False
        match["reviewed_by"] = str(reviewer_id)
        match["reviewer_note"] = payload.note

        score = sum(float(r.get("points_awarded") or 0.0) for r in responses)
        max_score = sum(float(r.get("points_possible") or 0.0) for r in responses)
        percentage = round(score / max_score * 100, 2) if max_score else 0.0
        assessment = await self.assessments.get(result.assessment_id)
        passing = assessment.passing_score if assessment else 0.0

        updated = await self.results.update(
            result,
            {
                "responses": responses,
                "score": score,
                "max_score": max_score,
                "percentage": percentage,
                "passed": percentage >= passing,
            },
        )
        await self.commit()
        return updated

    async def list_results(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> tuple[list[AssessmentResult], int]:
        items = await self.results.list_for_user(user_id, limit=limit, offset=offset)
        total = await self.results.count([AssessmentResult.user_id == user_id])
        return items, total

    async def submit_and_report(
        self, assessment_id: uuid.UUID, user_id: uuid.UUID, payload: AssessmentSubmission
    ):  # type: ignore[no-untyped-def]
        """Grade, update proficiency, and return the full learner-facing report.

        Every number here is computed deterministically: grading is exact-match,
        the mastery band is a pure threshold map, and proficiency updates are the
        evidence-weighted engine — the LLM is never consulted for a score.
        """
        from app.engines.assessment import (
            mastery_level,
            recommended_next_action,
        )
        from app.engines.assessment import (
            weak_topics as compute_weak_topics,
        )
        from app.repositories.skill import SkillRepository
        from app.schemas.assessment import AssessmentResultRead
        from app.schemas.assessment_gen import (
            AssessmentSubmitReport,
            SkillUpdate,
            WeakTopicRead,
        )
        from app.services.profile_service import ProfileService

        result = await self.submit(assessment_id, user_id, payload)
        prof_report = await ProfileService(self.session).update_proficiency_from_assessment(
            user_id, result
        )

        skill_ids = {
            uuid.UUID(str(r["skill_id"]))
            for r in result.responses
            if r.get("skill_id")
        }
        skill_ids.update(c.skill_id for c in prof_report.changes)
        skills = SkillRepository(self.session)
        names = {s.id: s.name for s in await skills.get_many(sorted(skill_ids))}

        weak = compute_weak_topics(result.responses, names)
        mastery = mastery_level(result.percentage)
        next_action = recommended_next_action(
            result.percentage, [w.skill_name for w in weak]
        )

        return AssessmentSubmitReport(
            result=AssessmentResultRead.model_validate(result),
            score=result.score,
            percentage=round(result.percentage, 4),
            passed=result.passed,
            mastery_level=mastery,
            skill_updates=[
                SkillUpdate(
                    skill_id=c.skill_id,
                    skill_name=names.get(c.skill_id),
                    previous_proficiency=c.previous_proficiency,
                    new_proficiency=c.new_proficiency,
                    delta=c.delta,
                )
                for c in prof_report.changes
            ],
            weak_topics=[
                WeakTopicRead(
                    skill_id=w.skill_id,
                    skill_name=w.skill_name,
                    correct=w.correct,
                    total=w.total,
                    ratio=round(w.ratio, 4),
                )
                for w in weak
            ],
            recommended_next_action=next_action,
        )

    async def list_results_for_assessment(
        self, assessment_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[AssessmentResult]:
        await self.get(assessment_id)
        return await self.results.list(
            limit=100,
            filters=[
                AssessmentResult.assessment_id == assessment_id,
                AssessmentResult.user_id == user_id,
            ],
            order_by=(AssessmentResult.created_at.desc(),),
        )

    async def get_result(self, result_id: uuid.UUID, user_id: uuid.UUID) -> AssessmentResult:
        result = await self.results.get(result_id)
        if result is None or result.user_id != user_id:
            raise NotFoundError("Assessment result", result_id)
        return result
