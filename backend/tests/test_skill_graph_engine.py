"""Unit tests for the pure skill-graph engine.

No database: these construct a graph in memory and exercise the deterministic
algorithms directly, which is the whole point of keeping the engine pure.
"""

from __future__ import annotations

import random
import uuid

import pytest

from app.engines.skill_graph import CycleError, GraphEdge, GraphNode, SkillGraph
from app.models.enums import RelationshipType as RT


def _id(slug: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, slug)


# The chain from the task, plus statistics -> machine-learning.
CHAIN = {
    "python": 1,
    "numpy": 2,
    "statistics": 2,
    "machine-learning": 3,
    "deep-learning": 4,
    "cnn": 4,
    "computer-vision": 4,
}
CHAIN_EDGES = [
    ("numpy", "python"),
    ("machine-learning", "numpy"),
    ("machine-learning", "statistics"),
    ("deep-learning", "machine-learning"),
    ("cnn", "deep-learning"),
    ("computer-vision", "cnn"),
]


def build_graph(
    difficulties: dict[str, int],
    edges: list[tuple[str, str]],
    *,
    edge_type: RT = RT.HARD_PREREQUISITE,
) -> SkillGraph:
    nodes = [
        GraphNode(id=_id(slug), slug=slug, name=slug.title(), difficulty=diff)
        for slug, diff in difficulties.items()
    ]
    graph_edges = [
        GraphEdge(source_id=_id(s), prerequisite_id=_id(p), relationship_type=edge_type)
        for s, p in edges
    ]
    return SkillGraph(nodes, graph_edges)


@pytest.fixture
def chain_graph() -> SkillGraph:
    return build_graph(CHAIN, CHAIN_EDGES)


def slugs(graph: SkillGraph, ids: list[uuid.UUID]) -> list[str]:
    return [graph.node(i).slug for i in ids]  # type: ignore[union-attr]


# --- prerequisite & dependency retrieval -----------------------------------
def test_direct_prerequisites(chain_graph: SkillGraph) -> None:
    prereqs = {
        chain_graph.node(e.prerequisite_id).slug  # type: ignore[union-attr]
        for e in chain_graph.prerequisites_of(_id("machine-learning"))
    }
    assert prereqs == {"numpy", "statistics"}


def test_direct_dependents(chain_graph: SkillGraph) -> None:
    dependents = {
        chain_graph.node(e.source_id).slug  # type: ignore[union-attr]
        for e in chain_graph.dependents_of(_id("machine-learning"))
    }
    assert dependents == {"deep-learning"}


def test_transitive_ancestors_with_depths(chain_graph: SkillGraph) -> None:
    ancestors = chain_graph.ancestors(_id("computer-vision"))
    by_slug = {chain_graph.node(i).slug: d for i, d in ancestors.items()}  # type: ignore[union-attr]
    assert by_slug == {
        "cnn": 1,
        "deep-learning": 2,
        "machine-learning": 3,
        "numpy": 4,
        "statistics": 4,
        "python": 5,
    }


def test_transitive_descendants(chain_graph: SkillGraph) -> None:
    descendants = chain_graph.descendants(_id("python"))
    assert _id("computer-vision") in descendants
    assert descendants[_id("numpy")] == 1


def test_required_closure_prunes_known_skills(chain_graph: SkillGraph) -> None:
    full = chain_graph.required_closure([_id("machine-learning")])
    # sort_key is (difficulty, slug): numpy and statistics tie on difficulty 2,
    # so numpy sorts first alphabetically.
    assert slugs(chain_graph, sorted(full, key=chain_graph.sort_key)) == [
        "python",
        "numpy",
        "statistics",
        "machine-learning",
    ]
    pruned = chain_graph.required_closure([_id("machine-learning")], stop_at=[_id("numpy")])
    pruned_slugs = {chain_graph.node(i).slug for i in pruned}  # type: ignore[union-attr]
    # numpy (known) and python (only reachable through numpy) drop out.
    assert pruned_slugs == {"machine-learning", "statistics"}


# --- topological ordering --------------------------------------------------
def test_topological_order_respects_prerequisites(chain_graph: SkillGraph) -> None:
    order = slugs(chain_graph, chain_graph.topological_order())
    assert order.index("python") < order.index("numpy")
    assert order.index("numpy") < order.index("machine-learning")
    assert order.index("statistics") < order.index("machine-learning")
    assert order.index("machine-learning") < order.index("deep-learning")
    assert order.index("deep-learning") < order.index("cnn")
    assert order.index("cnn") < order.index("computer-vision")


def test_topological_order_is_deterministic(chain_graph: SkillGraph) -> None:
    baseline = chain_graph.topological_order()
    nodes = [
        GraphNode(id=_id(s), slug=s, name=s, difficulty=d) for s, d in CHAIN.items()
    ]
    edges = [
        GraphEdge(source_id=_id(s), prerequisite_id=_id(p)) for s, p in CHAIN_EDGES
    ]
    for seed in range(25):
        rng = random.Random(seed)
        n = nodes[:]
        e = edges[:]
        rng.shuffle(n)
        rng.shuffle(e)
        assert SkillGraph(n, e).topological_order() == baseline


def test_tie_break_prefers_easier_then_alphabetical() -> None:
    # Two independent skills ready at once: lower difficulty comes first.
    graph = build_graph({"hard": 5, "easy": 1, "root": 1}, [("root", "easy"), ("root", "hard")])
    order = slugs(graph, graph.topological_order())
    assert order == ["easy", "hard", "root"]


