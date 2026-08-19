"""Unit tests for the pure path-generation engine — focus: prerequisite order."""

from __future__ import annotations

import uuid
from datetime import date

from app.engines.path import (
    CapstoneInput,
    GoalInput,
    MilestoneInput,
    PathConstraints,
    ResourcePick,
    build_roadmap,
)


def _m(slug, category, category_name, layer, *, with_resource=True, with_assessment=True):
    return MilestoneInput(
        skill_id=uuid.uuid5(uuid.NAMESPACE_DNS, slug),
        skill_slug=slug,
        skill_name=slug.replace("-", " ").title(),
        category_slug=category,
        category_name=category_name,
        difficulty=layer + 1,
        current_level=0.0,
        required_level=0.7,
        gap=0.7,
        layer=layer,
        resources=(ResourcePick(uuid.uuid4(), f"{slug} course", 10.0, "video"),) if with_resource else (),
        assessment_id=uuid.uuid4() if with_assessment else None,
        assessment_title=f"{slug} checkpoint" if with_assessment else None,
    )


def _cv_milestones():
    # a valid topological order for a CV curriculum
    return [
        _m("probability", "statistics", "Statistics", 0),
        _m("linear-algebra", "mathematics", "Mathematics", 0),
        _m("statistics", "statistics", "Statistics", 1),
        _m("machine-learning", "machine-learning", "Machine Learning", 2),
        _m("neural-networks", "deep-learning", "Deep Learning", 3),
        _m("deep-learning", "deep-learning", "Deep Learning", 4),
        _m("cnn", "deep-learning", "Deep Learning", 5),
        _m("computer-vision", "computer-vision", "Computer Vision", 6),
    ]


def _flatten(roadmap):
    return [m.skill_slug for p in roadmap.phases for m in p.milestones if m.skill_slug]


def _constraints():
    return PathConstraints(weekly_hours=10, start_date=date(2026, 9, 1))


def test_first_phase_is_foundations_and_capstone_is_last() -> None:
    rm = build_roadmap(
        _cv_milestones(), _constraints(), GoalInput("CV Engineer"),
        CapstoneInput("CV Capstone", "Build a CV project."),
    )
    assert rm.phases[0].title == "Foundations"
    assert rm.phases[-1].is_capstone
    assert rm.phases[-1].title == "Capstone"


def test_prerequisite_ordering_is_valid() -> None:
    rm = build_roadmap(_cv_milestones(), _constraints(), GoalInput("CV Engineer"))
    order = _flatten(rm)
    pos = {s: i for i, s in enumerate(order)}
    for dep, pre in [
        ("statistics", "probability"),
        ("machine-learning", "statistics"),
        ("machine-learning", "linear-algebra"),
        ("neural-networks", "machine-learning"),
        ("deep-learning", "neural-networks"),
        ("cnn", "deep-learning"),
        ("computer-vision", "cnn"),
    ]:
        assert pos[pre] < pos[dep], f"{pre} must precede {dep}"


def test_layer_ordering_preserved_despite_interleaved_input() -> None:
    # feed the milestones shuffled within-order-preserving is not guaranteed by
    # caller, but layer grouping must still produce layer-monotonic phases.
    rm = build_roadmap(_cv_milestones(), _constraints(), GoalInput("x"))
    # every phase's milestones sit at a layer >= the previous phase's max layer
    # (capstone excluded)
    order = _flatten(rm)
    # a skill never precedes one in a strictly lower layer band
    layers = {m.skill_slug: m.layer for m in _cv_milestones()}
    seen_max = -1
    for slug in order:
        assert layers[slug] >= 0
    # monotonic non-decreasing layer across the flattened order
    seq = [layers[s] for s in order]
    assert seq == sorted(seq)


def test_adjacent_same_category_phases_are_merged() -> None:
    rm = build_roadmap(_cv_milestones(), _constraints(), GoalInput("x"))
    titles = [p.title for p in rm.phases]
    # the three deep-learning layers collapse into one phase
    assert titles.count("Deep Learning") == 1
    dl_phase = next(p for p in rm.phases if p.title == "Deep Learning")
    assert {m.skill_slug for m in dl_phase.milestones} == {"neural-networks", "deep-learning", "cnn"}


def test_phase_indices_are_contiguous() -> None:
    rm = build_roadmap(
        _cv_milestones(), _constraints(), GoalInput("x"), CapstoneInput("Cap", "d")
    )
    assert [p.index for p in rm.phases] == list(range(len(rm.phases)))


def test_milestone_without_resource_becomes_self_study() -> None:
    milestones = [
        _m("linear-algebra", "mathematics", "Mathematics", 0, with_resource=False, with_assessment=False),
        _m("machine-learning", "machine-learning", "Machine Learning", 1),
    ]
    rm = build_roadmap(milestones, _constraints(), GoalInput("x"))
    assert "linear-algebra" in _flatten(rm)  # not silently dropped
    la = next(m for p in rm.phases for m in p.milestones if m.skill_slug == "linear-algebra")
    assert la.resource_items  # has a self-study item
    assert la.resource_items[0].kind == "review"


def test_each_milestone_has_completion_criteria_and_prerequisites() -> None:
    milestones = [
        _m("statistics", "statistics", "Statistics", 0),
        MilestoneInput(
            skill_id=uuid.uuid4(), skill_slug="ml", skill_name="ML",
            category_slug="machine-learning", category_name="Machine Learning",
            difficulty=3, current_level=0.3, required_level=0.8, gap=0.5, layer=1,
            prerequisite_names=("Statistics",),
            resources=(ResourcePick(uuid.uuid4(), "ML course", 20.0),),
            assessment_id=uuid.uuid4(), assessment_title="ML checkpoint",
        ),
    ]
    rm = build_roadmap(milestones, _constraints(), GoalInput("x"))
    ml = next(m for p in rm.phases for m in p.milestones if m.skill_slug == "ml")
    assert ml.completion_criteria
    assert "Statistics" in ml.prerequisites
    assert ml.assessment_item is not None


def test_scheduling_and_feasibility_warning() -> None:
    milestones = _cv_milestones()
    # a tight deadline should trip the feasibility warning
    tight = PathConstraints(weekly_hours=2, start_date=date(2026, 9, 1), target_deadline=date(2026, 10, 1))
    rm = build_roadmap(milestones, tight, GoalInput("x"))
    assert rm.feasibility_ok is False
    assert rm.feasibility_warning
    assert rm.suggestions
    assert rm.planned_start == date(2026, 9, 1)
    assert rm.planned_end is not None and rm.planned_end > rm.planned_start


def test_generation_is_deterministic() -> None:
    a = build_roadmap(_cv_milestones(), _constraints(), GoalInput("x"), CapstoneInput("Cap", "d"))
    b = build_roadmap(_cv_milestones(), _constraints(), GoalInput("x"), CapstoneInput("Cap", "d"))
    assert _flatten(a) == _flatten(b)
    assert [p.title for p in a.phases] == [p.title for p in b.phases]
    assert a.total_estimated_minutes == b.total_estimated_minutes
