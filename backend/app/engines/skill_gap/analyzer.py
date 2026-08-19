"""Deterministic skill-gap analysis.

Given a target (required proficiencies), a learner's current proficiencies, and
the prerequisite graph, this computes what must be learned and — crucially — in
what order. Everything here is arithmetic and graph traversal: no model, no
randomness, reproducible for identical inputs.

All proficiencies are on the canonical [0, 1] scale (the learner-profile scale),
so `gap = required - current` is directly comparable across skills.

Ordering rule: gaps are NOT sorted by size. A prerequisite always precedes the
skills that depend on it (priority-aware topological sort over the hard
prerequisite graph); the priority score only orders skills that are otherwise
free to be learned in either order.
"""

from __future__ import annotations

import heapq
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.engines.skill_graph.graph import SkillGraph

#: Gaps at or below this are treated as already met (ignored).
GAP_EPSILON = 1e-6


@dataclass(frozen=True, slots=True)
class RequiredSkill:
    """A skill the goal calls for, at a target proficiency in [0, 1]."""

    required_level: float
    importance: float = 1.0  # relevance to the goal, [0, 1]
    is_target: bool = True   # explicit goal skill vs. a pulled-in prerequisite


@dataclass(frozen=True, slots=True)
class GapWeights:
    """Weights for the priority score. Sum need not be 1; scores are relative."""

    gap: float = 0.30            # how far the learner is from the requirement
    downstream: float = 0.30     # how many other gaps this skill unblocks
    importance: float = 0.25     # relevance to the target goal
    readiness: float = 0.15      # learnable now (no unmet prerequisites) -> unblock sooner


@dataclass(frozen=True, slots=True)
class RankedGap:
    skill_id: uuid.UUID
    current_level: float
    required_level: float
    gap: float
    priority: float
    rank: int                    # 1-based position in the learning order
    level: int                   # DAG layer (0 = learnable immediately)
    is_target: bool
    importance: float
    downstream_count: int        # gaps that (transitively) depend on this one
    prerequisite_ids: tuple[uuid.UUID, ...]        # direct prerequisites that are also gaps
    unmet_prerequisite_ids: tuple[uuid.UUID, ...]  # of those, not yet satisfied
    reason: str


@dataclass(frozen=True, slots=True)
class GapAnalysis:
    ranked_gaps: tuple[RankedGap, ...] = ()
    #: Skills learnable right now (no unmet prerequisites), highest priority first.
    priority_skill_ids: tuple[uuid.UUID, ...] = ()
    #: Target skills already satisfied (gap <= 0), for transparency.
    met_target_ids: tuple[uuid.UUID, ...] = ()
    #: Required skill ids not present as nodes in the graph.
    unknown_skill_ids: tuple[uuid.UUID, ...] = ()

    def gap_for(self, skill_id: uuid.UUID) -> RankedGap | None:
        return next((g for g in self.ranked_gaps if g.skill_id == skill_id), None)


def _propagate_required_levels(
    required: Mapping[uuid.UUID, RequiredSkill],
    current: Mapping[uuid.UUID, float],
    graph: SkillGraph,
    *,
    min_gap: float,
) -> dict[uuid.UUID, float]:
    """Assign a required level to every prerequisite the learner still needs.

    Explicit target levels are authoritative. A pulled-in prerequisite inherits
    the strongest demand from the skills that need it: for each dependent D that
    still requires work and depends on prerequisite P via an edge of `strength`,
    P must reach at least `required[D] * strength`. A dependent that is already
    satisfied imposes NO requirement on its prerequisites — if the learner has D
    they implicitly have its prerequisite chain — so met skills do not drag in
    their prerequisites as spurious gaps. Processing dependents before
    prerequisites (reverse topological order) flows demand down a whole chain.
    """
    targets = list(required)
    closure = graph.required_closure(targets)  # targets + transitive prerequisites
    order = graph.topological_order(closure)   # prerequisites first

    levels: dict[uuid.UUID, float] = {
        sid: required[sid].required_level for sid in targets if sid in closure
    }
    for skill_id in reversed(order):  # dependents first
        demand = levels.get(skill_id)
        if demand is None:
            continue
        # Only a skill that itself still needs work requires its prerequisites.
        if demand - current.get(skill_id, 0.0) <= min_gap:
            continue
        for edge in graph.prerequisites_of(skill_id):
            prereq = edge.prerequisite_id
            if prereq in required:  # explicit targets keep their stated level
                continue
            propagated = demand * edge.strength
            if propagated > levels.get(prereq, 0.0):
                levels[prereq] = propagated
    return levels


