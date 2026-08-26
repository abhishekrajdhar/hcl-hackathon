"""Deterministic learning-path generator.

Composes the gap engine (ordered, prerequisite-valid milestones), the resource
catalogue, existing skill assessments and the roadmap engine into a persisted
LearningPath. The LLM is never asked to invent the roadmap.

Persistence uses the LearningPath + LearningPathItem tables (so progress
tracking works); the nested phase/milestone view is reconstructed from the
items, which carry their phase/milestone metadata in `rationale_trace` — a
single source of truth.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.engines.path import (
    CapstoneInput,
    GoalInput,
    MilestoneInput,
    PathConstraints,
    ResourcePick,
    Roadmap,
    build_roadmap,
)
from app.models.assessment import Assessment
from app.models.enums import (
    PathItemStatus,
    PathItemType,
    PathStatus,
    ResourceType,
)
from app.models.path import LearningPath, LearningPathItem
from app.models.resource import Resource, ResourceSkill
from app.repositories.assessment import AssessmentRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.resource import ResourceRepository
from app.repositories.user import LearnerProfileRepository, UserRepository
from app.schemas.learning_path import (
    GeneratePathRequest,
    LearningPathRoadmap,
    RoadmapItem,
    RoadmapMilestone,
    RoadmapPhase,
)
from app.schemas.skill_gap import RequiredSkillInput, SkillGapAnalyzeRequest
from app.services.base import BaseService
from app.services.skill_gap_service import SkillGapService
from app.services.skill_resolver import SkillResolver

GENERATOR_VERSION = "path-generator-v1"
#: Resources selected per milestone skill.
_RESOURCES_PER_MILESTONE = 2


class PathGeneratorService(BaseService):
    def __init__(self, session: AsyncSession, llm: "LLMProvider | None" = None) -> None:
        super().__init__(session)
        #: Used only to design role graphs for goals the catalogue cannot name.
        self.llm = llm
        self.gap_service = SkillGapService(session)
        self.resources = ResourceRepository(session)
        self.assessments = AssessmentRepository(session)
        self.paths = LearningPathRepository(session)
        self.path_items = LearningPathItemRepository(session)
        self.profiles = LearnerProfileRepository(session)
        self.users = UserRepository(session)

    # --- generation ------------------------------------------------------
    async def generate(
        self,
        request: GeneratePathRequest,
        *,
        requesting_user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> LearningPathRoadmap:
        target_skills = request.target_skills
        # A learner describes a goal in a sentence, not as a list of skill ids.
        # When nothing explicit was supplied, resolve the goal text against the
        # catalogue and plan toward that skill — the gap engine pulls in its
        # whole prerequisite closure from there, which is the actual roadmap.
        if not target_skills and request.goal_id is None:
            target_skills = await self._targets_from_goal_text(request.goal_text)

        gap_request = SkillGapAnalyzeRequest(
            user_id=request.user_id,
            goal_id=request.goal_id,
            target_skills=target_skills,
        )
        computed = await self.gap_service.compute(
            gap_request, requesting_user_id=requesting_user_id, is_admin=is_admin
        )
        learner_id = computed.user_id or request.user_id
        if not computed.analysis.ranked_gaps:
            raise ValidationError(
                "No skill gaps to plan — the learner already meets this goal",
                error_code="no_gaps",
            )

        profile = await self.profiles.get_by_user(learner_id)
        constraints = self._constraints(request, profile)
        milestones = await self._build_milestones(computed, constraints)
        capstone = await self._build_capstone(request, computed)
        goal = GoalInput(
            title=request.goal_text or "Your learning goal",
            target_role=profile.target_role if profile else None,
        )

        explicit_targets = [
            {"skill_id": str(sid), "required_level": rs.required_level}
            for sid, rs in computed.required.items()
            if rs.is_target
        ]
        roadmap = build_roadmap(milestones, constraints, goal, capstone)
        path = await self._persist(request, learner_id, roadmap, explicit_targets)
        return await self._roadmap_for(path.id, learner_id)

    async def _targets_from_goal_text(self, goal_text: str | None) -> list[RequiredSkillInput]:
        """Any goal phrase -> a target vector, growing the graph when needed.

        Delegated to RoleGraphService: exact catalogue match first, then the
        model designs the role's skill graph (materialised deterministically),
        then the curated nearest-role fallback — a 422 only when every layer
        comes up empty.
        """
        from app.services.role_graph_service import RoleGraphService

        return await RoleGraphService(self.session, self.llm).targets_for_goal(goal_text)

    async def regenerate(
        self,
        path_id: uuid.UUID,
        *,
        requesting_user_id: uuid.UUID,
        is_admin: bool,
        weekly_hours: int | None = None,
        target_deadline: date | None = None,
    ) -> LearningPathRoadmap:
        path = await self.paths.get(path_id)
        if path is None:
            raise NotFoundError("Learning path", path_id)
        if not is_admin and path.user_id != requesting_user_id:
            raise ForbiddenError("You may only regenerate your own learning paths")

        snapshot = path.constraints_snapshot or {}
        request = GeneratePathRequest(
            user_id=path.user_id,
            goal_id=path.goal_id,
            target_skills=[],
            goal_text=snapshot.get("goal_text"),
            weekly_hours=weekly_hours,
            target_deadline=target_deadline,
            activate=path.status == PathStatus.ACTIVE,
        )
        # Reuse the goal's target vector when the path was goal-derived; otherwise
        # fall back to the stored required-skill snapshot.
        if path.goal_id is None:
            request = request.model_copy(
                update={
                    "target_skills": [
                        {"skill_id": s["skill_id"], "required_level": s["required_level"]}
                        for s in snapshot.get("target_skills", [])
                    ]
                }
            )
        new_roadmap = await self.generate(
            request, requesting_user_id=requesting_user_id, is_admin=is_admin
        )
        # Mark the previous path superseded.
        await self.paths.update(
            path, {"status": PathStatus.SUPERSEDED}
        )
        await self.commit()
        return new_roadmap

    # --- input assembly --------------------------------------------------
    @staticmethod
    def _constraints(request: GeneratePathRequest, profile) -> PathConstraints:  # type: ignore[no-untyped-def]
        return PathConstraints(
            weekly_hours=request.weekly_hours or (profile.weekly_hours if profile else 5),
            target_deadline=request.target_deadline
            or (profile.target_deadline if profile else None),
            start_date=date.today(),
            preferred_modalities=tuple(profile.preferred_modalities) if profile else (),
        )

    async def _build_milestones(
        self, computed, constraints: PathConstraints
    ) -> list[MilestoneInput]:
        milestones: list[MilestoneInput] = []
        preferred = set(constraints.preferred_modalities)
        for gap in computed.analysis.ranked_gaps:
            skill = computed.nodes.get(gap.skill_id)
            if skill is None:
                continue
            category_slug = skill.category.slug if skill.category else "general"
            category_name = skill.category.name if skill.category else "Foundations"
            prereq_names = tuple(
                computed.nodes[pid].name
                for pid in gap.prerequisite_ids
                if pid in computed.nodes
            )
            picks = await self._select_resources(gap.skill_id, preferred)
            assessment = await self._select_assessment(gap.skill_id)
            milestones.append(
                MilestoneInput(
                    skill_id=skill.id,
                    skill_slug=skill.slug,
                    skill_name=skill.name,
                    category_slug=category_slug,
                    category_name=category_name,
                    difficulty=skill.difficulty,
                    current_level=gap.current_level,
                    required_level=gap.required_level,
                    gap=gap.gap,
                    layer=gap.level,
                    prerequisite_names=prereq_names,
                    resources=picks,
                    assessment_id=assessment.id if assessment else None,
                    assessment_title=assessment.title if assessment else None,
                )
            )
        return milestones

    async def _select_resources(
        self, skill_id: uuid.UUID, preferred: set[str]
    ) -> tuple[ResourcePick, ...]:
        """Best resources teaching a skill: quality first, preferred modality as a
        tiebreak. Deterministic — a resource that teaches the milestone skill is
        appropriate by the time the learner reaches this phase."""
        candidates = await self.resources.list(
            limit=8,
            filters=[
                Resource.is_active.is_(True),
                ResourceRepository.teaches_skill_filter(skill_id),
                Resource.resource_type != ResourceType.PROJECT,  # projects go in the capstone
            ],
            order_by=(Resource.quality_score.desc().nullslast(), Resource.id),
        )
        ranked = sorted(
            candidates,
            key=lambda r: (
                0 if r.modality.value in preferred else 1,
                -(r.quality_score or 0.0),
                str(r.id),
            ),
        )
        return tuple(
            ResourcePick(
                resource_id=r.id,
                title=r.title,
                estimated_hours=r.estimated_hours,
                modality=r.modality.value,
                difficulty=r.difficulty,
            )
            for r in ranked[:_RESOURCES_PER_MILESTONE]
        )

    async def _select_assessment(self, skill_id: uuid.UUID) -> Assessment | None:
        found = await self.assessments.list(
            limit=1,
            filters=[Assessment.skill_id == skill_id, Assessment.is_active.is_(True)],
            order_by=(Assessment.created_at.desc(),),
        )
        return found[0] if found else None

    async def _build_capstone(self, request: GeneratePathRequest, computed) -> CapstoneInput:
        """A final project. Prefer a real project resource that teaches the
        goal's skills; otherwise synthesise a capstone titled from the goal."""
        gap_ids = [g.skill_id for g in computed.analysis.ranked_gaps]
        project = None
        if gap_ids:
            projects = await self.resources.list(
                limit=1,
                filters=[
                    Resource.is_active.is_(True),
                    Resource.resource_type == ResourceType.PROJECT,
                    Resource.id.in_(
                        ResourceSkill.__table__.select()
                        .with_only_columns(ResourceSkill.resource_id)
                        .where(ResourceSkill.skill_id.in_(gap_ids))
                    ),
                ],
                order_by=(Resource.quality_score.desc().nullslast(), Resource.id),
            )
            project = projects[0] if projects else None

        goal_label = request.goal_text or "your goal"
        skill_names = tuple(
            computed.nodes[g.skill_id].name
            for g in computed.analysis.ranked_gaps[-3:]
            if g.skill_id in computed.nodes
        )
        if project is not None:
            return CapstoneInput(
                title=project.title,
                description=f"Capstone project applying your new skills toward {goal_label}.",
                resource_id=project.id,
                skill_names=skill_names,
                estimated_hours=project.estimated_hours or 20.0,
            )
        return CapstoneInput(
            title=f"Capstone Project: {goal_label}",
            description=f"Design and build a project that demonstrates {goal_label}.",
            resource_id=None,
            skill_names=skill_names,
            estimated_hours=20.0,
        )

    # --- persistence -----------------------------------------------------
    async def _persist(
        self,
        request: GeneratePathRequest,
        learner_id: uuid.UUID,
        roadmap: Roadmap,
        explicit_targets: list[dict],
    ) -> LearningPath:
        version = await self.paths.next_version(learner_id, request.goal_id)
        status = PathStatus.ACTIVE if request.activate else PathStatus.DRAFT
        if request.activate:
            await self._supersede_active(learner_id)

        phase_dates = {p.index: (p.planned_start, p.planned_end) for p in roadmap.phases}
        phase_meta = {
            p.index: {"title": p.title, "objective": p.objective, "is_capstone": p.is_capstone}
            for p in roadmap.phases
        }
        milestone_meta = {
            (m.title): m
            for p in roadmap.phases
            for m in p.milestones
        }

        path = LearningPath(
            user_id=learner_id,
            goal_id=request.goal_id,
            title=f"Roadmap to {request.goal_text or 'your goal'}",
            version=version,
            status=status,
            generator_version=GENERATOR_VERSION,
            total_estimated_minutes=roadmap.total_estimated_minutes,
            constraints_snapshot={
                "goal_text": request.goal_text,
                "target_skills": explicit_targets,
                "feasibility_ok": roadmap.feasibility_ok,
                "feasibility_warning": roadmap.feasibility_warning,
                "suggestions": list(roadmap.suggestions),
                "planned_start": roadmap.planned_start.isoformat() if roadmap.planned_start else None,
                "planned_end": roadmap.planned_end.isoformat() if roadmap.planned_end else None,
            },
        )
        self.paths.add(path)
        await self.session.flush()

        for item in roadmap.items:
            planned_start, planned_end = phase_dates.get(item.phase_index, (None, None))
            milestone = milestone_meta.get(item.rationale.get("milestone", ""))
            item_type = {
                "resource": PathItemType.RESOURCE,
                "assessment": PathItemType.ASSESSMENT,
                "review": PathItemType.MILESTONE_REVIEW,
                "project": PathItemType.RESOURCE
                if item.resource_id is not None
                else PathItemType.MILESTONE_REVIEW,
            }[item.kind]
            trace = {
                **item.rationale,
                **phase_meta.get(item.phase_index, {}),
                "skill_id": str(item.skill_id) if item.skill_id else None,
                "current_level": milestone.current_level if milestone else None,
                "required_level": milestone.required_level if milestone else None,
                "gap": milestone.gap if milestone else None,
                "prerequisites": list(milestone.prerequisites) if milestone else [],
                "completion_criteria": milestone.completion_criteria if milestone else None,
            }
            self.path_items.add(
                LearningPathItem(
                    path_id=path.id,
                    resource_id=item.resource_id,
                    assessment_id=item.assessment_id,
                    order_index=item.order_index,
                    milestone_index=item.phase_index,
                    milestone_title=phase_meta.get(item.phase_index, {}).get("title"),
                    title=item.title,
                    item_type=item_type,
                    status=(
                        PathItemStatus.AVAILABLE
                        if item.phase_index == 0
                        else PathItemStatus.LOCKED
                    ),
                    estimated_minutes=item.estimated_minutes,
                    rationale_trace=trace,
                    planned_start=planned_start,
                    planned_end=planned_end,
                )
            )
        await self.session.flush()
        await self.commit()
        return path

    async def _supersede_active(self, learner_id: uuid.UUID) -> None:
        active = await self.paths.list(
            limit=100,
            filters=[
                LearningPath.user_id == learner_id,
                LearningPath.status == PathStatus.ACTIVE,
            ],
        )
        for path in active:
            path.status = PathStatus.SUPERSEDED
        await self.session.flush()

    # --- reconstruction --------------------------------------------------
    async def get_active_roadmap(
        self, user_id: uuid.UUID, *, requesting_user_id: uuid.UUID, is_admin: bool
    ) -> LearningPathRoadmap:
        if not is_admin and user_id != requesting_user_id:
            raise ForbiddenError("You may only view your own learning path")
        path = await self.paths.get_active_for_user(user_id)
        if path is None:
            raise NotFoundError("Active learning path for this user")
        return await self._roadmap_for(path.id, user_id)

    async def _roadmap_for(self, path_id: uuid.UUID, user_id: uuid.UUID) -> LearningPathRoadmap:
        path = await self.paths.get(path_id)
        assert path is not None
        items = await self.path_items.list_for_path(path_id)

        phases: dict[int, RoadmapPhase] = {}
        milestones: dict[tuple[int, str], RoadmapMilestone] = {}

        for item in items:
            trace = item.rationale_trace or {}
            phase_index = item.milestone_index
            if phase_index not in phases:
                phases[phase_index] = RoadmapPhase(
                    index=phase_index,
                    title=trace.get("phase_title") or item.milestone_title or f"Phase {phase_index + 1}",
                    objective=trace.get("objective", ""),
                    is_capstone=bool(trace.get("is_capstone")),
                    estimated_minutes=0,
                    planned_start=item.planned_start,
                    planned_end=item.planned_end,
                    milestones=[],
                )
            phase = phases[phase_index]
            phase.estimated_minutes += item.estimated_minutes

            milestone_key = (phase_index, trace.get("milestone") or item.title)
            if milestone_key not in milestones:
                milestone = RoadmapMilestone(
                    skill_id=None,
                    skill_slug=trace.get("skill_slug"),
                    title=trace.get("milestone") or item.title,
                    current_level=trace.get("current_level") or 0.0,
                    required_level=trace.get("required_level") or 0.0,
                    gap=trace.get("gap") or 0.0,
                    prerequisites=trace.get("prerequisites", []),
                    completion_criteria=trace.get("completion_criteria") or "",
                    estimated_minutes=0,
                    resources=[],
                    assessment=None,
                    project=None,
                )
                milestones[milestone_key] = milestone
                phase.milestones.append(milestone)
            milestone = milestones[milestone_key]
            milestone.estimated_minutes += item.estimated_minutes

            roadmap_item = RoadmapItem(
                id=item.id,
                kind=trace.get("kind", item.item_type.value),
                title=item.title,
                status=item.status,
                estimated_minutes=item.estimated_minutes,
                resource_id=item.resource_id,
                assessment_id=item.assessment_id,
                is_optional=item.is_optional,
            )
            kind = trace.get("kind")
            if kind == "assessment":
                milestone.assessment = roadmap_item
            elif kind == "project":
                milestone.project = roadmap_item
            else:  # resource or self-study review
                milestone.resources.append(roadmap_item)

        snapshot = path.constraints_snapshot or {}
        return LearningPathRoadmap(
            path_id=path.id,
            user_id=user_id,
            goal_id=path.goal_id,
            title=path.title,
            version=path.version,
            status=path.status,
            generator_version=path.generator_version,
            total_estimated_minutes=path.total_estimated_minutes,
            planned_start=_parse_date(snapshot.get("planned_start")),
            planned_end=_parse_date(snapshot.get("planned_end")),
            feasibility_ok=snapshot.get("feasibility_ok", True),
            feasibility_warning=snapshot.get("feasibility_warning"),
            suggestions=snapshot.get("suggestions", []),
            phases=[phases[i] for i in sorted(phases)],
            created_at=path.created_at,
        )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date() if "T" in value else date.fromisoformat(value)
    except ValueError:
        return None
