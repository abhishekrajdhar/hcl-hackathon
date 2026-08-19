"""Deterministic learning-path (roadmap) construction.

Turns an already prerequisite-ordered list of skill milestones, the selected
resources, and the learner's constraints into a phased roadmap with a schedule.
Pure — no DB, no model, no clock (dates are computed from an injected
`start_date`). The LLM is never asked to invent the roadmap; it may later explain
one built here.

Ordering guarantee: the input milestones must already be in a valid prerequisite
order (the caller uses the gap engine's topological ranking). This module
preserves that order within and across phases, so a skill never appears before
one it depends on.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

DEFAULT_ASSESSMENT_MINUTES = 20
DEFAULT_REVIEW_MINUTES = 120
DEFAULT_WEEKLY_MINUTES = 5 * 60


@dataclass(frozen=True, slots=True)
class ResourcePick:
    resource_id: uuid.UUID
    title: str
    estimated_hours: float
    modality: str = "mixed"
    difficulty: int = 1
    is_project: bool = False


@dataclass(frozen=True, slots=True)
class MilestoneInput:
    skill_id: uuid.UUID
    skill_slug: str
    skill_name: str
    category_slug: str
    category_name: str
    difficulty: int
    current_level: float
    required_level: float
    gap: float
    layer: int = 0
    prerequisite_names: tuple[str, ...] = ()
    resources: tuple[ResourcePick, ...] = ()
    assessment_id: uuid.UUID | None = None
    assessment_title: str | None = None


@dataclass(frozen=True, slots=True)
class CapstoneInput:
    title: str
    description: str
    resource_id: uuid.UUID | None = None
    skill_names: tuple[str, ...] = ()
    estimated_hours: float = 20.0


@dataclass(frozen=True, slots=True)
class GoalInput:
    title: str
    target_role: str | None = None


@dataclass(frozen=True, slots=True)
class PathConstraints:
    weekly_hours: int = 5
    target_deadline: date | None = None
    start_date: date | None = None
    preferred_modalities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlannedItem:
    order_index: int
    phase_index: int
    kind: str  # "resource" | "assessment" | "project"
    title: str
    estimated_minutes: int
    resource_id: uuid.UUID | None = None
    assessment_id: uuid.UUID | None = None
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = None
    is_optional: bool = False
    rationale: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MilestonePlan:
    skill_id: uuid.UUID | None
    skill_slug: str | None
    title: str
    current_level: float
    required_level: float
    gap: float
    prerequisites: tuple[str, ...]
    completion_criteria: str
    estimated_minutes: int
    resource_items: tuple[PlannedItem, ...]
    assessment_item: PlannedItem | None


@dataclass(frozen=True, slots=True)
class PhasePlan:
    index: int
    title: str
    objective: str
    milestones: tuple[MilestonePlan, ...]
    estimated_minutes: int
    planned_start: date | None
    planned_end: date | None
    is_capstone: bool = False


@dataclass(frozen=True, slots=True)
class Roadmap:
    phases: tuple[PhasePlan, ...]
    items: tuple[PlannedItem, ...]
    total_estimated_minutes: int
    planned_start: date | None
    planned_end: date | None
    feasibility_ok: bool
    feasibility_warning: str | None
    suggestions: tuple[str, ...]


def _hours_to_minutes(hours: float) -> int:
    return max(0, round(hours * 60))


def _completion_criteria(skill_name: str, required_level: float, has_assessment: bool) -> str:
    target = f"{round(required_level * 100)}%"
    if has_assessment:
        return (
            f"Complete the resources and score at least 70% on the {skill_name} "
            f"checkpoint to reach ~{target} proficiency."
        )
    return f"Complete the resources to reach ~{target} proficiency in {skill_name}."


def _phase_objective(category_name: str, milestone_names: list[str]) -> str:
    return f"Build {category_name} skills: {', '.join(milestone_names)}."


def _merge_adjacent_phases(phases: list[PhasePlan]) -> list[PhasePlan]:
    merged: list[PhasePlan] = []
    for phase in phases:
        if merged and merged[-1].title == phase.title:
            prev = merged[-1]
            combined = prev.milestones + phase.milestones
            merged[-1] = PhasePlan(
                index=prev.index,
                title=prev.title,
                objective=_phase_objective(prev.title, [m.title for m in combined]),
                milestones=combined,
                estimated_minutes=prev.estimated_minutes + phase.estimated_minutes,
                planned_start=None,
                planned_end=None,
                is_capstone=prev.is_capstone,
            )
        else:
            merged.append(phase)
    # re-index so phase indices stay contiguous (0..N)
    reindexed: list[PhasePlan] = []
    for new_index, phase in enumerate(merged):
        remapped = tuple(
            _reindex_milestone_items(m, new_index) for m in phase.milestones
        )
        reindexed.append(
            PhasePlan(
                index=new_index,
                title=phase.title,
                objective=phase.objective,
                milestones=remapped,
                estimated_minutes=phase.estimated_minutes,
                planned_start=phase.planned_start,
                planned_end=phase.planned_end,
                is_capstone=phase.is_capstone,
            )
        )
    return reindexed


def _reindex_milestone_items(milestone: MilestonePlan, phase_index: int) -> MilestonePlan:
    def fix(item: PlannedItem | None) -> PlannedItem | None:
        if item is None:
            return None
        return PlannedItem(
            order_index=item.order_index,
            phase_index=phase_index,
            kind=item.kind,
            title=item.title,
            estimated_minutes=item.estimated_minutes,
            resource_id=item.resource_id,
            assessment_id=item.assessment_id,
            skill_id=item.skill_id,
            skill_slug=item.skill_slug,
            is_optional=item.is_optional,
            rationale={**item.rationale, "phase_index": phase_index},
        )
    return MilestonePlan(
        skill_id=milestone.skill_id,
        skill_slug=milestone.skill_slug,
        title=milestone.title,
        current_level=milestone.current_level,
        required_level=milestone.required_level,
        gap=milestone.gap,
        prerequisites=milestone.prerequisites,
        completion_criteria=milestone.completion_criteria,
        estimated_minutes=milestone.estimated_minutes,
        resource_items=tuple(i for i in (fix(x) for x in milestone.resource_items) if i),
        assessment_item=fix(milestone.assessment_item),
    )


def _dominant_category(group: list[MilestoneInput]) -> str:
    """The most common category name in a layer (deterministic tie-break)."""
    counts: dict[str, int] = {}
    for m in group:
        name = m.category_name or "Foundations"
        counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def build_roadmap(
    milestones: list[MilestoneInput],
    constraints: PathConstraints,
    goal: GoalInput,
    capstone: CapstoneInput | None = None,
) -> Roadmap:
    """Assemble phases, milestones, items and a schedule from ordered inputs."""
    order_counter = 0
    items: list[PlannedItem] = []

    # --- group milestones into phases by prerequisite DAG layer.
    # A skill's prerequisites are always in a strictly lower layer, so grouping
    # by layer preserves prerequisite order regardless of the within-layer input
    # order, and it never fragments the way category runs can. Layer 0 (nothing
    # unmet before it) becomes the "Foundations" phase.
    by_layer: dict[int, list[MilestoneInput]] = {}
    for milestone in milestones:
        by_layer.setdefault(milestone.layer, []).append(milestone)

    phases: list[PhasePlan] = []
    for phase_index, layer in enumerate(sorted(by_layer)):
        group = by_layer[layer]
        category_name = "Foundations" if phase_index == 0 else _dominant_category(group)
        milestone_plans: list[MilestonePlan] = []

        for milestone in group:
            resource_items: list[PlannedItem] = []
            for pick in milestone.resources:
                order_counter += 1
                item = PlannedItem(
                    order_index=order_counter,
                    phase_index=phase_index,
                    kind="resource",
                    title=pick.title,
                    estimated_minutes=_hours_to_minutes(pick.estimated_hours),
                    resource_id=pick.resource_id,
                    skill_id=milestone.skill_id,
                    skill_slug=milestone.skill_slug,
                    rationale={
                        "phase_index": phase_index,
                        "phase_title": category_name,
                        "milestone": milestone.skill_name,
                        "skill_slug": milestone.skill_slug,
                        "kind": "resource",
                        "modality": pick.modality,
                        "difficulty": pick.difficulty,
                    },
                )
                resource_items.append(item)
                items.append(item)

            assessment_item: PlannedItem | None = None
            if milestone.assessment_id is not None:
                order_counter += 1
                assessment_item = PlannedItem(
                    order_index=order_counter,
                    phase_index=phase_index,
                    kind="assessment",
                    title=milestone.assessment_title or f"{milestone.skill_name} checkpoint",
                    estimated_minutes=DEFAULT_ASSESSMENT_MINUTES,
                    assessment_id=milestone.assessment_id,
                    skill_id=milestone.skill_id,
                    skill_slug=milestone.skill_slug,
                    rationale={
                        "phase_index": phase_index,
                        "phase_title": category_name,
                        "milestone": milestone.skill_name,
                        "skill_slug": milestone.skill_slug,
                        "kind": "assessment",
                    },
                )
                items.append(assessment_item)

            if not resource_items and assessment_item is None:
                # No catalogue resource yet — keep the skill visible as a
                # self-study milestone rather than silently dropping it.
                order_counter += 1
                review = PlannedItem(
                    order_index=order_counter,
                    phase_index=phase_index,
                    kind="review",
                    title=f"Self-study: {milestone.skill_name}",
                    estimated_minutes=DEFAULT_REVIEW_MINUTES,
                    skill_id=milestone.skill_id,
                    skill_slug=milestone.skill_slug,
                    rationale={
                        "phase_index": phase_index,
                        "phase_title": category_name,
                        "milestone": milestone.skill_name,
                        "skill_slug": milestone.skill_slug,
                        "kind": "review",
                    },
                )
                resource_items.append(review)
                items.append(review)

            milestone_minutes = sum(i.estimated_minutes for i in resource_items) + (
                assessment_item.estimated_minutes if assessment_item else 0
            )
            milestone_plans.append(
                MilestonePlan(
                    skill_id=milestone.skill_id,
                    skill_slug=milestone.skill_slug,
                    title=milestone.skill_name,
                    current_level=round(milestone.current_level, 4),
                    required_level=round(milestone.required_level, 4),
                    gap=round(milestone.gap, 4),
                    prerequisites=milestone.prerequisite_names,
                    completion_criteria=_completion_criteria(
                        milestone.skill_name, milestone.required_level, assessment_item is not None
                    ),
                    estimated_minutes=milestone_minutes,
                    resource_items=tuple(resource_items),
                    assessment_item=assessment_item,
                )
            )

        phase_minutes = sum(m.estimated_minutes for m in milestone_plans)
        phases.append(
            PhasePlan(
                index=phase_index,
                title=category_name,
                objective=_phase_objective(category_name, [m.title for m in milestone_plans]),
                milestones=tuple(milestone_plans),
                estimated_minutes=phase_minutes,
                planned_start=None,
                planned_end=None,
            )
        )

    # Merge consecutive phases that share a title (adjacent DAG layers of the
    # same category) into one — order-safe because they are already adjacent —
    # so "Deep Learning, Deep Learning, Deep Learning" becomes a single phase.
    phases = _merge_adjacent_phases(phases)

    # --- capstone phase ----------------------------------------------------
    if capstone is not None:
        order_counter += 1
        capstone_index = len(phases)
        project_item = PlannedItem(
            order_index=order_counter,
            phase_index=capstone_index,
            kind="project",
            title=capstone.title,
            estimated_minutes=_hours_to_minutes(capstone.estimated_hours),
            resource_id=capstone.resource_id,
            rationale={
                "phase_index": capstone_index,
                "phase_title": "Capstone",
                "milestone": capstone.title,
                "kind": "project",
                "is_capstone": True,
            },
        )
        items.append(project_item)
        capstone_milestone = MilestonePlan(
            skill_id=None,
            skill_slug=None,
            title=capstone.title,
            current_level=0.0,
            required_level=1.0,
            gap=1.0,
            prerequisites=capstone.skill_names,
            completion_criteria=(
                "Design and complete the capstone project, applying every skill "
                "in the roadmap toward your goal."
            ),
            estimated_minutes=project_item.estimated_minutes,
            resource_items=(project_item,),
            assessment_item=None,
        )
        phases.append(
            PhasePlan(
                index=capstone_index,
                title="Capstone",
                objective=capstone.description,
                milestones=(capstone_milestone,),
                estimated_minutes=project_item.estimated_minutes,
                planned_start=None,
                planned_end=None,
                is_capstone=True,
            )
        )

    # Rebuild the flat item list from the final phases so every item's
    # phase_index matches after merging/reindexing.
    items = [
        item
        for phase in phases
        for milestone in phase.milestones
        for item in (*milestone.resource_items, *( (milestone.assessment_item,) if milestone.assessment_item else () ))
    ]
    items.sort(key=lambda i: i.order_index)

    # --- schedule ----------------------------------------------------------
    phases = _schedule(phases, constraints)
    total = sum(p.estimated_minutes for p in phases)
    planned_start = phases[0].planned_start if phases else None
    planned_end = phases[-1].planned_end if phases else None

    feasibility_ok, warning, suggestions = _feasibility(
        planned_end, constraints, total
    )

    return Roadmap(
        phases=tuple(phases),
        items=tuple(items),
        total_estimated_minutes=total,
        planned_start=planned_start,
        planned_end=planned_end,
        feasibility_ok=feasibility_ok,
        feasibility_warning=warning,
        suggestions=tuple(suggestions),
    )


def _schedule(phases: list[PhasePlan], constraints: PathConstraints) -> list[PhasePlan]:
    """Assign start/end dates to each phase from the weekly-hours budget."""
    weekly_minutes = max(60, (constraints.weekly_hours or 5) * 60)
    start = constraints.start_date or date.today()
    cursor = start
    scheduled: list[PhasePlan] = []
    for phase in phases:
        weeks = max(1, -(-phase.estimated_minutes // weekly_minutes))  # ceil division
        phase_start = cursor
        phase_end = cursor + timedelta(weeks=weeks)
        scheduled.append(
            PhasePlan(
                index=phase.index,
                title=phase.title,
                objective=phase.objective,
                milestones=phase.milestones,
                estimated_minutes=phase.estimated_minutes,
                planned_start=phase_start,
                planned_end=phase_end,
                is_capstone=phase.is_capstone,
            )
        )
        cursor = phase_end
    return scheduled


def _feasibility(
    planned_end: date | None, constraints: PathConstraints, total_minutes: int
) -> tuple[bool, str | None, list[str]]:
    if constraints.target_deadline is None or planned_end is None:
        return True, None, []
    if planned_end <= constraints.target_deadline:
        return True, None, []

    over_days = (planned_end - constraints.target_deadline).days
    needed_weekly = total_minutes / 60 / max(
        1, ((constraints.target_deadline - (constraints.start_date or date.today())).days / 7)
    )
    warning = (
        f"At {constraints.weekly_hours}h/week this roadmap finishes about "
        f"{over_days} day(s) after your target date."
    )
    suggestions = [
        f"Increase weekly study to about {max(1, round(needed_weekly))}h/week.",
        "Extend the target date.",
        "Drop optional/nice-to-have milestones.",
    ]
    return False, warning, suggestions
