"""The material-exhaustion unlock rule.

A strong assessment score is the fast unlock; this rule is the safety net. A
learner who has completed or skipped everything actionable must never be left
staring at a fully-locked remainder of their roadmap — which is exactly what
happened when a milestone had no assessment to score.
"""

from __future__ import annotations

from app.models.enums import PathItemStatus, PathItemType
from app.models.path import LearningPathItem
from app.services.path_unlock import first_locked_milestone, unlock_if_exhausted


def _item(order: int, milestone: str, phase: int, status: PathItemStatus) -> LearningPathItem:
    return LearningPathItem(
        order_index=order,
        milestone_index=phase,
        title=f"item-{order}",
        item_type=PathItemType.RESOURCE,
        status=status,
        estimated_minutes=30,
        rationale_trace={"milestone": milestone},
    )


def test_exhausted_path_unlocks_exactly_the_next_milestone() -> None:
    items = [
        _item(0, "Foundations", 0, PathItemStatus.COMPLETED),
        _item(1, "Foundations", 0, PathItemStatus.COMPLETED),
        _item(2, "Python", 1, PathItemStatus.LOCKED),
        _item(3, "Python", 1, PathItemStatus.LOCKED),
        _item(4, "Docker", 2, PathItemStatus.LOCKED),
    ]
    unlocked = unlock_if_exhausted(items)
    assert [i.order_index for i in unlocked] == [2, 3], "the whole next milestone, no more"
    assert items[2].status == PathItemStatus.AVAILABLE
    assert items[3].status == PathItemStatus.AVAILABLE
    assert items[4].status == PathItemStatus.LOCKED, "later milestones stay gated"


def test_open_work_blocks_the_exhaustion_unlock() -> None:
    """An available item IS the next step — nothing should leapfrog it."""
    for blocking in (PathItemStatus.AVAILABLE, PathItemStatus.IN_PROGRESS):
        items = [
            _item(0, "Foundations", 0, blocking),
            _item(1, "Python", 1, PathItemStatus.LOCKED),
        ]
        assert unlock_if_exhausted(items) == []
        assert items[1].status == PathItemStatus.LOCKED


def test_skipped_counts_as_done() -> None:
    items = [
        _item(0, "Foundations", 0, PathItemStatus.SKIPPED),
        _item(1, "Python", 1, PathItemStatus.LOCKED),
    ]
    assert len(unlock_if_exhausted(items)) == 1
    assert items[1].status == PathItemStatus.AVAILABLE


def test_nothing_locked_means_nothing_to_do() -> None:
    items = [_item(0, "Foundations", 0, PathItemStatus.COMPLETED)]
    assert unlock_if_exhausted(items) == []
    assert unlock_if_exhausted([]) == []


def test_first_locked_milestone_groups_by_trace_and_phase() -> None:
    items = [
        _item(5, "Docker", 2, PathItemStatus.LOCKED),
        _item(2, "Python", 1, PathItemStatus.LOCKED),
        _item(3, "Python", 1, PathItemStatus.LOCKED),
    ]
    group = first_locked_milestone(items)
    assert [i.order_index for i in group] == [2, 3]
