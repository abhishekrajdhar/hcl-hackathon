"""Unit tests for the pure skill-gap engine. No database, no model."""

from __future__ import annotations

import random
import uuid

from app.engines.skill_gap import GapWeights, RequiredSkill, analyze_gaps
from app.engines.skill_graph import GraphEdge, GraphNode, SkillGraph
from app.models.enums import RelationshipType as RT


def _graph(edges: list[tuple[str, str]], difficulty: dict[str, int] | None = None):
    names = {n for e in edges for n in e}
    ids = {n: uuid.uuid5(uuid.NAMESPACE_DNS, n) for n in names}
    difficulty = difficulty or {}
    nodes = [
        GraphNode(id=ids[n], slug=n, name=n.replace("-", " ").title(), difficulty=difficulty.get(n, 1))
        for n in names
    ]
    graph_edges = [
        GraphEdge(source_id=ids[s], prerequisite_id=ids[p], relationship_type=RT.HARD_PREREQUISITE)
        for s, p in edges
    ]
    return SkillGraph(nodes, graph_edges), ids


# The ML-engineer example from the task.
def _ml_setup():
    graph, ids = _graph(
        [
            ("machine-learning", "python"),
            ("machine-learning", "statistics"),
            ("machine-learning", "linear-algebra"),
            ("neural-networks", "machine-learning"),
            ("neural-networks", "linear-algebra"),
            ("deep-learning", "neural-networks"),
            ("pytorch", "python"),
            ("mlops", "machine-learning"),
        ],
        difficulty={"python": 1, "statistics": 2, "linear-algebra": 3, "machine-learning": 3,
                    "neural-networks": 4, "deep-learning": 4, "pytorch": 3, "mlops": 4},
    )
    required = {
        ids["python"]: RequiredSkill(0.8, 1.0),
        ids["statistics"]: RequiredSkill(0.7, 0.9),
        ids["machine-learning"]: RequiredSkill(0.8, 1.0),
        ids["deep-learning"]: RequiredSkill(0.7, 0.8),
        ids["pytorch"]: RequiredSkill(0.6, 0.6),
        ids["mlops"]: RequiredSkill(0.5, 0.5),
    }
    current = {ids["python"]: 0.9, ids["statistics"]: 0.4, ids["machine-learning"]: 0.3, ids["deep-learning"]: 0.1}
    return graph, ids, required, current


def test_gap_is_required_minus_current_and_positive_only() -> None:
    graph, ids, required, current = _ml_setup()
    res = analyze_gaps(required, current, graph)
    by = {g.skill_id: g for g in res.ranked_gaps}
    # python met (0.9 >= 0.8) -> excluded, reported as a met target
    assert ids["python"] not in by
    assert ids["python"] in res.met_target_ids
    assert round(by[ids["statistics"]].gap, 2) == 0.30
    assert round(by[ids["machine-learning"]].gap, 2) == 0.50
    assert round(by[ids["deep-learning"]].gap, 2) == 0.60


def test_prerequisites_precede_dependents() -> None:
    graph, ids, required, current = _ml_setup()
    order = [g.skill_id for g in analyze_gaps(required, current, graph).ranked_gaps]
    pos = {sid: i for i, sid in enumerate(order)}
    assert pos[ids["statistics"]] < pos[ids["machine-learning"]]
    assert pos[ids["linear-algebra"]] < pos[ids["machine-learning"]]
    assert pos[ids["machine-learning"]] < pos[ids["neural-networks"]]
    assert pos[ids["neural-networks"]] < pos[ids["deep-learning"]]
    assert pos[ids["machine-learning"]] < pos[ids["mlops"]]


def test_not_sorted_by_gap_size() -> None:
    graph, ids, required, current = _ml_setup()
    res = analyze_gaps(required, current, graph)
    order = [g.skill_id for g in res.ranked_gaps]
    # deep-learning has the largest target gap (0.60) but must not be first;
    # a foundational, smaller-gap skill leads.
    assert order[0] != ids["deep-learning"]
    assert order[-1] in (ids["deep-learning"], ids["mlops"])
    # explicit proof it is not a gap-desc sort:
    gaps_in_order = [g.gap for g in res.ranked_gaps]
    assert gaps_in_order != sorted(gaps_in_order, reverse=True)


