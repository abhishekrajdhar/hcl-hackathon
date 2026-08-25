"""Tool abstractions for the learning assistant.

Each tool wraps an application service and returns a structured `ToolResult`.
These tools are the ONLY way the assistant reads or writes application state, so
the LLM can never invent a skill level, a completed course, a recommendation or
a roadmap milestone — it only ever sees what a tool actually returned. When the
data does not exist, the tool says so (`available=False`) and the assistant
relays that rather than guessing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.embeddings.base import EmbeddingProvider
from app.models.enums import PathItemStatus
from app.repositories.recommendation import RecommendationRepository
from app.schemas.adaptive import AdaptiveUpdateRequest, ExplicitSkillScore
from app.services.adaptive_service import AdaptiveLearningService
from app.services.path_generator_service import PathGeneratorService
from app.services.profile_service import ProfileService
from app.services.progress_service import ProgressService
from app.services.search_service import SemanticSearchService
from app.services.skill_graph_service import SkillGraphService
from app.services.skill_resolver import SkillResolver

#: Tool catalogue (name -> one-line description), exposed for the system prompt.
TOOL_DESCRIPTIONS: dict[str, str] = {
    "get_learner_profile": "The learner's profile: goal, role, weekly hours, and recorded skills.",
    "get_skill_gaps": "Which skills still need work to reach the goal, with current vs required level.",
    "get_current_learning_path": "The active roadmap: phases, milestones and their status.",
    "get_recommendations": "The learner's current recommended resources.",
    "get_progress": "Progress summary: items completed, time spent, completion percentage.",
    "get_next_action": "The single next step the learner should take.",
    "search_resources": "Search the catalogue for resources relevant to a query.",
    "update_learning_progress": "Record a completed resource or an assessment score and adapt the path.",
    "get_goal_prerequisites": "Direct prerequisites of the learner's goal skill, split into met and unknown.",
}


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    available: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


class ChatToolExecutor:
    """Runs a named tool against the real services for one learner."""

    def __init__(
        self, session: AsyncSession, user_id: uuid.UUID, embedding_provider: EmbeddingProvider
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.provider = embedding_provider

    # --- 1 ---------------------------------------------------------------
    async def get_learner_profile(self) -> ToolResult:
        try:
            full = await ProfileService(self.session).get_full_profile(self.user_id)
        except AppError:
            return ToolResult("get_learner_profile", False,
                              "No learner profile has been created yet.")
        p = full.profile
        top = sorted(full.skills, key=lambda s: -s.proficiency)[:5]
        return ToolResult(
            "get_learner_profile", True,
            f"Goal: {p.target_role or p.goal_text_raw or 'not set'}; "
            f"experience: {p.experience_level.value}; weekly hours: {p.weekly_hours}; "
            f"{full.skill_count} skills recorded.",
            {
                "goal": p.goal_text_raw,
                "target_role": p.target_role,
                "experience_level": p.experience_level.value,
                "weekly_hours": p.weekly_hours,
                "interests": p.interests,
                "skill_count": full.skill_count,
                "top_skills": [
                    {"skill": s.skill.name if s.skill else None, "proficiency": s.proficiency}
                    for s in top
                ],
                "assessment_attempts": full.assessment_history.total_attempts,
            },
        )

    # --- 2 ---------------------------------------------------------------
    async def get_skill_gaps(self) -> ToolResult:
        roadmap = await self._active_roadmap()
        if roadmap is None:
            return ToolResult("get_skill_gaps", False,
                              "No active learning path, so there are no computed skill gaps yet.")
        gaps = [
            {"skill": m.title, "current_level": m.current_level,
             "required_level": m.required_level, "gap": m.gap}
            for phase in roadmap.phases if not phase.is_capstone
            for m in phase.milestones if m.gap > 0 and m.skill_slug
        ]
        if not gaps:
            return ToolResult("get_skill_gaps", True, "No remaining skill gaps — every target is met.",
                              {"gaps": []})
        return ToolResult(
            "get_skill_gaps", True,
            f"{len(gaps)} skill gap(s), starting with {gaps[0]['skill']}.",
            {"gaps": gaps},
        )

    # --- 3 ---------------------------------------------------------------
    async def get_current_learning_path(self) -> ToolResult:
        roadmap = await self._active_roadmap()
        if roadmap is None:
            return ToolResult("get_current_learning_path", False,
                              "No active learning path. Set a goal to generate one.")
        phases = [
            {"phase": p.title, "is_capstone": p.is_capstone,
             "milestones": [m.title for m in p.milestones]}
            for p in roadmap.phases
        ]
        return ToolResult(
            "get_current_learning_path", True,
            f"Active roadmap '{roadmap.title}' with {len(phases)} phases "
            f"({roadmap.total_estimated_minutes // 60}h total).",
            {"title": roadmap.title, "phases": phases,
             "total_hours": roadmap.total_estimated_minutes // 60,
             "feasibility_ok": roadmap.feasibility_ok},
        )

    # --- 4 ---------------------------------------------------------------
    async def get_recommendations(self) -> ToolResult:
        items = await RecommendationRepository(self.session).list_pending_for_user(
            self.user_id, limit=10
        )
        if not items:
            return ToolResult("get_recommendations", False,
                              "No recommendations have been generated yet.")
        data = [
            {"title": r.resource.title if r.resource else None, "score": r.score,
             "reason": r.reason}
            for r in items
        ]
        return ToolResult("get_recommendations", True,
                          f"{len(data)} recommended resource(s).", {"recommendations": data})

    # --- 5 ---------------------------------------------------------------
    async def get_progress(self) -> ToolResult:
        summary = await ProgressService(self.session).summary(self.user_id)
        return ToolResult(
            "get_progress", True,
            f"{summary.active_path_completed_items}/{summary.active_path_total_items} items "
            f"completed ({summary.completion_pct:.0f}%), {summary.total_time_minutes // 60}h spent.",
            {
                "items_completed": summary.active_path_completed_items,
                "items_total": summary.active_path_total_items,
                "completion_pct": summary.completion_pct,
                "total_time_hours": summary.total_time_minutes // 60,
            },
        )

    # --- 6 ---------------------------------------------------------------
    async def get_next_action(self) -> ToolResult:
        roadmap = await self._active_roadmap()
        if roadmap is None:
            return ToolResult("get_next_action", False,
                              "No active path yet — set a goal and I'll build your roadmap.")
        for phase in roadmap.phases:
            for m in phase.milestones:
                for item in (*m.resources, *( [m.assessment] if m.assessment else [] ),
                             *( [m.project] if m.project else [] )):
                    if item and item.status in (PathItemStatus.AVAILABLE, PathItemStatus.IN_PROGRESS):
                        return ToolResult(
                            "get_next_action", True,
                            f"Next: {item.title} ({item.kind}) in the {phase.title} phase.",
                            {"title": item.title, "kind": item.kind, "phase": phase.title,
                             "milestone": m.title, "estimated_minutes": item.estimated_minutes},
                        )
        return ToolResult("get_next_action", True,
                          "Everything currently available is done — great work!", {})

    # --- 7 ---------------------------------------------------------------
    async def search_resources(self, query: str, *, top_k: int = 5) -> ToolResult:
        if not query:
            return ToolResult("search_resources", False, "No search topic was provided.")
        scored = await SemanticSearchService(self.session, self.provider).semantic_search(
            query, top_k=top_k
        )
        if not scored:
            return ToolResult("search_resources", True,
                              f"No resources found for '{query}'.", {"query": query, "results": []})
        results = [
            {"title": s.resource.title, "type": s.resource.resource_type.value,
             "similarity": s.similarity}
            for s in scored
        ]
        return ToolResult("search_resources", True,
                          f"Found {len(results)} resource(s) for '{query}'.",
                          {"query": query, "results": results})

    # --- 8 ---------------------------------------------------------------
    async def update_learning_progress(
        self, *, resource_ref: str | None = None, score: float | None = None
    ) -> ToolResult:
        adaptive = AdaptiveLearningService(self.session)
        if score is not None:
            skill_id = await self._current_milestone_skill()
            if skill_id is None:
                return ToolResult("update_learning_progress", False,
                                  "I couldn't tell which skill that score is for — "
                                  "which assessment did you take?")
            result = await adaptive.update(
                AdaptiveUpdateRequest(
                    user_id=self.user_id,
                    skill_scores=[ExplicitSkillScore(skill_id=skill_id, score=score)],
                ),
                requesting_user_id=self.user_id, is_admin=False,
            )
            return self._adaptive_result("update_learning_progress", result, f"score {score:.0%}")

        if resource_ref:
            resource_id = await self._resolve_path_resource(resource_ref)
            if resource_id is None:
                return ToolResult("update_learning_progress", False,
                                  f"I couldn't find '{resource_ref}' in your learning path.")
            result = await adaptive.update(
                AdaptiveUpdateRequest(user_id=self.user_id, completed_resource_id=resource_id),
                requesting_user_id=self.user_id, is_admin=False,
            )
            return self._adaptive_result("update_learning_progress", result, f"completed {resource_ref}")

        return ToolResult("update_learning_progress", False,
                          "Tell me what you completed or the score you got.")

    # --- helpers ---------------------------------------------------------
    # --- 9 ---------------------------------------------------------------
    async def get_goal_prerequisites(self) -> ToolResult:
        """What the learner's goal rests on, and which of it is still unknown.

        The goal is stored as free text ("machine learning engineer"), so it is
        resolved to a catalogue skill first. A role that does not resolve
        confidently yields `available=False` — the assistant then simply does
        not ask a prerequisite question, rather than inventing one about a
        skill the graph never confirmed.
        """
        try:
            profile = await ProfileService(self.session).get_for_user(self.user_id)
        except AppError:
            return ToolResult("get_goal_prerequisites", False, "No learner profile yet.")
        goal_text = (profile.target_role or profile.goal_text_raw or "").strip()
        if not goal_text:
            return ToolResult("get_goal_prerequisites", False, "No goal recorded yet.")

        resolution = await SkillResolver(self.session).resolve(goal_text)
        if resolution.status != "matched" or resolution.skill is None:
            return ToolResult(
                "get_goal_prerequisites", False,
                f"'{goal_text}' does not map onto a single catalogue skill.",
            )

        goal_skill = resolution.skill
        edges = await SkillGraphService(self.session).get_prerequisites(goal_skill.id)
        if not edges:
            return ToolResult(
                "get_goal_prerequisites", True,
                f"{goal_skill.name} has no prerequisites.",
                {"goal_skill": goal_skill.name, "met": [], "unknown": []},
            )

        # `list_skills` returns the canonical [0, 1] proficiency, which is the
        # scale every band in the app is expressed in.
        recorded = {
            us.skill_id: us.proficiency
            for us in (await ProfileService(self.session).list_skills(self.user_id))
        }

        met: list[dict[str, Any]] = []
        unknown: list[dict[str, Any]] = []
        for edge in edges:
            skill = edge.prerequisite_skill
            if skill is None:
                continue
            entry = {
                "skill": skill.name,
                "slug": skill.slug,
                "required": edge.relationship_type.value == "hard_prerequisite",
            }
            if edge.prerequisite_skill_id in recorded:
                entry["level"] = recorded[edge.prerequisite_skill_id]
                met.append(entry)
            else:
                unknown.append(entry)

        # Hard prerequisites first: those are the ones that actually gate the goal.
        unknown.sort(key=lambda e: (not e["required"], e["skill"]))
        summary = (
            f"{goal_skill.name} rests on {len(edges)} prerequisite(s); "
            f"{len(met)} recorded, {len(unknown)} not yet known."
        )
        return ToolResult(
            "get_goal_prerequisites", True, summary,
            {"goal_skill": goal_skill.name, "met": met, "unknown": unknown},
        )

    async def _active_roadmap(self):  # type: ignore[no-untyped-def]
        try:
            return await PathGeneratorService(self.session).get_active_roadmap(
                self.user_id, requesting_user_id=self.user_id, is_admin=False
            )
        except AppError:
            return None

    async def _resolve_path_resource(self, ref: str) -> uuid.UUID | None:
        roadmap = await self._active_roadmap()
        if roadmap is None:
            return None
        needle = ref.lower().replace(" course", "").replace(" resource", "").strip()
        for phase in roadmap.phases:
            for m in phase.milestones:
                for item in (*m.resources, *( [m.project] if m.project else [] )):
                    if item and item.resource_id and needle in item.title.lower():
                        return item.resource_id
        return None

    async def _current_milestone_skill(self) -> uuid.UUID | None:
        """The skill of the first not-yet-completed milestone (what a score maps to)."""
        from app.repositories.path import (
            LearningPathItemRepository,
            LearningPathRepository,
        )

        path = await LearningPathRepository(self.session).get_active_for_user(self.user_id)
        if path is None:
            return None
        items = await LearningPathItemRepository(self.session).list_for_path(path.id)
        for item in sorted(items, key=lambda i: i.order_index):
            if item.status in (PathItemStatus.AVAILABLE, PathItemStatus.IN_PROGRESS):
                raw = (item.rationale_trace or {}).get("skill_id")
                if raw:
                    try:
                        return uuid.UUID(str(raw))
                    except (ValueError, TypeError):
                        return None
        return None

    @staticmethod
    def _adaptive_result(name: str, result, what: str) -> ToolResult:  # type: ignore[no-untyped-def]
        return ToolResult(
            name, True,
            f"Recorded {what}. Updated {len(result.updated_skills)} skill(s); "
            f"unlocked {len(result.unlocked_milestones)} milestone(s).",
            {
                "updated_skills": [
                    {"skill": s.skill_name, "previous": s.previous_proficiency,
                     "new": s.new_proficiency, "mastery": s.mastery_level}
                    for s in result.updated_skills
                ],
                "unlocked_milestones": [m.title for m in result.unlocked_milestones],
                "completed_milestones": [m.title for m in result.completed_milestones],
                "newly_recommended": [r.title for r in result.newly_recommended_resources],
                "next_action": result.next_recommended_action,
            },
        )
