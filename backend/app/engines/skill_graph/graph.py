"""Pure, deterministic algorithms over the skill prerequisite DAG.

Nothing in this module touches the database, the network or a model. Given the
same nodes and edges it always returns the same answer, which is what makes
prerequisite ordering auditable and testable.

Edge direction: an edge records that `source` requires `prerequisite`. In a
learning sequence the prerequisite therefore comes *first*.
"""

from __future__ import annotations

import heapq
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.models.enums import (
    BLOCKING_RELATIONSHIPS,
    ORDERING_RELATIONSHIPS,
    RelationshipType,
)

#: Safety bound on traversal depth. A well-formed taxonomy is far shallower;
#: this only stops a malformed graph from producing an unbounded walk.
MAX_TRAVERSAL_DEPTH = 32


@dataclass(frozen=True, slots=True)
class GraphNode:
    id: uuid.UUID
    slug: str
    name: str
    difficulty: int = 1
    category_slug: str | None = None


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: uuid.UUID
    prerequisite_id: uuid.UUID
    relationship_type: RelationshipType = RelationshipType.HARD_PREREQUISITE
    strength: float = 1.0
    min_level: float = 1.0


@dataclass(frozen=True, slots=True)
class OrderViolation:
    skill_id: uuid.UUID
    prerequisite_id: uuid.UUID
    relationship_type: RelationshipType
    reason: Literal["missing_prerequisite", "out_of_order"]
    skill_position: int
    prerequisite_position: int | None
    severity: Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    violations: tuple[OrderViolation, ...] = ()
    missing_prerequisites: tuple[uuid.UUID, ...] = ()
    unknown_skills: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CycleError(Exception):
    """Raised when an operation requires a DAG but the graph contains a cycle."""

    cycles: tuple[tuple[uuid.UUID, ...], ...] = field(default=())

    def __str__(self) -> str:  # pragma: no cover - message formatting
        return f"skill graph contains {len(self.cycles)} cycle(s)"


