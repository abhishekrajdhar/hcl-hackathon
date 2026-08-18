"""Deterministic learner-profile validation.

Field-level range checks belong to Pydantic; this module holds the *semantic*
checks that need several fields together or an external reference (today's
date). Pure and side-effect free: it takes a snapshot in and returns issues out,
so it is trivially unit-testable and reused by both the API and the future LLM
ingestion path.

Severity contract:
- `error`   — the profile is internally inconsistent and must be corrected.
- `warning` — accepted, but likely to produce a poor learning plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Severity = Literal["error", "warning"]

MAX_REALISTIC_WEEKLY_HOURS = 80
MIN_USEFUL_WEEKLY_HOURS = 1


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    code: str
    message: str
    severity: Severity


@dataclass(frozen=True, slots=True)
class ProfileValidationResult:
    is_valid: bool
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        return (*self.errors, *self.warnings)


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    """The subset of profile state validation reasons about."""

    weekly_hours: int
    experience_level: str
    target_deadline: date | None = None
    goal_text_raw: str | None = None
    target_role: str | None = None
    interests: tuple[str, ...] = ()
    preferred_modalities: tuple[str, ...] = ()
    skill_count: int = 0
    max_proficiency: float = 0.0
    proficiencies: tuple[float, ...] = field(default=())


def validate_profile(snapshot: ProfileSnapshot, *, today: date) -> ProfileValidationResult:
    """Run every semantic check and bucket the issues by severity."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    # --- errors: internal inconsistency ---
    if snapshot.target_deadline is not None and snapshot.target_deadline <= today:
        errors.append(
            ValidationIssue(
                field="target_deadline",
                code="deadline_in_past",
                message="Target completion date must be in the future.",
                severity="error",
            )
        )

    for value in snapshot.proficiencies:
        if not 0.0 <= value <= 1.0:
            errors.append(
                ValidationIssue(
                    field="skills",
                    code="proficiency_out_of_range",
                    message=f"Skill proficiency {value} is outside the [0, 1] range.",
                    severity="error",
                )
            )
            break

    # --- warnings: accepted but likely to plan poorly ---
    if snapshot.weekly_hours < MIN_USEFUL_WEEKLY_HOURS:
        warnings.append(
            ValidationIssue(
                field="weekly_hours",
                code="weekly_hours_too_low",
                message="With no weekly hours available, a schedule cannot be built.",
                severity="warning",
            )
        )
    elif snapshot.weekly_hours > MAX_REALISTIC_WEEKLY_HOURS:
        warnings.append(
            ValidationIssue(
                field="weekly_hours",
                code="weekly_hours_unrealistic",
                message=f"{snapshot.weekly_hours} hours/week is unusually high and may not be sustainable.",
                severity="warning",
            )
        )

    if not (snapshot.goal_text_raw or snapshot.target_role):
        warnings.append(
            ValidationIssue(
                field="goal",
                code="no_goal_or_role",
                message="Neither a learning goal nor a target role is set; recommendations will be generic.",
                severity="warning",
            )
        )

    # An expert who has reported no meaningful skill is probably mis-set.
    if snapshot.experience_level == "expert" and snapshot.skill_count and snapshot.max_proficiency < 0.5:
        warnings.append(
            ValidationIssue(
                field="experience_level",
                code="experience_skill_mismatch",
                message="Experience level is 'expert' but no skill is above 0.5 proficiency.",
                severity="warning",
            )
        )

    if snapshot.skill_count == 0:
        warnings.append(
            ValidationIssue(
                field="skills",
                code="no_skills",
                message="No current skills recorded; a diagnostic assessment is recommended.",
                severity="warning",
            )
        )

    return ProfileValidationResult(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
