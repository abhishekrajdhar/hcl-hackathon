"""Skill knowledge graph: traversal, sequencing and integrity.

The service is responsible for loading the right slice of the graph out of
Postgres and handing it to the pure algorithms in `app.engines.skill_graph`.
No decision here is delegated to a model — prerequisite ordering is a
correctness property, so it is computed, not generated.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.engines.skill_graph import CycleError, GraphEdge, GraphNode, SkillGraph
from app.engines.skill_graph.graph import MAX_TRAVERSAL_DEPTH
from app.models.enums import ORDERING_RELATIONSHIPS, RelationshipType
from app.models.skill import Prerequisite, Skill
from app.repositories.skill import PrerequisiteRepository, SkillRepository
from app.schemas.skill import (
    CycleReport,
    LearningSequenceRequest,
    LearningSequenceResponse,
    LearningSequenceStep,
    OrderViolationRead,
    PrerequisiteCreate,
    PrerequisiteTreeNode,
    PrerequisiteTreeResponse,
    PrerequisiteUpdate,
    SkillDependencyAnalysis,
    SkillGraphNode,
    SkillGraphResponse,
    SkillSummary,
    ValidateOrderResponse,
)
from app.services.base import BaseService

#: Depth cap for the recursive tree response, independent of traversal depth.
MAX_TREE_DEPTH = 12

_HARD_ONLY = frozenset({RelationshipType.HARD_PREREQUISITE})


class SkillGraphService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.skills = SkillRepository(session)
        self.prerequisites = PrerequisiteRepository(session)

    # --- loading ---------------------------------------------------------
    @staticmethod
    def _to_node(skill: Skill) -> GraphNode:
        return GraphNode(
            id=skill.id,
            slug=skill.slug,
            name=skill.name,
            difficulty=skill.difficulty,
            category_slug=skill.category.slug if skill.category is not None else None,
        )

    @staticmethod
    def _to_edge(edge: Prerequisite) -> GraphEdge:
        return GraphEdge(
            source_id=edge.source_skill_id,
            prerequisite_id=edge.prerequisite_skill_id,
            relationship_type=edge.relationship_type,
            strength=edge.strength,
            min_level=edge.min_level,
        )

    async def _load_graph(
        self,
        roots: Sequence[uuid.UUID],
        *,
        include_dependents: bool = False,
        types: Iterable[RelationshipType] | None = None,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
    ) -> tuple[SkillGraph, dict[uuid.UUID, Skill]]:
        """Pull only the subgraph reachable from `roots` and build the engine view."""
        node_ids: set[uuid.UUID] = set(roots)
        node_ids.update(await self.prerequisites.ancestor_ids(list(roots), max_depth))
        if include_dependents:
            node_ids.update(await self.prerequisites.descendant_ids(list(roots), max_depth))

        skills = {s.id: s for s in await self.skills.get_many(sorted(node_ids))}
        edges = await self.prerequisites.edges_within(sorted(node_ids))

        allowed = set(types) if types is not None else set(ORDERING_RELATIONSHIPS)
        graph = SkillGraph(
            (self._to_node(s) for s in skills.values()),
            (self._to_edge(e) for e in edges if e.relationship_type in allowed),
        )
        return graph, skills

    def _summary(self, skills: dict[uuid.UUID, Skill], skill_id: uuid.UUID) -> SkillSummary:
        skill = skills[skill_id]
        return SkillSummary(
            id=skill.id,
            slug=skill.slug,
            name=skill.name,
            difficulty=skill.difficulty,
            category_id=skill.category_id,
        )

    def _summaries(
        self, skills: dict[uuid.UUID, Skill], skill_ids: Iterable[uuid.UUID]
    ) -> list[SkillSummary]:
        return [self._summary(skills, sid) for sid in skill_ids if sid in skills]

    # --- 1. get_skill ----------------------------------------------------
    async def get_skill(self, skill_id: uuid.UUID) -> Skill:
        skill = await self.skills.get(skill_id)
        if skill is None:
            raise NotFoundError("Skill", skill_id)
        return skill

    # --- 2. get_prerequisites --------------------------------------------
    async def get_prerequisites(
        self, skill_id: uuid.UUID, *, transitive: bool = False, max_depth: int = MAX_TRAVERSAL_DEPTH
    ) -> list[Prerequisite] | list[tuple[Skill, int]]:
        """Direct prerequisites, or the whole transitive set with depths."""
        await self.get_skill(skill_id)
        if not transitive:
            return await self.prerequisites.list_prerequisites(skill_id)

        depths = await self.prerequisites.ancestor_ids([skill_id], max_depth)
        skills = {s.id: s for s in await self.skills.get_many(sorted(depths))}
        resolved = [(skills[sid], depth) for sid, depth in depths.items() if sid in skills]
        resolved.sort(key=lambda pair: (pair[1], pair[0].difficulty, pair[0].slug))
        return resolved

    # --- 3. get_dependents -----------------------------------------------
    async def get_dependents(
        self, skill_id: uuid.UUID, *, transitive: bool = False, max_depth: int = MAX_TRAVERSAL_DEPTH
    ) -> list[Prerequisite] | list[tuple[Skill, int]]:
        """Skills that require this one, directly or transitively."""
        await self.get_skill(skill_id)
        if not transitive:
            return await self.prerequisites.list_dependents(skill_id)

        depths = await self.prerequisites.descendant_ids([skill_id], max_depth)
        skills = {s.id: s for s in await self.skills.get_many(sorted(depths))}
        resolved = [(skills[sid], depth) for sid, depth in depths.items() if sid in skills]
        resolved.sort(key=lambda pair: (pair[1], pair[0].difficulty, pair[0].slug))
        return resolved

    # --- 4. get_prerequisite_tree ----------------------------------------
    async def get_prerequisite_tree(
        self, skill_id: uuid.UUID, *, max_depth: int = MAX_TREE_DEPTH
    ) -> PrerequisiteTreeResponse:
        """Nested prerequisite tree.

        The graph is a DAG, not a tree, so a shared prerequisite would otherwise
        be duplicated combinatorially. Each skill is expanded once; later
        appearances are flagged `already_visited` with no children.
        """
        root = await self.get_skill(skill_id)
        graph, skills = await self._load_graph([skill_id])
        depth_cap = max(1, min(max_depth, MAX_TREE_DEPTH))

        expanded: set[uuid.UUID] = set()
        counted: set[uuid.UUID] = set()
        deepest = 0
        truncated = False

        def build(
            current_id: uuid.UUID,
            depth: int,
            edge: GraphEdge | None,
        ) -> PrerequisiteTreeNode:
            nonlocal deepest, truncated
            deepest = max(deepest, depth)
            node = PrerequisiteTreeNode(
                skill=self._summary(skills, current_id),
                depth=depth,
                relationship_type=edge.relationship_type if edge else None,
                strength=edge.strength if edge else None,
                min_level=edge.min_level if edge else None,
            )
            if current_id in expanded:
                node.already_visited = True
                return node
            if depth >= depth_cap:
                if graph.prerequisites_of(current_id):
                    truncated = True
                return node

            expanded.add(current_id)
            for child in graph.prerequisites_of(current_id):
                if child.prerequisite_id not in skills:
                    continue
                counted.add(child.prerequisite_id)
                node.prerequisites.append(build(child.prerequisite_id, depth + 1, child))
            return node

        tree = build(root.id, 0, None)
        return PrerequisiteTreeResponse(
            root=tree,
            total_prerequisites=len(counted),
            max_depth=deepest,
            truncated=truncated,
        )

    # --- 5. validate_learning_order --------------------------------------
    async def validate_learning_order(
        self, skill_ids: Sequence[uuid.UUID]
    ) -> ValidateOrderResponse:
        """Check a proposed order. Hard-prerequisite breaches are errors."""
        graph, skills = await self._load_graph(list(skill_ids))
        result = graph.validate_order(list(skill_ids))

        violations: list[OrderViolationRead] = []
        for violation in result.violations:
            subject = skills.get(violation.skill_id)
            prereq = skills.get(violation.prerequisite_id)
            subject_name = subject.name if subject else str(violation.skill_id)
            prereq_name = prereq.name if prereq else str(violation.prerequisite_id)
            if violation.reason == "missing_prerequisite":
                message = f"'{subject_name}' requires '{prereq_name}', which is not in the sequence"
            else:
                message = (
                    f"'{prereq_name}' is at position {violation.prerequisite_position} but must "
                    f"come before '{subject_name}' at position {violation.skill_position}"
                )
            violations.append(
                OrderViolationRead(
                    skill_id=violation.skill_id,
                    prerequisite_id=violation.prerequisite_id,
                    relationship_type=violation.relationship_type,
                    reason=violation.reason,
                    severity=violation.severity,
                    skill_position=violation.skill_position,
                    prerequisite_position=violation.prerequisite_position,
                    message=message,
                )
            )

        # A correct alternative to hand back when the proposed order is wrong.
        try:
            suggested = graph.topological_order(graph.required_closure(skill_ids))
        except CycleError as exc:
            raise self._cycle_error(exc, skills) from exc

        return ValidateOrderResponse(
            is_valid=result.is_valid,
            violations=violations,
            missing_prerequisites=self._summaries(skills, result.missing_prerequisites),
            unknown_skill_ids=list(result.unknown_skills),
            suggested_order=self._summaries(skills, suggested),
        )

    # --- 6. find_learning_sequence ---------------------------------------
    async def find_learning_sequence(
        self, request: LearningSequenceRequest
    ) -> LearningSequenceResponse:
        """Deterministic, prerequisite-aware order covering every target.

        Pulls in the transitive prerequisites of the targets, drops anything the
        learner already knows (and anything only reachable through it), then
        topologically sorts with a stable tie-break: easier skills first, then
        alphabetically. Same inputs always produce the same sequence.
        """
        targets = list(dict.fromkeys(request.target_skill_ids))
        types = None if request.include_soft_prerequisites else _HARD_ONLY

        graph, skills = await self._load_graph(targets, types=types)

        missing = [str(t) for t in targets if t not in skills]
        if missing:
            raise NotFoundError("Skill", ", ".join(sorted(missing)))

        known = {k for k in request.known_skill_ids}
        closure = graph.required_closure(targets, stop_at=known)

        try:
            order = graph.topological_order(closure)
            levels = graph.layers(closure)
        except CycleError as exc:
            raise self._cycle_error(exc, skills) from exc

        level_of = {
            skill_id: index for index, group in enumerate(levels) for skill_id in group
        }
        target_set = set(targets)
        steps = [
            LearningSequenceStep(
                position=position,
                level=level_of[skill_id],
                skill=self._summary(skills, skill_id),
                is_target=skill_id in target_set,
                prerequisite_ids=[
                    edge.prerequisite_id
                    for edge in graph.prerequisites_of(skill_id)
                    if edge.prerequisite_id in closure
                ],
            )
            for position, skill_id in enumerate(order)
            if skill_id in skills
        ]

        return LearningSequenceResponse(
            sequence=steps,
            levels=[self._summaries(skills, group) for group in levels],
            total_skills=len(steps),
            target_skill_ids=targets,
            skipped_known_skill_ids=sorted(known & set(skills), key=lambda s: str(s)),
        )

    # --- 7. calculate_skill_dependencies ---------------------------------
    async def calculate_skill_dependencies(
        self, target_skill_id: uuid.UUID
    ) -> SkillDependencyAnalysis:
        """Full dependency picture for one skill, including the critical path."""
        await self.get_skill(target_skill_id)
        graph, skills = await self._load_graph([target_skill_id], include_dependents=True)

        direct = [edge.prerequisite_id for edge in graph.prerequisites_of(target_skill_id)]
        ancestors = graph.ancestors(target_skill_id)
        descendants = graph.descendants(target_skill_id)

        prerequisite_ids = set(ancestors)
        try:
            sequence = graph.topological_order(prerequisite_ids | {target_skill_id})
            levels = graph.layers(prerequisite_ids)
            critical_path = graph.longest_prerequisite_chain(target_skill_id)
        except CycleError as exc:
            raise self._cycle_error(exc, skills) from exc

        ordered_ancestors = [sid for sid in sequence if sid in prerequisite_ids]

        return SkillDependencyAnalysis(
            skill=self._summary(skills, target_skill_id),
            direct_prerequisites=self._summaries(skills, direct),
            all_prerequisites=self._summaries(skills, ordered_ancestors),
            total_prerequisites=len(prerequisite_ids),
            max_depth=max(ancestors.values(), default=0),
            critical_path=self._summaries(skills, critical_path),
            critical_path_length=len(critical_path),
            levels=[self._summaries(skills, group) for group in levels],
            learning_sequence=self._summaries(skills, sequence),
            unlocks=self._summaries(
                skills, sorted(descendants, key=lambda s: (descendants[s], str(s)))
            ),
        )

    # --- closure view (kept for the existing /graph endpoint) -------------
    async def closure_graph(
        self, skill_id: uuid.UUID, depth: int = MAX_TRAVERSAL_DEPTH
    ) -> SkillGraphResponse:
        root = await self.get_skill(skill_id)
        depths = await self.prerequisites.ancestor_ids([skill_id], min(depth, MAX_TRAVERSAL_DEPTH))
        skills = {s.id: s for s in await self.skills.get_many(sorted(depths))}

        nodes = [SkillGraphNode(skill_id=root.id, slug=root.slug, name=root.name, depth=0)]
        for skill_id_, node_depth in sorted(depths.items(), key=lambda kv: kv[1]):
            skill = skills.get(skill_id_)
            if skill is not None:
                nodes.append(
                    SkillGraphNode(
                        skill_id=skill.id, slug=skill.slug, name=skill.name, depth=node_depth
                    )
                )

        edges = await self.prerequisites.edges_within([root.id, *depths])
        return SkillGraphResponse(root_skill_id=root.id, nodes=nodes, edges=edges)  # type: ignore[arg-type]

    # --- integrity -------------------------------------------------------
    async def detect_cycles(self) -> CycleReport:
        """Whole-graph integrity check.

        Writes are guarded, so this should always come back clean; it exists to
        catch anything introduced by a bulk import or a direct SQL edit.
        """
        edges = await self.prerequisites.all_edges()
        skill_ids = {e.source_skill_id for e in edges} | {e.prerequisite_skill_id for e in edges}
        skills = {s.id: s for s in await self.skills.get_many(sorted(skill_ids))}
        graph = SkillGraph(
            (self._to_node(s) for s in skills.values()),
            (self._to_edge(e) for e in edges),
        )
        cycles = graph.detect_cycles()
        return CycleReport(
            is_acyclic=not cycles,
            cycle_count=len(cycles),
            cycles=[self._summaries(skills, cycle) for cycle in cycles],
        )

    def _cycle_error(self, exc: CycleError, skills: dict[uuid.UUID, Skill]) -> ValidationError:
        rendered = [
            " -> ".join(skills[sid].slug if sid in skills else str(sid) for sid in cycle)
            for cycle in exc.cycles
        ]
        return ValidationError(
            "The skill graph contains a prerequisite cycle, so no valid order exists",
            error_code="prerequisite_cycle",
            extra={"cycles": rendered},
        )

    # --- edge mutation (cycle-guarded) -----------------------------------
    async def add_prerequisite(self, payload: PrerequisiteCreate) -> Prerequisite:
        if payload.source_skill_id == payload.prerequisite_skill_id:
            raise ValidationError(
                "A skill cannot be its own prerequisite", error_code="self_prerequisite"
            )
        source = await self.get_skill(payload.source_skill_id)
        prerequisite = await self.get_skill(payload.prerequisite_skill_id)

        if await self.prerequisites.get_edge(source.id, prerequisite.id) is not None:
            raise ConflictError("This prerequisite edge already exists", error_code="edge_exists")

        if payload.relationship_type in ORDERING_RELATIONSHIPS:
            await self._assert_acyclic(source.id, prerequisite.id)

        await self.prerequisites.create(payload.model_dump())
        await self.commit()
        edge = await self.prerequisites.get_edge(source.id, prerequisite.id)
        assert edge is not None
        return edge

    async def _assert_acyclic(
        self, source_skill_id: uuid.UUID, prerequisite_skill_id: uuid.UUID
    ) -> None:
        """Reject an edge that would close a cycle, before it is written.

        Adding `source requires prerequisite` is a cycle exactly when `source`
        already sits in the prerequisite closure of `prerequisite`.
        """
        graph, skills = await self._load_graph([prerequisite_skill_id])
        path = graph.would_create_cycle(source_skill_id, prerequisite_skill_id)
        if path is None:
            return

        source = await self.skills.get(source_skill_id)
        rendered = [
            skills[sid].slug if sid in skills else (source.slug if source and sid == source.id else str(sid))
            for sid in path
        ]
        raise ValidationError(
            "This prerequisite would introduce a cycle in the skill graph",
            error_code="prerequisite_cycle",
            extra={
                "source_skill_id": str(source_skill_id),
                "prerequisite_skill_id": str(prerequisite_skill_id),
                "cycle": " -> ".join(rendered),
            },
        )

    async def update_prerequisite(
        self, edge_id: uuid.UUID, payload: PrerequisiteUpdate
    ) -> Prerequisite:
        edge = await self.prerequisites.get(edge_id)
        if edge is None:
            raise NotFoundError("Prerequisite", edge_id)

        data = payload.model_dump(exclude_unset=True)
        new_type = data.get("relationship_type", edge.relationship_type)
        # Promoting a `related` edge into an ordering edge can introduce a cycle.
        if (
            new_type in ORDERING_RELATIONSHIPS
            and edge.relationship_type not in ORDERING_RELATIONSHIPS
        ):
            await self._assert_acyclic(edge.source_skill_id, edge.prerequisite_skill_id)

        await self.prerequisites.update(edge, data)
        await self.commit()
        return edge

    async def delete_prerequisite(self, edge_id: uuid.UUID) -> None:
        edge = await self.prerequisites.get(edge_id)
        if edge is None:
            raise NotFoundError("Prerequisite", edge_id)
        await self.prerequisites.delete(edge)
        await self.commit()