class SkillGraph:
    """An immutable view of the prerequisite graph.

    `related` edges are excluded from every traversal: they are an association,
    not a dependency, so they neither order skills nor form cycles.
    """

    def __init__(self, nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]) -> None:
        self._nodes: dict[uuid.UUID, GraphNode] = {node.id: node for node in nodes}

        # prerequisites_of[x] = edges where x is the source (things x needs)
        # dependents_of[x]    = edges where x is the prerequisite (things needing x)
        self._prerequisites_of: dict[uuid.UUID, list[GraphEdge]] = {}
        self._dependents_of: dict[uuid.UUID, list[GraphEdge]] = {}
        self._edges: list[GraphEdge] = []

        for edge in edges:
            if edge.relationship_type not in ORDERING_RELATIONSHIPS:
                continue
            self._edges.append(edge)
            self._prerequisites_of.setdefault(edge.source_id, []).append(edge)
            self._dependents_of.setdefault(edge.prerequisite_id, []).append(edge)

        # Stable ordering everywhere, so every traversal is reproducible.
        for bucket in (self._prerequisites_of, self._dependents_of):
            for edge_list in bucket.values():
                edge_list.sort(key=lambda e: (self.sort_key(e.prerequisite_id), e.source_id.int))

    # --- basics ----------------------------------------------------------
    @property
    def node_ids(self) -> list[uuid.UUID]:
        return sorted(self._nodes, key=self.sort_key)

    @property
    def edges(self) -> list[GraphEdge]:
        return list(self._edges)

    def node(self, skill_id: uuid.UUID) -> GraphNode | None:
        return self._nodes.get(skill_id)

    def has_node(self, skill_id: uuid.UUID) -> bool:
        return skill_id in self._nodes

    def sort_key(self, skill_id: uuid.UUID) -> tuple[int, str]:
        """Total order used to break ties deterministically.

        Easier skills first, then alphabetically by slug. Slugs are unique, so
        no two nodes ever compare equal and the result is a total order.
        """
        node = self._nodes.get(skill_id)
        if node is None:
            # Edge endpoint outside the loaded subgraph: sort last, but stably.
            return (99, str(skill_id))
        return (node.difficulty, node.slug)

    def prerequisites_of(
        self, skill_id: uuid.UUID, *, types: Iterable[RelationshipType] | None = None
    ) -> list[GraphEdge]:
        """Direct prerequisites of a skill."""
        edges = self._prerequisites_of.get(skill_id, [])
        if types is None:
            return list(edges)
        allowed = set(types)
        return [e for e in edges if e.relationship_type in allowed]

    def dependents_of(
        self, skill_id: uuid.UUID, *, types: Iterable[RelationshipType] | None = None
    ) -> list[GraphEdge]:
        """Skills that directly require this one."""
        edges = self._dependents_of.get(skill_id, [])
        if types is None:
            return list(edges)
        allowed = set(types)
        return [e for e in edges if e.relationship_type in allowed]

    # --- traversal -------------------------------------------------------
    def _reachable(
        self,
        roots: Iterable[uuid.UUID],
        *,
        upward: bool,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
        types: Iterable[RelationshipType] | None = None,
        stop_at: Iterable[uuid.UUID] | None = None,
    ) -> dict[uuid.UUID, int]:
        """Breadth-first closure returning {skill_id: minimum depth from a root}.

        Roots are excluded. `stop_at` nodes are neither included nor expanded
        through — used to prune branches a learner has already mastered.
        Depth-bounded, and safe on a cyclic graph because `seen` is checked
        before enqueueing.
        """
        allowed = set(types) if types is not None else None
        blocked = set(stop_at) if stop_at is not None else set()
        seen: dict[uuid.UUID, int] = {}
        roots = list(roots)
        frontier = [(node_id, 0) for node_id in roots]
        root_set = set(roots)

        while frontier:
            current, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            edges = (
                self._prerequisites_of.get(current, [])
                if upward
                else self._dependents_of.get(current, [])
            )
            for edge in edges:
                if allowed is not None and edge.relationship_type not in allowed:
                    continue
                neighbour = edge.prerequisite_id if upward else edge.source_id
                if neighbour in root_set or neighbour in blocked:
                    continue
                if neighbour in seen and seen[neighbour] <= depth + 1:
                    continue
                seen[neighbour] = depth + 1
                frontier.append((neighbour, depth + 1))
        return seen

    def ancestors(
        self,
        skill_id: uuid.UUID,
        *,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
        types: Iterable[RelationshipType] | None = None,
    ) -> dict[uuid.UUID, int]:
        """All transitive prerequisites, mapped to their shallowest depth."""
        return self._reachable([skill_id], upward=True, max_depth=max_depth, types=types)

    def descendants(
        self,
        skill_id: uuid.UUID,
        *,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
        types: Iterable[RelationshipType] | None = None,
    ) -> dict[uuid.UUID, int]:
        """All skills transitively unlocked by this one."""
        return self._reachable([skill_id], upward=False, max_depth=max_depth, types=types)

    def required_closure(
        self,
        skill_ids: Iterable[uuid.UUID],
        *,
        stop_at: Iterable[uuid.UUID] | None = None,
    ) -> set[uuid.UUID]:
        """The targets plus everything they transitively require.

        Anything in `stop_at` is treated as already mastered: it is excluded and
        the walk does not continue past it, so prerequisites reachable only
        through a mastered skill drop out too.
        """
        blocked = set(stop_at) if stop_at is not None else set()
        targets = [s for s in skill_ids if s not in blocked]
        closure = set(targets)
        closure.update(self._reachable(targets, upward=True, stop_at=blocked))
        return closure

    # --- cycles ----------------------------------------------------------
    def detect_cycles(self) -> list[list[uuid.UUID]]:
        """Every cycle reachable by DFS, as node lists in traversal order.

        Iterative three-colour DFS: WHITE unvisited, GREY on the current stack,
        BLACK finished. Encountering a GREY node closes a cycle. Iterative so a
        pathological graph cannot blow the Python stack.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[uuid.UUID, int] = {node_id: WHITE for node_id in self._nodes}
        for edge in self._edges:  # tolerate endpoints outside the node set
            colour.setdefault(edge.source_id, WHITE)
            colour.setdefault(edge.prerequisite_id, WHITE)

        cycles: list[list[uuid.UUID]] = []
        seen_cycles: set[frozenset[uuid.UUID]] = set()

        for root in sorted(colour, key=self.sort_key):
            if colour[root] != WHITE:
                continue

            path: list[uuid.UUID] = []
            on_path: set[uuid.UUID] = set()
            # (node, iterator of its prerequisites)
            stack: list[tuple[uuid.UUID, list[uuid.UUID]]] = [
                (root, [e.prerequisite_id for e in self._prerequisites_of.get(root, [])])
            ]
            colour[root] = GREY
            path.append(root)
            on_path.add(root)

            while stack:
                node, pending = stack[-1]
                if not pending:
                    colour[node] = BLACK
                    stack.pop()
                    path.pop()
                    on_path.discard(node)
                    continue

                nxt = pending.pop(0)
                if colour.get(nxt, WHITE) == GREY and nxt in on_path:
                    cycle = path[path.index(nxt) :] + [nxt]
                    signature = frozenset(cycle)
                    if signature not in seen_cycles:
                        seen_cycles.add(signature)
                        cycles.append(cycle)
                    continue
                if colour.get(nxt, WHITE) != WHITE:
                    continue

                colour[nxt] = GREY
                path.append(nxt)
                on_path.add(nxt)
                stack.append(
                    (nxt, [e.prerequisite_id for e in self._prerequisites_of.get(nxt, [])])
                )

        return cycles

    def is_acyclic(self) -> bool:
        return not self.detect_cycles()

    def would_create_cycle(
        self, source_id: uuid.UUID, prerequisite_id: uuid.UUID
    ) -> list[uuid.UUID] | None:
        """Check an edge *before* it is written.

        Adding `source requires prerequisite` closes a cycle exactly when
        `source` is already reachable from `prerequisite` by following
        prerequisites upward. Returns the offending path, or None when safe.
        """
        if source_id == prerequisite_id:
            return [source_id, prerequisite_id]

        # BFS upward from `prerequisite`, tracking parents to rebuild the path.
        parents: dict[uuid.UUID, uuid.UUID] = {}
        frontier = [prerequisite_id]
        visited = {prerequisite_id}
        depth = 0
        while frontier and depth < MAX_TRAVERSAL_DEPTH:
            nxt_frontier: list[uuid.UUID] = []
            for current in frontier:
                for edge in self._prerequisites_of.get(current, []):
                    neighbour = edge.prerequisite_id
                    if neighbour in visited:
                        continue
                    visited.add(neighbour)
                    parents[neighbour] = current
                    if neighbour == source_id:
                        path = [source_id]
                        walk = source_id
                        while walk in parents:
                            walk = parents[walk]
                            path.append(walk)
                        # source ... prerequisite, then the new edge closes it
                        return [*path, source_id]
                    nxt_frontier.append(neighbour)
            frontier = nxt_frontier
            depth += 1
        return None

    # --- ordering --------------------------------------------------------
    def topological_order(self, subset: Iterable[uuid.UUID] | None = None) -> list[uuid.UUID]:
        """Prerequisite-respecting order, deterministic across runs.

        Kahn's algorithm with a min-heap on `sort_key`, so among the skills that
        are ready at any moment the easiest (then alphabetically first) is always
        emitted next. Raises CycleError if the subgraph is not a DAG.
        """
        nodes = set(subset) if subset is not None else set(self._nodes)

        indegree: dict[uuid.UUID, int] = {}
        for node_id in nodes:
            prereqs = {
                e.prerequisite_id
                for e in self._prerequisites_of.get(node_id, [])
                if e.prerequisite_id in nodes
            }
            indegree[node_id] = len(prereqs)

        heap: list[tuple[tuple[int, str], uuid.UUID]] = [
            (self.sort_key(node_id), node_id) for node_id, degree in indegree.items() if degree == 0
        ]
        heapq.heapify(heap)

        order: list[uuid.UUID] = []
        while heap:
            _, node_id = heapq.heappop(heap)
            order.append(node_id)
            for edge in sorted(
                self._dependents_of.get(node_id, []), key=lambda e: self.sort_key(e.source_id)
            ):
                dependent = edge.source_id
                if dependent not in nodes:
                    continue
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    heapq.heappush(heap, (self.sort_key(dependent), dependent))

        if len(order) != len(nodes):
            remaining = nodes - set(order)
            cycles = [c for c in self.detect_cycles() if remaining.intersection(c)]
            raise CycleError(cycles=tuple(tuple(c) for c in cycles))
        return order

    def layers(self, subset: Iterable[uuid.UUID] | None = None) -> list[list[uuid.UUID]]:
        """Group a topological order into levels that can be learned in parallel.

        Level 0 has no prerequisites inside the subset; a skill's level is one
        more than the deepest level among its prerequisites.
        """
        order = self.topological_order(subset)
        nodes = set(order)
        level: dict[uuid.UUID, int] = {}
        for node_id in order:
            prereq_levels = [
                level[e.prerequisite_id]
                for e in self._prerequisites_of.get(node_id, [])
                if e.prerequisite_id in nodes
            ]
            level[node_id] = max(prereq_levels) + 1 if prereq_levels else 0

        depth = max(level.values(), default=-1) + 1
        grouped: list[list[uuid.UUID]] = [[] for _ in range(depth)]
        for node_id in order:  # order is already deterministic
            grouped[level[node_id]].append(node_id)
        return grouped

    def longest_prerequisite_chain(self, skill_id: uuid.UUID) -> list[uuid.UUID]:
        """The critical path: the deepest chain of prerequisites below a skill.

        Its length is the minimum number of sequential steps before the skill
        can be attempted, regardless of how much is studied in parallel.
        """
        closure = self.required_closure([skill_id])
        order = self.topological_order(closure)

        best_len: dict[uuid.UUID, int] = {}
        best_prev: dict[uuid.UUID, uuid.UUID | None] = {}
        for node_id in order:
            candidates = [
                (best_len[e.prerequisite_id], e.prerequisite_id)
                for e in self._prerequisites_of.get(node_id, [])
                if e.prerequisite_id in best_len
            ]
            if candidates:
                # Deterministic tie-break among equally long chains.
                best = max(candidates, key=lambda c: (c[0], self.sort_key(c[1])))
                best_len[node_id] = best[0] + 1
                best_prev[node_id] = best[1]
            else:
                best_len[node_id] = 1
                best_prev[node_id] = None

        chain: list[uuid.UUID] = []
        cursor: uuid.UUID | None = skill_id
        while cursor is not None:
            chain.append(cursor)
            cursor = best_prev.get(cursor)
        chain.reverse()
        return chain

    # --- validation ------------------------------------------------------
    def validate_order(self, sequence: Sequence[uuid.UUID]) -> ValidationResult:
        """Check a proposed learning order against the graph.

        A hard prerequisite that is absent or appears too late is an *error*;
        soft and recommended edges produce *warnings*. Duplicate entries are
        resolved to their first position.
        """
        position: dict[uuid.UUID, int] = {}
        for index, skill_id in enumerate(sequence):
            position.setdefault(skill_id, index)

        unknown = tuple(
            sorted((s for s in position if s not in self._nodes), key=self.sort_key)
        )

        violations: list[OrderViolation] = []
        for skill_id, index in position.items():
            for edge in self.prerequisites_of(skill_id):
                prereq_index = position.get(edge.prerequisite_id)
                blocking = edge.relationship_type in BLOCKING_RELATIONSHIPS
                severity: Literal["error", "warning"] = "error" if blocking else "warning"

                if prereq_index is None:
                    violations.append(
                        OrderViolation(
                            skill_id=skill_id,
                            prerequisite_id=edge.prerequisite_id,
                            relationship_type=edge.relationship_type,
                            reason="missing_prerequisite",
                            skill_position=index,
                            prerequisite_position=None,
                            severity=severity,
                        )
                    )
                elif prereq_index > index:
                    violations.append(
                        OrderViolation(
                            skill_id=skill_id,
                            prerequisite_id=edge.prerequisite_id,
                            relationship_type=edge.relationship_type,
                            reason="out_of_order",
                            skill_position=index,
                            prerequisite_position=prereq_index,
                            severity=severity,
                        )
                    )

        violations.sort(
            key=lambda v: (v.skill_position, self.sort_key(v.prerequisite_id), v.reason)
        )

        missing = self.required_closure(position.keys()) - set(position)
        return ValidationResult(
            is_valid=not any(v.severity == "error" for v in violations),
            violations=tuple(violations),
            missing_prerequisites=tuple(sorted(missing, key=self.sort_key)),
            unknown_skills=unknown,
        )
