"""Deterministic career-readiness scoring.

Answers "how close is this learner to their target role?" — not as one opaque
number, but as the composite the spec asks for: an overall figure broken into
dimensions (knowledge vs the target vector, assessment performance, project
work, momentum), with each target skill reported individually so the learner
can see exactly which gap is holding the number down.

Pure arithmetic over evidence that already exists — no DB, no clock, no model.
A dimension with no evidence is reported as such and removed from the weighted
composite rather than counted as zero: "no assessments yet" is missing data,
not failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

#: Composite weights. Renormalised over the dimensions that have evidence.
WEIGHTS = {
    "knowledge": 0.45,
    "assessments": 0.20,
    "projects": 0.20,
    "momentum": 0.15,
}

#: Momentum score by pace label — being on plan is full marks; running slower
#: than planned is a drag on readiness, not a moral failing, so it stays high.
MOMENTUM_BY_PACE = {"faster": 1.0, "on_track": 1.0, "slower": 0.6, "unknown": None}


@dataclass(frozen=True, slots=True)
class TargetSkill:
    skill_id: str
    name: str
    required_level: float
    current_level: float

    @property
    def readiness(self) -> float:
        if self.required_level <= 0:
            return 1.0
        return min(1.0, self.current_level / self.required_level)


@dataclass(frozen=True, slots=True)
class Dimension:
    key: str
    label: str
    #: 0..1, or None when there is no evidence for this dimension yet.
    score: float | None
    detail: str


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    overall: float
    dimensions: tuple[Dimension, ...]
    skills: tuple[TargetSkill, ...]
    #: The single dimension pulling the overall down hardest, for coaching copy.
    weakest: str | None


def compute_readiness(
    targets: Sequence[TargetSkill],
    assessment_percentages: Sequence[float],
    projects_completed: int,
    projects_total: int,
    pace_label: str,
) -> ReadinessReport:
    dimensions: list[Dimension] = []

    # --- knowledge vs the target vector ----------------------------------
    if targets:
        knowledge = sum(t.readiness for t in targets) / len(targets)
        gaps = [t for t in targets if t.readiness < 1.0]
        detail = (
            "every target met"
            if not gaps
            else f"{len(gaps)} of {len(targets)} target skills below requirement"
        )
        dimensions.append(Dimension("knowledge", "Technical skills", round(knowledge, 4), detail))
    else:
        dimensions.append(
            Dimension("knowledge", "Technical skills", None, "no target skills recorded yet")
        )

    # --- assessment performance -------------------------------------------
    if assessment_percentages:
        avg = sum(assessment_percentages) / len(assessment_percentages)
        dimensions.append(
            Dimension(
                "assessments", "Assessment performance", round(min(1.0, avg), 4),
                f"average over {len(assessment_percentages)} attempt(s)",
            )
        )
    else:
        dimensions.append(
            Dimension("assessments", "Assessment performance", None, "no assessments taken yet")
        )

    # --- project work ------------------------------------------------------
    if projects_total > 0:
        score = projects_completed / projects_total
        dimensions.append(
            Dimension(
                "projects", "Project work", round(score, 4),
                f"{projects_completed} of {projects_total} planned project(s) done",
            )
        )
    else:
        dimensions.append(Dimension("projects", "Project work", None, "no projects on this path"))

    # --- momentum ----------------------------------------------------------
    momentum = MOMENTUM_BY_PACE.get(pace_label)
    if momentum is not None:
        detail = "on plan" if momentum >= 1.0 else "running behind the planned pace"
        dimensions.append(Dimension("momentum", "Momentum", momentum, detail))
    else:
        dimensions.append(
            Dimension("momentum", "Momentum", None, "not enough completed items to measure")
        )

    # --- weighted composite over evidenced dimensions ----------------------
    evidenced = [(d, WEIGHTS[d.key]) for d in dimensions if d.score is not None]
    total_weight = sum(w for _, w in evidenced)
    overall = (
        sum(d.score * w for d, w in evidenced) / total_weight if total_weight > 0 else 0.0
    )

    scored = [d for d, _ in evidenced]
    weakest = min(scored, key=lambda d: d.score).key if scored else None

    return ReadinessReport(
        overall=round(overall, 4),
        dimensions=tuple(dimensions),
        skills=tuple(sorted(targets, key=lambda t: t.readiness)),
        weakest=weakest,
    )
