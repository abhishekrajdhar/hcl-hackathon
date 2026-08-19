"""Recommendation explainability.

    Recommendation -> RecommendationEvidence -> LLM -> grounded explanation

Builds a structured evidence object from stored facts, hands ONLY that to the
LLM, then verifies the generated text introduces no unsupported number or skill.
If the LLM is unavailable or its output fails the grounding check, a
deterministic template (grounded by construction) is used. The LLM never invents
facts, and no ungrounded claim is ever returned.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.engines.explanation import check_grounding, render_template
from app.llm.base import LLMError, LLMProvider
from app.models.goal import LearningGoal
from app.models.recommendation import Recommendation
from app.models.skill import UserSkill
from app.repositories.goal import LearningGoalRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.skill import (
    PrerequisiteRepository,
    SkillRepository,
    UserSkillRepository,
)
from app.repositories.user import LearnerProfileRepository, UserRepository
from app.schemas.explanation import (
    ExplanationRequest,
    ExplanationResponse,
    PrerequisiteRelation,
    RecommendationEvidence,
    ResourceSkillFact,
    RoadmapPosition,
)
from app.services.base import BaseService

logger = get_logger(__name__)

_STRENGTH_THRESHOLD = 0.6
_DEFAULT_REQUIRED = 0.7
_GOAL_LEVEL_SCALE = 10.0
_PREREQ_LEVEL_SCALE = 10.0

_EXPLANATION_SYSTEM_PROMPT = """You explain, in 2-4 sentences, why a learning \
resource was recommended to a learner. You are given ONLY a set of structured \
facts. Use only those facts. Never introduce a skill, percentage, or claim that \
is not present in the facts. Do not exaggerate. Write directly to the learner."""


class ExplanationService(BaseService):
    def __init__(self, session: AsyncSession, llm_provider: LLMProvider | None = None) -> None:
        super().__init__(session)
        self.llm = llm_provider
        self.recommendations = RecommendationRepository(session)
        self.skills = SkillRepository(session)
        self.user_skills = UserSkillRepository(session)
        self.prerequisites = PrerequisiteRepository(session)
        self.goals = LearningGoalRepository(session)
        self.profiles = LearnerProfileRepository(session)
        self.paths = LearningPathRepository(session)
        self.path_items = LearningPathItemRepository(session)
        self.users = UserRepository(session)

    async def explain(
        self,
        recommendation_id: uuid.UUID,
        request: ExplanationRequest,
        *,
        requesting_user_id: uuid.UUID,
        is_admin: bool,
    ) -> ExplanationResponse:
        recommendation = await self.recommendations.get(recommendation_id)
        if recommendation is None:
            raise NotFoundError("Recommendation", recommendation_id)
        if not is_admin and recommendation.user_id != requesting_user_id:
            raise ForbiddenError("You may only explain your own recommendations")

        evidence = await self._build_evidence(recommendation)
        explanation, grounded, source = await self._generate(evidence, request)
        return ExplanationResponse(
            recommendation_id=recommendation_id,
            kind=request.kind,
            explanation=explanation,
            grounded=grounded,
            source=source,
            evidence=evidence,
        )

    # --- evidence assembly ----------------------------------------------
    async def _build_evidence(self, rec: Recommendation) -> RecommendationEvidence:
        user_id = rec.user_id
        resource = rec.resource
        skill = await self.skills.get(rec.skill_id) if rec.skill_id else None
        skill_name = skill.name if skill else "the target skill"

        current_level = 0.0
        if skill is not None:
            us = await self.user_skills.get_for_user(user_id, skill.id)
            current_level = us.proficiency if us else 0.0

        goal_title, required_level = await self._goal_and_required(user_id, skill)
        skill_gap = max(0.0, round(required_level - current_level, 4))

        prereq_relations = await self._prerequisite_relations(user_id, skill)
        resource_skills = [
            ResourceSkillFact(
                skill=link.skill.name,
                teaches_from=min(1.0, max(0.0, link.teaches_level_from)),
                teaches_to=min(1.0, max(0.0, link.teaches_level_to)),
            )
            for link in (resource.skills if resource else [])
            if link.skill is not None
        ]
        roadmap_position = await self._roadmap_position(user_id, rec.resource_id)
        strengths = await self._strengths(user_id)

        return RecommendationEvidence(
            recommendation_id=rec.id,
            resource_title=resource.title if resource else "the resource",
            resource_type=resource.resource_type.value if resource else "resource",
            resource_difficulty=resource.difficulty if resource else 1,
            learner_skill=skill_name,
            current_level=round(current_level, 4),
            required_level=round(required_level, 4),
            skill_gap=skill_gap,
            prerequisite_relationships=prereq_relations,
            resource_skills=resource_skills,
            goal=goal_title,
            roadmap_position=roadmap_position,
            strengths=strengths,
        )

    async def _goal_and_required(self, user_id: uuid.UUID, skill) -> tuple[str, float]:  # type: ignore[no-untyped-def]
        # Prefer an active goal; use its required level for this skill if present.
        goals = await self.goals.list(
            limit=1,
            filters=[LearningGoal.user_id == user_id],
            order_by=(LearningGoal.priority, LearningGoal.created_at.desc()),
        )
        goal = goals[0] if goals else None
        goal_title = None
        required = _DEFAULT_REQUIRED
        if goal is not None:
            goal_title = goal.target_role or goal.title
            if skill is not None:
                for ts in goal.target_skills:
                    if ts.skill_id == skill.id:
                        required = min(1.0, ts.required_level / _GOAL_LEVEL_SCALE)
                        break
        if goal_title is None:
            profile = await self.profiles.get_by_user(user_id)
            goal_title = (profile.target_role if profile and profile.target_role else "your goal")
        return goal_title, required

    async def _prerequisite_relations(self, user_id: uuid.UUID, skill) -> list[PrerequisiteRelation]:  # type: ignore[no-untyped-def]
        if skill is None:
            return []
        edges = await self.prerequisites.list_prerequisites(skill.id)
        relations: list[PrerequisiteRelation] = []
        for edge in edges:
            prereq = edge.prerequisite_skill
            us = await self.user_skills.get_for_user(user_id, edge.prerequisite_skill_id)
            learner_level = us.proficiency if us else 0.0
            required = min(1.0, edge.min_level / _PREREQ_LEVEL_SCALE)
            relations.append(
                PrerequisiteRelation(
                    skill=prereq.name if prereq else str(edge.prerequisite_skill_id),
                    relationship=edge.relationship_type.value,
                    status="met" if learner_level >= required else "unmet",
                    learner_level=round(learner_level, 4),
                    required_level=round(required, 4),
                )
            )
        return relations

    async def _roadmap_position(
        self, user_id: uuid.UUID, resource_id: uuid.UUID | None
    ) -> RoadmapPosition | None:
        if resource_id is None:
            return None
        path = await self.paths.get_active_for_user(user_id)
        if path is None:
            return None
        items = await self.path_items.list_for_path(path.id)
        match = next((i for i in items if i.resource_id == resource_id), None)
        if match is None:
            return None
        trace = match.rationale_trace or {}
        # skills unlocked = later milestones in the roadmap
        later = [
            i.rationale_trace.get("milestone")
            for i in items
            if i.milestone_index > match.milestone_index and i.rationale_trace.get("milestone")
        ]
        unlocks: list[str] = []
        for name in later:
            if name and name not in unlocks:
                unlocks.append(name)
        return RoadmapPosition(
            phase_index=match.milestone_index,
            phase_title=trace.get("phase_title") or match.milestone_title or "your roadmap",
            milestone=trace.get("milestone") or match.title,
            unlocks=unlocks[:4],
        )

    async def _strengths(self, user_id: uuid.UUID) -> list[str]:
        rows = await self.user_skills.list(
            limit=5,
            filters=[UserSkill.user_id == user_id, UserSkill.proficiency >= _STRENGTH_THRESHOLD],
            order_by=(UserSkill.proficiency.desc(),),
        )
        return [r.skill.name for r in rows if r.skill is not None]

    # --- generation ------------------------------------------------------
    async def _generate(
        self, evidence: RecommendationEvidence, request: ExplanationRequest
    ) -> tuple[str, bool, str]:
        template = render_template(evidence, request.kind)

        if not request.use_llm or self.llm is None:
            return template, True, "template"

        allowed_levels, allowed_terms = self._grounding_allowances(evidence)
        try:
            completion = await self.llm.complete(
                system=_EXPLANATION_SYSTEM_PROMPT,
                user=self._llm_prompt(evidence, request.kind),
                max_tokens=400,
            )
            text = completion.text.strip()
        except LLMError as exc:
            logger.warning("explanation LLM failed; using template", extra={"error": str(exc)[:200]})
            return template, True, "template"

        if not text:
            return template, True, "template"

        result = check_grounding(text, allowed_levels=allowed_levels, allowed_terms=allowed_terms)
        if result.grounded:
            return text, True, "llm"
        logger.warning(
            "explanation failed grounding; using template",
            extra={
                "unsupported_pct": result.unsupported_percentages,
                "unsupported_terms": result.unsupported_terms[:5],
            },
        )
        return template, True, "template"

    @staticmethod
    def _grounding_allowances(
        evidence: RecommendationEvidence,
    ) -> tuple[list[float], list[str]]:
        levels = [evidence.current_level, evidence.required_level, evidence.skill_gap]
        terms = [evidence.learner_skill, evidence.goal, evidence.resource_title, evidence.resource_type]
        for rel in evidence.prerequisite_relationships:
            levels.extend([rel.learner_level, rel.required_level])
            terms.append(rel.skill)
        for rs in evidence.resource_skills:
            levels.extend([rs.teaches_from, rs.teaches_to])
            terms.append(rs.skill)
        terms.extend(evidence.strengths)
        if evidence.roadmap_position:
            terms.append(evidence.roadmap_position.phase_title)
            terms.append(evidence.roadmap_position.milestone)
            terms.extend(evidence.roadmap_position.unlocks)
        return levels, [t for t in terms if t]

    @staticmethod
    def _llm_prompt(evidence: RecommendationEvidence, kind: str) -> str:
        focus = {
            "why_course": "Explain why this course fits the learner right now.",
            "why_now": "Explain why now is (or is not) the right time for this.",
            "why_order": "Explain why this comes in this order relative to prerequisites.",
            "why_project": "Explain why this project is worth doing for the goal.",
            "why_assessment": "Explain why taking this assessment matters before advancing.",
        }.get(kind, "Explain why this was recommended.")
        return (
            f"{focus}\n\nFacts (JSON):\n"
            f"{json.dumps(evidence.model_dump(mode='json'), indent=2)}"
        )