def analyze_gaps(
    required: Mapping[uuid.UUID, RequiredSkill],
    current: Mapping[uuid.UUID, float],
    graph: SkillGraph,
    *,
    weights: GapWeights | None = None,
    min_gap: float = GAP_EPSILON,
) -> GapAnalysis:
    """Compute, prioritise and prerequisite-order the learner's skill gaps."""
    weights = weights or GapWeights()

    unknown = tuple(sorted((sid for sid in required if not graph.has_node(sid)), key=str))
    known_required = {sid: rs for sid, rs in required.items() if graph.has_node(sid)}

    required_levels = _propagate_required_levels(known_required, current, graph, min_gap=min_gap)

    # --- raw gaps -------------------------------------------------------
    gaps: dict[uuid.UUID, float] = {}
    met_targets: list[uuid.UUID] = []
    for skill_id, req_level in required_levels.items():
        gap = req_level - current.get(skill_id, 0.0)
        if gap > min_gap:
            gaps[skill_id] = gap
        elif skill_id in known_required and known_required[skill_id].is_target:
            met_targets.append(skill_id)

    gap_set = set(gaps)
    if not gap_set:
        return GapAnalysis(
            met_target_ids=tuple(sorted(met_targets, key=graph.sort_key)),
            unknown_skill_ids=unknown,
        )

    # --- structural facts over the induced gap subgraph -----------------
    direct_prereqs: dict[uuid.UUID, list[uuid.UUID]] = {}
    unmet_prereqs: dict[uuid.UUID, list[uuid.UUID]] = {}
    downstream: dict[uuid.UUID, int] = {}
    for skill_id in gap_set:
        prereqs_in_gap = [
            e.prerequisite_id
            for e in graph.prerequisites_of(skill_id)
            if e.prerequisite_id in gap_set
        ]
        direct_prereqs[skill_id] = prereqs_in_gap
        unmet_prereqs[skill_id] = list(prereqs_in_gap)  # all are gaps => all unmet
        downstream[skill_id] = sum(1 for d in graph.descendants(skill_id) if d in gap_set)

    max_downstream = max(downstream.values(), default=0)

    def importance_of(skill_id: uuid.UUID) -> float:
        rs = known_required.get(skill_id)
        if rs is not None:
            return rs.importance
        # pulled-in prerequisite: inherit the max importance of its dependents
        dependents = [d for d in graph.descendants(skill_id) if d in known_required]
        return max((known_required[d].importance for d in dependents), default=0.5)

    # --- priority score -------------------------------------------------
    priority: dict[uuid.UUID, float] = {}
    for skill_id in gap_set:
        gap_component = min(1.0, gaps[skill_id])
        downstream_component = downstream[skill_id] / max_downstream if max_downstream else 0.0
        importance_component = importance_of(skill_id)
        readiness_component = 1.0 if not unmet_prereqs[skill_id] else 0.0
        priority[skill_id] = round(
            weights.gap * gap_component
            + weights.downstream * downstream_component
            + weights.importance * importance_component
            + weights.readiness * readiness_component,
            6,
        )

    order = _priority_topological_order(gap_set, graph, priority)
    levels = _layers(gap_set, graph)

    is_target = {sid: (sid in known_required and known_required[sid].is_target) for sid in gap_set}
    ranked = tuple(
        RankedGap(
            skill_id=skill_id,
            current_level=round(current.get(skill_id, 0.0), 6),
            required_level=round(required_levels[skill_id], 6),
            gap=round(gaps[skill_id], 6),
            priority=priority[skill_id],
            rank=index + 1,
            level=levels[skill_id],
            is_target=is_target[skill_id],
            importance=round(importance_of(skill_id), 6),
            downstream_count=downstream[skill_id],
            prerequisite_ids=tuple(direct_prereqs[skill_id]),
            unmet_prerequisite_ids=tuple(unmet_prereqs[skill_id]),
            reason=_build_reason(
                graph=graph,
                skill_id=skill_id,
                gap=gaps[skill_id],
                is_target=is_target[skill_id],
                downstream_count=downstream[skill_id],
                unmet=unmet_prereqs[skill_id],
                gap_set=gap_set,
                known_required=known_required,
            ),
        )
        for index, skill_id in enumerate(order)
    )

    priority_skills = tuple(
        sid
        for sid in order
        if not unmet_prereqs[sid]  # learnable now
    )
    priority_skills = tuple(
        sorted(priority_skills, key=lambda s: (-priority[s], *graph.sort_key(s)))
    )

    return GapAnalysis(
        ranked_gaps=ranked,
        priority_skill_ids=priority_skills,
        met_target_ids=tuple(sorted(met_targets, key=graph.sort_key)),
        unknown_skill_ids=unknown,
    )