def test_layers_group_parallel_skills(chain_graph: SkillGraph) -> None:
    layers = [set(slugs(chain_graph, layer)) for layer in chain_graph.layers()]
    assert {"python", "statistics"} == layers[0]
    assert layers[1] == {"numpy"}
    assert layers[2] == {"machine-learning"}


def test_longest_prerequisite_chain(chain_graph: SkillGraph) -> None:
    chain = slugs(chain_graph, chain_graph.longest_prerequisite_chain(_id("computer-vision")))
    assert chain == [
        "python",
        "numpy",
        "machine-learning",
        "deep-learning",
        "cnn",
        "computer-vision",
    ]


# --- cycle detection -------------------------------------------------------
def test_acyclic_graph_reports_no_cycles(chain_graph: SkillGraph) -> None:
    assert chain_graph.is_acyclic()
    assert chain_graph.detect_cycles() == []


def test_detect_direct_cycle() -> None:
    graph = build_graph({"a": 1, "b": 2}, [("a", "b"), ("b", "a")])
    cycles = graph.detect_cycles()
    assert not graph.is_acyclic()
    assert len(cycles) == 1
    assert {graph.node(i).slug for i in cycles[0]} == {"a", "b"}  # type: ignore[union-attr]


def test_detect_longer_cycle() -> None:
    graph = build_graph(
        {"a": 1, "b": 2, "c": 3}, [("a", "b"), ("b", "c"), ("c", "a")]
    )
    cycles = graph.detect_cycles()
    assert len(cycles) == 1
    assert {graph.node(i).slug for i in cycles[0]} == {"a", "b", "c"}  # type: ignore[union-attr]


def test_topological_order_raises_on_cycle() -> None:
    graph = build_graph({"a": 1, "b": 2, "c": 3}, [("a", "b"), ("b", "c"), ("c", "a")])
    with pytest.raises(CycleError) as exc:
        graph.topological_order()
    assert exc.value.cycles


def test_related_edges_never_form_cycles() -> None:
    # A related edge in the "wrong" direction must not create a cycle, because
    # related edges are excluded from the ordering graph entirely.
    graph = build_graph(
        {"a": 1, "b": 2}, [("a", "b"), ("b", "a")], edge_type=RT.RELATED
    )
    assert graph.is_acyclic()
    assert graph.topological_order()  # does not raise


# --- would_create_cycle (pre-write guard) ----------------------------------
def test_would_create_cycle_detects_back_edge(chain_graph: SkillGraph) -> None:
    # python -> computer-vision would close python..cv..python.
    path = chain_graph.would_create_cycle(_id("python"), _id("computer-vision"))
    assert path is not None
    assert path[0] == _id("python")


def test_would_create_cycle_allows_safe_edge(chain_graph: SkillGraph) -> None:
    # computer-vision -> statistics does not close a cycle.
    assert chain_graph.would_create_cycle(_id("computer-vision"), _id("statistics")) is None


def test_would_create_cycle_rejects_self_edge(chain_graph: SkillGraph) -> None:
    assert chain_graph.would_create_cycle(_id("python"), _id("python")) is not None


# --- validate order --------------------------------------------------------
def test_valid_order_passes(chain_graph: SkillGraph) -> None:
    order = chain_graph.topological_order()
    result = chain_graph.validate_order(order)
    assert result.is_valid
    assert not result.violations


def test_missing_prerequisite_is_error(chain_graph: SkillGraph) -> None:
    # deep-learning before its prerequisites, which are absent entirely.
    result = chain_graph.validate_order([_id("deep-learning")])
    assert not result.is_valid
    reasons = {v.reason for v in result.violations}
    assert "missing_prerequisite" in reasons
    assert all(v.severity == "error" for v in result.violations)
    missing = {chain_graph.node(i).slug for i in result.missing_prerequisites}  # type: ignore[union-attr]
    assert "machine-learning" in missing


def test_out_of_order_is_error(chain_graph: SkillGraph) -> None:
    # numpy after machine-learning: present but too late.
    seq = [_id("machine-learning"), _id("statistics"), _id("numpy"), _id("python")]
    result = chain_graph.validate_order(seq)
    assert not result.is_valid
    assert any(v.reason == "out_of_order" for v in result.violations)


def test_soft_prerequisite_out_of_order_is_warning_not_error() -> None:
    graph = build_graph(
        {"advanced": 3, "basics": 1},
        [("advanced", "basics")],
        edge_type=RT.SOFT_PREREQUISITE,
    )
    # advanced before basics violates a soft edge → warning, still "valid".
    result = graph.validate_order([_id("advanced"), _id("basics")])
    assert result.is_valid
    assert len(result.violations) == 1
    assert result.violations[0].severity == "warning"


def test_unknown_skill_is_reported() -> None:
    graph = build_graph({"a": 1}, [])
    ghost = _id("ghost")
    result = graph.validate_order([_id("a"), ghost])
    assert ghost in result.unknown_skills


# --- robustness ------------------------------------------------------------
def test_deep_chain_is_bounded() -> None:
    # A chain longer than MAX_TRAVERSAL_DEPTH must not hang or overflow.
    n = 60
    diffs = {f"s{i}": 1 for i in range(n)}
    edges = [(f"s{i+1}", f"s{i}") for i in range(n - 1)]
    graph = build_graph(diffs, edges)
    assert graph.is_acyclic()
    # ancestors are depth-bounded; ordering still covers the whole set.
    assert len(graph.topological_order()) == n
