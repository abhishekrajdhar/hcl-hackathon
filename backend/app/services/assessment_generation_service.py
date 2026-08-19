"""Assessment generation.

Produces a multiple-choice assessment for a skill. The LLM MAY write the
questions, but its output is parsed and validated against a strict Pydantic
schema before anything is stored — a malformed or mis-keyed question is dropped,
never scored. When no LLM is configured (or it fails validation), a
deterministic template generator provides valid questions so the backend always
works locally. The LLM never determines the score; grading is exact-match.
"""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.embeddings.base import EmbeddingProvider  # noqa: F401  (kept for symmetry)
from app.engines.assessment import GeneratedMCQuestion, SkillFact, generate_mc_questions
from app.llm.base import LLMError, LLMProvider
from app.llm.parsing import JsonExtractionError, extract_json_object
from app.llm.schemas import GeneratedAssessment, generated_assessment_schema
from app.models.enums import AssessmentType, QuestionType
from app.models.skill import Skill
from app.repositories.skill import SkillRepository
from app.schemas.assessment import AssessmentCreate, QuestionCreate
from app.schemas.assessment_gen import (
    GenerateAssessmentRequest,
    GeneratedAssessmentInfo,
)
from app.services.assessment_service import AssessmentService
from app.services.base import BaseService

logger = get_logger(__name__)

_ASSESSMENT_SYSTEM_PROMPT = """You write multiple-choice quiz questions to test \
whether a learner has acquired a specific skill. Return only the structured \
questions. Each question must have exactly one correct option, plausible \
distractors, unique option keys, and the correct_key must match an option key. \
Do not invent facts about the learner. Keep questions focused on the named skill."""


class AssessmentGenerationService(BaseService):
    def __init__(self, session: AsyncSession, llm_provider: LLMProvider | None = None) -> None:
        super().__init__(session)
        self.skills = SkillRepository(session)
        self.assessments = AssessmentService(session)
        self.llm = llm_provider

    async def generate(self, request: GenerateAssessmentRequest) -> GeneratedAssessmentInfo:
        skill = await self._resolve_skill(request)
        distractors = await self._distractor_facts(skill)

        source = "template"
        source_model: str | None = None
        questions: list[GeneratedMCQuestion] = []

        if request.use_llm and self.llm is not None:
            questions, source_model = await self._try_llm(skill, request)
            if questions:
                source = "llm"

        if not questions:
            questions = generate_mc_questions(
                self._fact(skill),
                distractors,
                count=request.num_questions,
                difficulty=request.difficulty,
            )
            source = "template"
            source_model = "deterministic-question-bank-v1"

        assessment = await self._persist(skill, request, questions, source, source_model)
        return GeneratedAssessmentInfo(
            assessment_id=assessment.id,
            skill_id=skill.id,
            title=assessment.title,
            question_count=len(questions),
            difficulty=request.difficulty,
            source=source,  # type: ignore[arg-type]
            source_model=source_model,
        )

    # --- LLM path (validated) -------------------------------------------
    async def _try_llm(
        self, skill: Skill, request: GenerateAssessmentRequest
    ) -> tuple[list[GeneratedMCQuestion], str | None]:
        prompt = (
            f"Write {request.num_questions} multiple-choice questions at difficulty "
            f"{request.difficulty}/5 that test the skill '{skill.name}'. "
            f"Skill description: {skill.description or 'n/a'}."
        )
        try:
            completion = await self.llm.complete(  # type: ignore[union-attr]
                system=_ASSESSMENT_SYSTEM_PROMPT,
                user=prompt,
                json_schema=generated_assessment_schema(),
                max_tokens=2048,
            )
            payload = extract_json_object(completion.text)
            validated = GeneratedAssessment.model_validate(payload)
        except (LLMError, JsonExtractionError, PydanticValidationError) as exc:
            logger.warning(
                "assessment generation via LLM failed; using template",
                extra={"skill": skill.slug, "error": str(exc)[:200]},
            )
            return [], None

        questions = [
            GeneratedMCQuestion(
                stem=q.stem,
                options=[{"key": o.key, "text": o.text} for o in q.options],
                correct_key=q.correct_key,
                explanation=q.explanation,
                difficulty=q.difficulty,
            )
            for q in validated.questions[: request.num_questions]
        ]
        model = getattr(completion, "model", None)
        return questions, f"{self.llm.name}:{model}" if self.llm else None

    # --- persistence -----------------------------------------------------
    async def _persist(
        self,
        skill: Skill,
        request: GenerateAssessmentRequest,
        questions: list[GeneratedMCQuestion],
        source: str,
        source_model: str | None,
    ):  # type: ignore[no-untyped-def]
        payload = AssessmentCreate(
            skill_id=skill.id,
            title=request.title or f"{skill.name} checkpoint",
            description=f"Auto-generated ({source}) assessment for {skill.name}.",
            type=AssessmentType.CHECKPOINT,
            difficulty=request.difficulty,
            passing_score=0.7,
            questions=[
                QuestionCreate(
                    skill_id=skill.id,
                    order_index=index,
                    question_type=QuestionType.SINGLE_CHOICE,
                    stem=q.stem,
                    options=[dict(o) for o in q.options],
                    correct_answer={"value": q.correct_key},
                    explanation=q.explanation,
                    points=1.0,
                    difficulty_b=float(q.difficulty),
                )
                for index, q in enumerate(questions)
            ],
        )
        assessment = await self.assessments.create(payload)
        # mark provenance
        assessment.is_generated = True
        assessment.source_model = source_model
        await self.session.flush()
        await self.commit()
        return assessment

    # --- helpers ---------------------------------------------------------
    async def _resolve_skill(self, request: GenerateAssessmentRequest) -> Skill:
        if request.skill_id is not None:
            skill = await self.skills.get(request.skill_id)
            if skill is None:
                raise NotFoundError("Skill", request.skill_id)
            return skill
        if request.skill_slug:
            skill = await self.skills.get_by_slug(request.skill_slug)
            if skill is None:
                raise NotFoundError("Skill", request.skill_slug)
            return skill
        raise NotFoundError("Skill", "none provided")

    @staticmethod
    def _fact(skill: Skill) -> SkillFact:
        return SkillFact(
            skill_id=skill.id,
            name=skill.name,
            description=skill.description,
            category_name=skill.category.name if skill.category else None,
        )

    async def _distractor_facts(self, skill: Skill) -> list[SkillFact]:
        others = await self.skills.list(
            limit=12,
            filters=[Skill.id != skill.id, Skill.is_active.is_(True)],
            order_by=(Skill.difficulty, Skill.slug),
        )
        return [self._fact(s) for s in others]