def _priority_topological_order(
    gap_set: set[uuid.UUID], graph: SkillGraph, priority: Mapping[uuid.UUID, float]
) -> list[uuid.UUID]:
    """Kahn's algorithm restricted to the gap set, breaking ties by priority.

    A skill is emitted only after every prerequisite that is also a gap; among
    the skills that are ready at any step, the highest priority (then easiest,
    then alphabetical) goes first. Deterministic. The gap set is a subset of a
    DAG, so this always consumes every node.
    """
    indegree = {
        sid: sum(
            1 for e in graph.prerequisites_of(sid) if e.prerequisite_id in gap_set
        )
        for sid in gap_set
    }

    def key(sid: uuid.UUID) -> tuple:
        difficulty, slug = graph.sort_key(sid)
        return (-priority[sid], difficulty, slug, sid.int)

    heap = [(key(sid), sid) for sid, deg in indegree.items() if deg == 0]
    heapq.heapify(heap)

    order: list[uuid.UUID] = []
    while heap:
        _, skill_id = heapq.heappop(heap)
        order.append(skill_id)
        for edge in graph.dependents_of(skill_id):
            dependent = edge.source_id
            if dependent not in gap_set:
                continue
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(heap, (key(dependent), dependent))
    return order


def _layers(gap_set: set[uuid.UUID], graph: SkillGraph) -> dict[uuid.UUID, int]:
    """Level of each gap skill: one past the deepest prerequisite that is a gap."""
    order = graph.topological_order(gap_set)
    level: dict[uuid.UUID, int] = {}
    for skill_id in order:
        prereq_levels = [
            level[e.prerequisite_id]
            for e in graph.prerequisites_of(skill_id)
            if e.prerequisite_id in gap_set
        ]
        level[skill_id] = max(prereq_levels) + 1 if prereq_levels else 0
    return level


def _names(graph: SkillGraph, ids: Iterable[uuid.UUID]) -> list[str]:
    out = []
    for sid in ids:
        node = graph.node(sid)
        out.append(node.name if node is not None else str(sid))
    return out


def _build_reason(
    *,
    graph: SkillGraph,
    skill_id: uuid.UUID,
    gap: float,
    is_target: bool,
    downstream_count: int,
    unmet: list[uuid.UUID],
    gap_set: set[uuid.UUID],
    known_required: Mapping[uuid.UUID, RequiredSkill],
) -> str:
    """Deterministic, template-built explanation — never model-generated."""
    role = "Directly required for your goal" if is_target else "Prerequisite for your goal"
    parts = [f"{role} (gap of {gap:.2f})."]

    if unmet:
        names = _names(graph, sorted(unmet, key=graph.sort_key))
        parts.append(f"Learn first: {', '.join(names)}.")
    else:
        parts.append("Can be started now.")

    if downstream_count:
        dependents = [d for d in graph.descendants(skill_id) if d in gap_set]
        sample = _names(graph, sorted(dependents, key=graph.sort_key)[:3])
        more = "" if downstream_count <= 3 else f" and {downstream_count - 3} more"
        parts.append(f"Unblocks {downstream_count} later skill(s): {', '.join(sample)}{more}.")

    return " ".join(parts)