def test_transitive_prerequisites_pulled_in_as_gaps() -> None:
    graph, ids, required, current = _ml_setup()
    res = analyze_gaps(required, current, graph)
    gap_ids = {g.skill_id for g in res.ranked_gaps}
    # linear-algebra and neural-networks are not explicit targets but are pulled in.
    assert ids["linear-algebra"] in gap_ids
    assert ids["neural-networks"] in gap_ids
    la = res.gap_for(ids["linear-algebra"])
    assert la is not None and la.is_target is False


def test_met_skill_prerequisites_not_pulled_in() -> None:
    # python(met) requires programming-fundamentals; it must NOT become a gap.
    graph, ids = _graph([("python", "programming-fundamentals"), ("ml", "python"), ("ml", "statistics")])
    required = {ids["python"]: RequiredSkill(0.8), ids["ml"]: RequiredSkill(0.8), ids["statistics"]: RequiredSkill(0.7)}
    current = {ids["python"]: 0.9, ids["ml"]: 0.3, ids["statistics"]: 0.4}
    gap_ids = {g.skill_id for g in analyze_gaps(required, current, graph).ranked_gaps}
    assert ids["programming-fundamentals"] not in gap_ids
    assert gap_ids == {ids["statistics"], ids["ml"]}


def test_foundational_skill_ranks_above_bigger_gap() -> None:
    graph, ids, required, current = _ml_setup()
    res = analyze_gaps(required, current, graph)
    stats = res.gap_for(ids["statistics"])
    deep = res.gap_for(ids["deep-learning"])
    # statistics (gap 0.30) unblocks more and is foundational -> higher priority
    # AND earlier rank than deep-learning (gap 0.60).
    assert stats.priority > deep.priority
    assert stats.rank < deep.rank
    assert stats.downstream_count > deep.downstream_count


def test_priority_skills_are_learnable_now() -> None:
    graph, ids, required, current = _ml_setup()
    res = analyze_gaps(required, current, graph)
    # every priority skill has no unmet prerequisite in the gap set (level 0)
    by = {g.skill_id: g for g in res.ranked_gaps}
    for sid in res.priority_skill_ids:
        assert by[sid].level == 0
        assert by[sid].unmet_prerequisite_ids == ()


def test_reason_is_populated_and_deterministic() -> None:
    graph, ids, required, current = _ml_setup()
    a = analyze_gaps(required, current, graph)
    b = analyze_gaps(required, current, graph)
    assert all(g.reason for g in a.ranked_gaps)
    assert [g.reason for g in a.ranked_gaps] == [g.reason for g in b.ranked_gaps]


def test_ordering_is_deterministic_across_shuffles() -> None:
    graph, ids, required, current = _ml_setup()
    baseline = [g.skill_id for g in analyze_gaps(required, current, graph).ranked_gaps]
    rng = random.Random(0)
    for _ in range(25):
        nodes = [graph.node(nid) for nid in graph.node_ids]
        edges = list(graph.edges)
        rng.shuffle(nodes)
        rng.shuffle(edges)
        shuffled = SkillGraph(nodes, edges)
        assert [g.skill_id for g in analyze_gaps(required, current, shuffled).ranked_gaps] == baseline


def test_no_gaps_when_learner_meets_everything() -> None:
    graph, ids = _graph([("ml", "python")])
    required = {ids["ml"]: RequiredSkill(0.5), ids["python"]: RequiredSkill(0.5)}
    current = {ids["ml"]: 0.9, ids["python"]: 0.9}
    res = analyze_gaps(required, current, graph)
    assert res.ranked_gaps == ()
    assert set(res.met_target_ids) == {ids["ml"], ids["python"]}


def test_unknown_required_skill_is_reported() -> None:
    graph, ids = _graph([("ml", "python")])
    ghost = uuid.uuid4()
    required = {ids["ml"]: RequiredSkill(0.8), ghost: RequiredSkill(0.8)}
    res = analyze_gaps(required, {}, graph)
    assert ghost in res.unknown_skill_ids


def test_weights_change_priority_ordering() -> None:
    graph, ids, required, current = _ml_setup()
    gap_heavy = analyze_gaps(required, current, graph, weights=GapWeights(gap=1.0, downstream=0, importance=0, readiness=0))
    # With gap the only factor, the priority score must equal the (clamped) gap.
    for g in gap_heavy.ranked_gaps:
        assert abs(g.priority - min(1.0, g.gap)) < 1e-6
