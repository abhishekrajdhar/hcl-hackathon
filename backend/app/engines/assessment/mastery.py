"""Deterministic mapping from assessment performance to skill mastery.

The LLM never decides a score or a mastery level — this is pure arithmetic over
the graded responses (which were themselves graded by exact match). Same result
every time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

MasteryLevel = Literal[
    "strong_mastery", "good_understanding", "partial_understanding", "requires_remediation"
]

#: Score thresholds -> mastery band (from the spec).
STRONG_THRESHOLD = 0.9
GOOD_THRESHOLD = 0.7
PARTIAL_THRESHOLD = 0.5


def mastery_level(percentage: float) -> MasteryLevel:
    if percentage >= STRONG_THRESHOLD:
        return "strong_mastery"
    if percentage >= GOOD_THRESHOLD:
        return "good_understanding"
    if percentage >= PARTIAL_THRESHOLD:
        return "partial_understanding"
    return "requires_remediation"


_ACTIONS: dict[MasteryLevel, str] = {
    "strong_mastery": "Advance to the next skill in your roadmap.",
    "good_understanding": "Proceed to the next skill.",
    "partial_understanding": "Revisit the resources for the weak topics before advancing.",
    "requires_remediation": "Remediate: restudy the fundamentals before moving on.",
}


def recommended_next_action(percentage: float, weak_topics: list[str]) -> str:
    action = _ACTIONS[mastery_level(percentage)]
    if weak_topics and percentage < STRONG_THRESHOLD:
        return f"{action} Focus on: {', '.join(weak_topics)}."
    return action


@dataclass(frozen=True, slots=True)
class WeakTopic:
    skill_id: uuid.UUID | None
    skill_name: str
    correct: int
    total: int

    @property
    def ratio(self) -> float:
        return self.correct / self.total if self.total else 0.0


def weak_topics(
    responses: list[dict],
    skill_names: dict[uuid.UUID, str],
    *,
    threshold: float = GOOD_THRESHOLD,
) -> list[WeakTopic]:
    """Per-skill topics where the learner scored below `threshold`.

    Groups graded responses by their question's skill; a skill is "weak" when
    fewer than `threshold` of its questions were correct. Deterministically
    ordered worst-first.
    """
    buckets: dict[uuid.UUID | None, list[int]] = {}
    for response in responses:
        raw = response.get("skill_id")
        skill_id = uuid.UUID(str(raw)) if raw else None
        buckets.setdefault(skill_id, []).append(1 if response.get("is_correct") else 0)

    weak: list[WeakTopic] = []
    for skill_id, marks in buckets.items():
        correct, total = sum(marks), len(marks)
        if total and correct / total < threshold:
            name = skill_names.get(skill_id, "General") if skill_id else "General"
            weak.append(WeakTopic(skill_id=skill_id, skill_name=name, correct=correct, total=total))
    return sorted(weak, key=lambda w: (w.ratio, w.skill_name))
