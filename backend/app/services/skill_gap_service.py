"""Skill Gap Engine.

Determines which skills a learner must develop to reach a goal, and — using the
prerequisite graph — in what order. Loads the required vector, the learner's
current proficiencies and the hard-prerequisite subgraph, then hands them to the
pure `analyze_gaps` engine. No LLM and no model arithmetic: every number and
every ordering decision is deterministic.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.engines.skill_gap import GapAnalysis, RankedGap, RequiredSkill, analyze_gaps
from app.engines.skill_graph import GraphEdge, GraphNode, SkillGraph
from app.engines.skill_graph.graph import MAX_TRAVERSAL_DEPTH
from app.models.enums import RelationshipType
from app.models.skill import Skill, UserSkill
from app.repositories.goal import LearningGoalRepository
from app.repositories.skill import (
    PrerequisiteRepository,
    SkillRepository,
    UserSkillRepository,
)
from app.schemas.skill_gap import (
    CurrentSkillInput,
    RequiredSkillInput,
    SkillGapAnalyzeRequest,
    SkillGapAnalyzeResponse,
    SkillGapItem,
    SkillRef,
)
from app.services.base import BaseService

#: Only hard prerequisites gate a learning order ("must be learned first").
_HARD_ONLY = frozenset({RelationshipType.HARD_PREREQUISITE})


@dataclass(frozen=True, slots=True)
class GapComputation:
    """Raw output of a gap computation, before API-response mapping."""

    analysis: GapAnalysis
    nodes: dict[uuid.UUID, Skill]
    user_id: uuid.UUID | None
    required: Mapping[uuid.UUID, RequiredSkill]
    current: dict[uuid.UUID, float]
#: LearningGoalSkill.required_level is on a 0..10 scale; the gap engine uses 0..1.
_GOAL_LEVEL_SCALE = 10.0


class SkillGapService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.skills = SkillRepository(session)
        self.user_skills = UserSkillRepository(session)
        self.prerequisites = PrerequisiteRepository(session)
        self.goals = LearningGoalRepository(session)

    # --- public engine methods -------------------------------------------
    @staticmethod
    def calculate_skill_gaps(
        required: Mapping[uuid.UUID, RequiredSkill],
        current: Mapping[uuid.UUID, float],
        *,
        min_gap: float = 0.0,
    ) -> dict[uuid.UUID, float]:
        """Raw gaps: required - current, keeping only positive gaps.

        Pure and graph-free — the first, deterministic step. `gap <= 0` skills
        are dropped (already met), matching the spec.
        """
        gaps: dict[uuid.UUID, float] = {}
        for skill_id, req in required.items():
            gap = req.required_level - current.get(skill_id, 0.0)
            if gap > min_gap:
                gaps[skill_id] = round(gap, 6)
        return gaps

    def resolve_prerequisites(
        self,
        required: Mapping[uuid.UUID, RequiredSkill],
        current: Mapping[uuid.UUID, float],
        graph: SkillGraph,
    ) -> list[uuid.UUID]:
        """Prerequisite-aware learning order over the gap set.

        Returns the skill ids in the order they should be learned — every
        prerequisite before the skills that depend on it.
        """
        return [g.skill_id for g in self.rank_skill_gaps(required, current, graph).ranked_gaps]

    def rank_skill_gaps(
        self,
        required: Mapping[uuid.UUID, RequiredSkill],
        current: Mapping[uuid.UUID, float],
        graph: SkillGraph,
    ) -> GapAnalysis:
        """Full prioritised, prerequisite-ordered gap analysis."""
        return analyze_gaps(required, current, graph)

    @staticmethod
    def get_priority_skills(analysis: GapAnalysis, *, top_k: int = 10) -> list[uuid.UUID]:
        """The highest-priority skills that can be started right now."""
        return list(analysis.priority_skill_ids[:top_k])

    # --- orchestration ---------------------------------------------------
    async def compute(
        self,
        request: SkillGapAnalyzeRequest,
        *,
        requesting_user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> "GapComputation":
        """Load inputs and run the engine, returning the raw analysis + context.

        Shared by `analyze` (which maps it to the API response) and the
        recommendation engine (which reuses the gaps and proficiencies directly).
        """
        required, current, effective_user_id = await self._load_required_and_current(
            request, requesting_user_id=requesting_user_id, is_admin=is_admin
        )
        if not required:
            raise ValidationError(
                "No target skills could be resolved for analysis",
                error_code="no_target_skills",
            )
        graph, nodes = await self._load_graph(required.keys())
        analysis = self.rank_skill_gaps(required, current, graph)
        return GapComputation(
            analysis=analysis,
            nodes=nodes,
            user_id=effective_user_id,
            required=required,
            current=dict(current),
        )

    async def analyze(
        self,
        request: SkillGapAnalyzeRequest,
        *,
        requesting_user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> SkillGapAnalyzeResponse:
        computed = await self.compute(
            request, requesting_user_id=requesting_user_id, is_admin=is_admin
        )
        priority_ids = self.get_priority_skills(computed.analysis, top_k=request.top_k)
        return self._to_response(
            computed.analysis,
            nodes=computed.nodes,
            priority_ids=priority_ids,
            user_id=computed.user_id,
            goal_id=request.goal_id,
        )

    # --- input loading ---------------------------------------------------
    async def _load_required_and_current(
        self,
        request: SkillGapAnalyzeRequest,
        *,
        requesting_user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> tuple[dict[uuid.UUID, RequiredSkill], dict[uuid.UUID, float], uuid.UUID | None]:
        required: dict[uuid.UUID, RequiredSkill] = {}

        def _authorize(owner_id: uuid.UUID) -> None:
            # Reading another learner's current skills requires self or admin;
            # enforced BEFORE any of that learner's data is loaded.
            if not is_admin and requesting_user_id is not None and owner_id != requesting_user_id:
                raise ForbiddenError("You may only analyse your own skill gaps")

        # Required from a goal's target vector (0..10 -> 0..1).
        effective_user_id = request.user_id
        if effective_user_id is not None:
            _authorize(effective_user_id)
        if request.goal_id is not None:
            goal = await self.goals.get(request.goal_id)
            if goal is None:
                raise NotFoundError("Learning goal", request.goal_id)
            _authorize(goal.user_id)
            effective_user_id = effective_user_id or goal.user_id
            for entry in goal.target_skills:
                required[entry.skill_id] = RequiredSkill(
                    required_level=min(1.0, entry.required_level / _GOAL_LEVEL_SCALE),
                    importance=entry.importance,
                    is_target=True,
                )

        # Explicit required skills override/supplement the goal.
        for item in request.target_skills:
            skill_id = await self._resolve_skill_id(item)
            required[skill_id] = RequiredSkill(
                required_level=item.required_level, importance=item.importance, is_target=True
            )

        # Current proficiencies: from the user, then explicit overrides.
        current: dict[uuid.UUID, float] = {}
        if effective_user_id is not None:
            rows = await self.user_skills.list(
                limit=1000, filters=[UserSkill.user_id == effective_user_id]
            )
            current = {us.skill_id: us.proficiency for us in rows}
        for item in request.current_skills:
            skill_id = await self._resolve_skill_id(item)
            current[skill_id] = item.current_level

        return required, current, effective_user_id

    async def _resolve_skill_id(
        self, item: RequiredSkillInput | CurrentSkillInput
    ) -> uuid.UUID:
        if item.skill_id is not None:
            if await self.skills.get(item.skill_id) is None:
                raise NotFoundError("Skill", item.skill_id)
            return item.skill_id
        skill = await self.skills.get_by_slug(item.skill_slug)  # type: ignore[arg-type]
        if skill is None:
            raise NotFoundError("Skill", item.skill_slug)
        return skill.id

    async def _load_graph(
        self, required_ids
    ) -> tuple[SkillGraph, dict[uuid.UUID, Skill]]:
        """Load the required skills plus their transitive hard prerequisites."""
        roots = list(required_ids)
        ancestor_depths = await self.prerequisites.ancestor_ids(roots, MAX_TRAVERSAL_DEPTH)
        node_ids = set(roots) | set(ancestor_depths)

        skills = {s.id: s for s in await self.skills.get_many(sorted(node_ids))}
        edges = await self.prerequisites.edges_within(sorted(node_ids))

        graph = SkillGraph(
            (
                GraphNode(
                    id=s.id,
                    slug=s.slug,
                    name=s.name,
                    difficulty=s.difficulty,
                    category_slug=s.category.slug if s.category is not None else None,
                )
                for s in skills.values()
            ),
            (
                GraphEdge(
                    source_id=e.source_skill_id,
                    prerequisite_id=e.prerequisite_skill_id,
                    relationship_type=e.relationship_type,
                    strength=e.strength,
                    min_level=e.min_level,
                )
                for e in edges
                if e.relationship_type in _HARD_ONLY
            ),
        )
        return graph, skills

    # --- response mapping ------------------------------------------------
    @staticmethod
    def _ref(nodes: dict[uuid.UUID, Skill], skill_id: uuid.UUID) -> SkillRef:
        skill = nodes.get(skill_id)
        if skill is None:  # defensive; should not happen for graph nodes
            return SkillRef(id=skill_id, slug=str(skill_id), name=str(skill_id))
        return SkillRef(id=skill.id, slug=skill.slug, name=skill.name)

    def _to_response(
        self,
        analysis: GapAnalysis,
        *,
        nodes: dict[uuid.UUID, Skill],
        priority_ids: list[uuid.UUID],
        user_id: uuid.UUID | None,
        goal_id: uuid.UUID | None,
    ) -> SkillGapAnalyzeResponse:
        gaps = [self._to_item(g, nodes) for g in analysis.ranked_gaps]
        return SkillGapAnalyzeResponse(
            user_id=user_id,
            goal_id=goal_id,
            total_gaps=len(gaps),
            gaps=gaps,
            priority_skills=[self._ref(nodes, sid) for sid in priority_ids],
            met_targets=[self._ref(nodes, sid) for sid in analysis.met_target_ids],
            unknown_skills=[str(sid) for sid in analysis.unknown_skill_ids],
        )

    def _to_item(self, gap: RankedGap, nodes: dict[uuid.UUID, Skill]) -> SkillGapItem:
        return SkillGapItem(
            skill=self._ref(nodes, gap.skill_id),
            current_level=gap.current_level,
            required_level=gap.required_level,
            gap=gap.gap,
            prerequisites=[self._ref(nodes, pid) for pid in gap.prerequisite_ids],
            priority=gap.priority,
            rank=gap.rank,
            level=gap.level,
            is_target=gap.is_target,
            importance=gap.importance,
            downstream_count=gap.downstream_count,
            reason=gap.reason,
        )
