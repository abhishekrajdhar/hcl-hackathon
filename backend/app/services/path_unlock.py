"""Milestone unlocking rules shared by the adaptive service and the roadmap.

Two ways forward exist. A strong assessment score is the fast unlock — the
adaptive engine's threshold decision. This module adds the safety net: when a
learner has finished or skipped everything actionable, the next milestone
opens on material exhaustion, because a milestone without an assessment (or a
learner who completed every resource before taking one) must never dead-end
the whole roadmap behind a lock nothing can open.
"""

from __future__ import annotations

from app.models.enums import PathItemStatus
from app.models.path import LearningPathItem


def first_locked_milestone(items: list[LearningPathItem]) -> list[LearningPathItem]:
    """The items of the earliest locked milestone, in order — empty if none."""
    locked = sorted(
        (i for i in items if i.status == PathItemStatus.LOCKED),
        key=lambda i: i.order_index,
    )
    if not locked:
        return []
    target = locked[0]
    key = (target.rationale_trace or {}).get("milestone") or target.title
    return [
        i
        for i in locked
        if ((i.rationale_trace or {}).get("milestone") or i.title) == key
        and i.milestone_index == target.milestone_index
    ]


def unlock_if_exhausted(items: list[LearningPathItem]) -> list[LearningPathItem]:
    """Open the next milestone when nothing actionable remains.

    Returns the items newly made available (empty when the learner still has
    open work, or when nothing is locked). Mutates statuses in place; the
    caller owns the flush/commit.
    """
    if not items:
        return []
    if any(
        i.status in (PathItemStatus.AVAILABLE, PathItemStatus.IN_PROGRESS) for i in items
    ):
        return []
    group = first_locked_milestone(items)
    for item in group:
        item.status = PathItemStatus.AVAILABLE
    return group
