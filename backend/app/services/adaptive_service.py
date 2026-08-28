"""Adaptive Learning Engine.

Runs the deterministic pipeline the spec describes after a learner event:

    User Progress -> Update Skill -> Recalculate Skill Gaps
                  -> Recalculate Recommendations -> Update Learning Path
                  -> Generate Next Action

Every step is deterministic (the SkillProficiencyUpdater formula and fixed
threshold decisions); no LLM is involved. The learner's active path is mutated
in place — milestones complete/unlock, introductory resources are skipped once a
skill is strong, and remediation resources are inserted when a score is low.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.engines.adaptive import (
    decide,
    recover_previous,
    update_from_assessment,
    update_from_completion,
)
from app.engines.assessment import mastery_level
from app.engines.profile import assessment_skill_scores, proficiency_to_level
from app.models.enums import EvidenceSource, PathItemStatus, PathItemType, ProgressEventType
from app.models.path import LearningPath, LearningPathItem
from app.models.progress import UserProgress
from app.models.resource import Resource
from app.models.skill import Skill, UserSkill
from app.repositories.assessment import AssessmentResultRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.resource import ResourceRepository
from app.repositories.skill import (
    PrerequisiteRepository,
    SkillRepository,
    UserSkillRepository,
)
from app.repositories.user import UserRepository
from app.schemas.adaptive import (
    AdaptiveUpdateRequest,
    AdaptiveUpdateResponse,
    MilestoneRead,
    ResourceItemRead,
    UpdatedSkillRead,
)
from app.services.base import BaseService
from app.services.path_unlock import unlock_if_exhausted

_INTRO_DIFFICULTY = 2  # resources at/below this difficulty count as introductory
_MAX_REMEDIATION = 2


@dataclass
class _SkillChange:
    skill_id: uuid.UUID
    previous: float
    new: float
    score: float | None


class AdaptiveLearningService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.users = UserRepository(session)
        self.skills = SkillRepository(session)
        self.user_skills = UserSkillRepository(session)
        self.prerequisites = PrerequisiteRepository(session)
        self.resources = ResourceRepository(session)
        self.results = AssessmentResultRepository(session)
        self.paths = LearningPathRepository(session)
        self.path_items = LearningPathItemRepository(session)

    async def update(
        self,
        request: AdaptiveUpdateRequest,
        *,
        requesting_user_id: uuid.UUID,
        is_admin: bool,
    ) -> AdaptiveUpdateResponse:
        if not is_admin and request.user_id != requesting_user_id:
            raise ForbiddenError("You may only adapt your own learning path")
        if await self.users.get(request.user_id) is None:
            raise NotFoundError("User", request.user_id)

        # 1) ingest the event and update skills deterministically
        trigger, changes, completed_resource_id, skipped_resource_id = await self._apply_event(
            request
        )

        # load the active path once; all path mutations happen on it
        path = await self.paths.get_active_for_user(request.user_id)
        items = await self.path_items.list_for_path(path.id) if path else []
        status_before = {i.id: i.status for i in items}

        completed: list[MilestoneRead] = []
        unlocked: list[MilestoneRead] = []
        removed: list[ResourceItemRead] = []
        newly_recommended: list[ResourceItemRead] = []

        # 2) mark a completed/skipped resource on the path
        if completed_resource_id is not None:
            self._complete_item(items, completed_resource_id)
        if request.completed_item_id is not None:
            self._complete_item_by_id(items, request.completed_item_id)
        if skipped_resource_id is not None:
            skipped = self._skip_item(items, skipped_resource_id)
            if skipped is not None:
                removed.append(skipped)

        # 3) apply the threshold decisions per updated skill
        updated_skills: list[UpdatedSkillRead] = []
        skill_names = {
            s.id: s for s in await self.skills.get_many([c.skill_id for c in changes])
        }
        for change in changes:
            skill = skill_names.get(change.skill_id)
            decision = decide(change.new, change.score)
            updated_skills.append(
                UpdatedSkillRead(
                    skill_id=change.skill_id,
                    skill_name=skill.name if skill else None,
                    previous_proficiency=round(change.previous, 4),
                    new_proficiency=round(change.new, 4),
                    delta=round(change.new - change.previous, 4),
                    mastery_level=mastery_level(change.score if change.score is not None else change.new),
                    level_band=decision.band,
                )
            )
            if path is not None:
                completed += self._complete_milestone(items, change)
                if decision.skip_introductory:
                    removed += self._skip_introductory(items, change.skill_id)
                if decision.unlock_next_milestone:
                    unlocked += self._unlock_next(items)
                # Remediation is inserted only on HARD evidence — a failed
                # assessment. A completion at a low recorded level used to
                # qualify too (recommend_remedial), which meant finishing a
                # course could grow the very phase just finished; a planned
                # roadmap stays as planned until a score proves it shouldn't.
                if decision.insert_remediation:
                    newly_recommended += await self._insert_remediation(
                        path, items, change.skill_id
                    )

        # 3b) Material exhaustion. A strong assessment score is the fast
        # unlock above; this is the safety net — with every actionable item
        # completed or skipped, the next milestone opens anyway, because a
        # milestone without an assessment must never dead-end the roadmap.
        if path is not None and not unlocked:
            for item in unlock_if_exhausted(items):
                unlocked.append(
                    MilestoneRead(
                        skill_id=self._item_skill_id(item),
                        title=(item.rationale_trace or {}).get("milestone") or item.title,
                        phase_title=(item.rationale_trace or {}).get("phase_title") or "",
                        phase_index=item.milestone_index,
                    )
                )

        # 3c) Progress is event-sourced: every summary derives from the event
        # log, so a status the adaptive engine changes without an event is a
        # completion the dashboard can never see. Append one per transition.
        self._record_events(request, trigger, items, status_before)

        # 4) recalculate the path total and persist everything
        if path is not None:
            path.total_estimated_minutes = sum(i.estimated_minutes for i in items)
        await self.session.flush()
        await self.commit()

        # 5) next action
        next_action = self._next_action(updated_skills, unlocked, removed, newly_recommended)

        return AdaptiveUpdateResponse(
            user_id=request.user_id,
            trigger=trigger,
            updated_skills=updated_skills,
            completed_milestones=_dedupe_milestones(completed),
            unlocked_milestones=_dedupe_milestones(unlocked),
            removed_resources=removed,
            newly_recommended_resources=newly_recommended,
            next_recommended_action=next_action,
        )

    # --- 1) event ingestion / skill update ------------------------------
    async def _apply_event(
        self, request: AdaptiveUpdateRequest
    ) -> tuple[str, list[_SkillChange], uuid.UUID | None, uuid.UUID | None]:
        if request.assessment_result_id is not None:
            changes = await self._from_assessment(request)
            return "assessment", changes, None, None
        if request.completed_resource_id is not None:
            changes = await self._from_completion(request.user_id, request.completed_resource_id)
            return "resource_completed", changes, request.completed_resource_id, None
        if request.completed_item_id is not None:
            # A path item with no resource behind it (self-study review, in-app
            # project). Completing it is real progress on the path but weak
            # evidence about the skill — the item completes, the milestone and
            # unlock cascade run, and proficiency is left to assessments.
            return "item_completed", [], None, None
        if request.skipped_resource_id is not None:
            return "resource_skipped", [], None, request.skipped_resource_id
        changes = await self._from_explicit(request)
        return "explicit", changes, None, None

    async def _from_assessment(self, request: AdaptiveUpdateRequest) -> list[_SkillChange]:
        result = await self.results.get(request.assessment_result_id)
        if result is None or result.user_id != request.user_id:
            raise NotFoundError("Assessment result", request.assessment_result_id)
        # Proficiency was already applied at submission; recover the pre-state
        # from the (deterministic) formula so we report an exact delta without
        # updating twice.
        scores = assessment_skill_scores(result.responses)
        changes: list[_SkillChange] = []
        for score in scores:
            entry = await self.user_skills.get_for_user(request.user_id, score.skill_id)
            current = entry.proficiency if entry else update_from_assessment(0.0, score.ratio)
            previous = recover_previous(current, score.ratio)
            changes.append(_SkillChange(score.skill_id, previous, current, score.ratio))
        return changes

    async def _from_completion(
        self, user_id: uuid.UUID, resource_id: uuid.UUID
    ) -> list[_SkillChange]:
        resources = await self.resources.get_many([resource_id])
        if not resources:
            raise NotFoundError("Resource", resource_id)
        resource = resources[0]
        changes: list[_SkillChange] = []
        for link in resource.skills:
            previous, new = await self._write_update(
                user_id, link.skill_id, update_from_completion, link.teaches_level_to,
                source=EvidenceSource.COMPLETION,
            )
            changes.append(_SkillChange(link.skill_id, previous, new, None))
        return changes

    async def _from_explicit(self, request: AdaptiveUpdateRequest) -> list[_SkillChange]:
        changes: list[_SkillChange] = []
        for item in request.skill_scores:
            skill = await self._resolve_skill(item.skill_id, item.skill_slug)
            previous, new = await self._write_update(
                request.user_id, skill.id, update_from_assessment, item.score,
                source=EvidenceSource.ASSESSMENT,
            )
            changes.append(_SkillChange(skill.id, previous, new, item.score))
        return changes

    async def _write_update(
        self, user_id: uuid.UUID, skill_id: uuid.UUID, fn, arg: float, *, source
    ) -> tuple[float, float]:  # type: ignore[no-untyped-def]
        skill = await self.skills.get(skill_id)
        if skill is None:
            raise NotFoundError("Skill", skill_id)
        entry = await self.user_skills.get_for_user(user_id, skill_id)
        previous = entry.proficiency if entry else 0.0
        new = fn(previous, arg)
        if entry is None:
            self.session.add(
                UserSkill(
                    user_id=user_id, skill_id=skill_id, proficiency=new,
                    current_level=proficiency_to_level(new, skill.level_scale),
                    confidence=0.5, evidence_source=source,
                )
            )
        else:
            entry.proficiency = new
            entry.current_level = proficiency_to_level(new, skill.level_scale)
            entry.evidence_source = source
        await self.session.flush()
        return previous, new

    async def _resolve_skill(self, skill_id, skill_slug) -> Skill:  # type: ignore[no-untyped-def]
        if skill_id is not None:
            skill = await self.skills.get(skill_id)
        else:
            skill = await self.skills.get_by_slug(skill_slug)
        if skill is None:
            raise NotFoundError("Skill", skill_id or skill_slug)
        return skill

    # --- 4) path mutations ----------------------------------------------
    @staticmethod
    def _complete_item(items: list[LearningPathItem], resource_id: uuid.UUID) -> None:
        for item in items:
            if item.resource_id == resource_id and item.status != PathItemStatus.COMPLETED:
                item.status = PathItemStatus.COMPLETED

    def _record_events(
        self,
        request: AdaptiveUpdateRequest,
        trigger: str,
        items: list[LearningPathItem],
        status_before: dict[uuid.UUID, PathItemStatus],
    ) -> None:
        for item in items:
            if item.id not in status_before or status_before[item.id] == item.status:
                continue
            if item.status == PathItemStatus.COMPLETED:
                event_type, pct = ProgressEventType.COMPLETED, 100.0
            elif item.status == PathItemStatus.SKIPPED:
                event_type, pct = ProgressEventType.SKIPPED, 0.0
            else:
                continue
            # Reported time belongs to the item the learner actually acted on,
            # not to items a milestone cascade completed alongside it.
            explicit = (
                item.id == request.completed_item_id
                or (item.resource_id is not None
                    and item.resource_id == request.completed_resource_id)
            )
            self.session.add(
                UserProgress(
                    user_id=request.user_id,
                    path_item_id=item.id,
                    resource_id=item.resource_id,
                    event_type=event_type,
                    progress_pct=pct,
                    time_spent_minutes=(request.time_spent_minutes or 0) if explicit else 0,
                    details={"source": "adaptive", "trigger": trigger},
                )
            )

    @staticmethod
    def _complete_item_by_id(items: list[LearningPathItem], item_id: uuid.UUID) -> None:
        for item in items:
            if item.id == item_id and item.status != PathItemStatus.COMPLETED:
                item.status = PathItemStatus.COMPLETED

    @staticmethod
    def _skip_item(items: list[LearningPathItem], resource_id: uuid.UUID) -> ResourceItemRead | None:
        for item in items:
            if item.resource_id == resource_id and item.status not in (
                PathItemStatus.COMPLETED, PathItemStatus.SKIPPED
            ):
                item.status = PathItemStatus.SKIPPED
                return ResourceItemRead(
                    resource_id=resource_id, item_id=item.id, title=item.title, reason="skipped"
                )
        return None

    def _complete_milestone(
        self, items: list[LearningPathItem], change: _SkillChange
    ) -> list[MilestoneRead]:
        completed: list[MilestoneRead] = []
        milestone_items = [i for i in items if i.rationale_trace.get("skill_slug") and
                           self._item_skill_id(i) == change.skill_id]
        if not milestone_items:
            return completed
        required = milestone_items[0].rationale_trace.get("required_level") or 0.0
        strong = change.score is not None and change.score >= 0.85
        if change.new >= required or strong:
            for item in milestone_items:
                if item.status not in (PathItemStatus.COMPLETED, PathItemStatus.SKIPPED):
                    item.status = PathItemStatus.COMPLETED
            trace = milestone_items[0].rationale_trace
            completed.append(
                MilestoneRead(
                    skill_id=change.skill_id,
                    title=trace.get("milestone") or milestone_items[0].title,
                    phase_title=trace.get("phase_title") or "",
                    phase_index=milestone_items[0].milestone_index,
                )
            )
        return completed

    @staticmethod
    def _skip_introductory(
        items: list[LearningPathItem], skill_id: uuid.UUID
    ) -> list[ResourceItemRead]:
        removed: list[ResourceItemRead] = []
        for item in items:
            trace = item.rationale_trace or {}
            is_intro = (trace.get("difficulty") or 5) <= _INTRO_DIFFICULTY
            if (
                is_intro
                and item.item_type == PathItemType.RESOURCE
                and item.status in (PathItemStatus.LOCKED, PathItemStatus.AVAILABLE)
                and _matches_skill(item, skill_id)
            ):
                item.status = PathItemStatus.SKIPPED
                removed.append(
                    ResourceItemRead(
                        resource_id=item.resource_id, item_id=item.id, title=item.title,
                        reason="already proficient — introductory material skipped",
                    )
                )
        return removed

    def _unlock_next(self, items: list[LearningPathItem]) -> list[MilestoneRead]:
        locked = sorted(
            (i for i in items if i.status == PathItemStatus.LOCKED),
            key=lambda i: i.order_index,
        )
        if not locked:
            return []
        target = locked[0]
        milestone_key = target.rationale_trace.get("milestone") or target.title
        milestone_items = [
            i for i in locked
            if (i.rationale_trace.get("milestone") or i.title) == milestone_key
            and i.milestone_index == target.milestone_index
        ]
        for item in milestone_items:
            item.status = PathItemStatus.AVAILABLE
        return [
            MilestoneRead(
                skill_id=self._item_skill_id(target),
                title=milestone_key,
                phase_title=target.rationale_trace.get("phase_title") or "",
                phase_index=target.milestone_index,
            )
        ]

    async def _insert_remediation(
        self, path: LearningPath, items: list[LearningPathItem], skill_id: uuid.UUID
    ) -> list[ResourceItemRead]:
        """Insert easier resources for the skill's prerequisites (remedial)."""
        prereq_edges = await self.prerequisites.list_prerequisites(skill_id)
        prereq_ids = [e.prerequisite_skill_id for e in prereq_edges] or [skill_id]
        existing_resource_ids = {i.resource_id for i in items if i.resource_id}

        candidates = await self.resources.list(
            limit=6,
            filters=[
                Resource.is_active.is_(True),
                ResourceRepository.teaches_skill_filter(prereq_ids[0]),
            ],
            order_by=(Resource.difficulty, Resource.quality_score.desc().nullslast(), Resource.id),
        )
        inserted: list[ResourceItemRead] = []
        next_order = max((i.order_index for i in items), default=0)
        for resource in candidates:
            if resource.id in existing_resource_ids or len(inserted) >= _MAX_REMEDIATION:
                continue
            next_order += 1
            new_item = LearningPathItem(
                path_id=path.id,
                resource_id=resource.id,
                order_index=next_order,
                milestone_index=0,
                milestone_title="Remediation",
                title=resource.title,
                item_type=PathItemType.RESOURCE,
                status=PathItemStatus.AVAILABLE,
                estimated_minutes=round(resource.estimated_hours * 60),
                rationale_trace={"kind": "remediation", "for_skill": str(skill_id)},
            )
            self.session.add(new_item)
            items.append(new_item)
            inserted.append(
                ResourceItemRead(
                    resource_id=resource.id, title=resource.title,
                    reason="remediation — added because your recent score was low",
                )
            )
        return inserted

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _item_skill_id(item: LearningPathItem) -> uuid.UUID | None:
        raw = item.rationale_trace.get("skill_id")
        try:
            return uuid.UUID(str(raw)) if raw else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _next_action(updated_skills, unlocked, removed, newly_recommended) -> str:  # type: ignore[no-untyped-def]
        if newly_recommended:
            return "Work through the newly added remediation resources before retrying the checkpoint."
        if unlocked:
            names = ", ".join(m.title for m in unlocked)
            return f"Great progress — the next milestone is unlocked: {names}."
        if removed:
            return "You're already proficient here; skip ahead to the next milestone."
        if updated_skills:
            band = updated_skills[0].level_band
            if band == "advanced":
                return "Advance to the next skill in your roadmap."
            if band == "intermediate":
                return "Continue with the intermediate resources for this skill."
            return "Reinforce the fundamentals before moving on."
        return "Continue with your current milestone."


def _matches_skill(item: LearningPathItem, skill_id: uuid.UUID) -> bool:
    raw = item.rationale_trace.get("skill_id")
    return str(raw) == str(skill_id)


def _dedupe_milestones(milestones: list[MilestoneRead]) -> list[MilestoneRead]:
    seen: set[tuple] = set()
    out: list[MilestoneRead] = []
    for m in milestones:
        key = (str(m.skill_id), m.title, m.phase_index)
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out
