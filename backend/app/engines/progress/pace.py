"""Deterministic learning-pace model.

The roadmap is planned from *estimated* effort; the event log records *actual*
minutes. Comparing the two says whether this learner runs fast or slow against
the catalogue's estimates, and that ratio is what turns a static plan into a
realistic forecast.

Pure arithmetic — no DB, no clock, no model. The caller supplies "now" and the
completed items, so the same inputs always produce the same forecast.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

PaceLabel = Literal["faster", "on_track", "slower", "unknown"]

#: Below this many completed items the ratio is noise, not a pace.
MIN_ITEMS_FOR_PACE = 3
#: Ratios inside this band read as "as planned" rather than fast or slow.
ON_TRACK_LOW = 0.85
ON_TRACK_HIGH = 1.15
#: Clamp: one mis-logged marathon session must not distort every forecast.
MIN_RATIO = 0.25
MAX_RATIO = 4.0


@dataclass(frozen=True, slots=True)
class CompletedEffort:
    """One finished item: what it was planned to take, and what it took."""

    estimated_minutes: int
    actual_minutes: int


@dataclass(frozen=True, slots=True)
class Pace:
    #: actual ÷ estimated. >1 means slower than the catalogue predicted.
    ratio: float
    label: PaceLabel
    sample_size: int
    #: Minutes actually spent across the sampled items.
    actual_minutes: int
    estimated_minutes: int

    @property
    def is_reliable(self) -> bool:
        return self.label != "unknown"


def compute_pace(items: Sequence[CompletedEffort]) -> Pace:
    """Actual-versus-estimated effort over the learner's finished items.

    Items with no estimate or no recorded time are skipped rather than counted
    as instant — a missing measurement is not a fast one.
    """
    usable = [i for i in items if i.estimated_minutes > 0 and i.actual_minutes > 0]
    estimated = sum(i.estimated_minutes for i in usable)
    actual = sum(i.actual_minutes for i in usable)

    if len(usable) < MIN_ITEMS_FOR_PACE or estimated <= 0:
        return Pace(
            ratio=1.0,
            label="unknown",
            sample_size=len(usable),
            actual_minutes=actual,
            estimated_minutes=estimated,
        )

    ratio = min(MAX_RATIO, max(MIN_RATIO, actual / estimated))
    if ratio < ON_TRACK_LOW:
        label: PaceLabel = "faster"
    elif ratio > ON_TRACK_HIGH:
        label = "slower"
    else:
        label = "on_track"
    return Pace(
        ratio=round(ratio, 4),
        label=label,
        sample_size=len(usable),
        actual_minutes=actual,
        estimated_minutes=estimated,
    )


def adjusted_remaining_minutes(remaining_estimated: int, pace: Pace) -> int:
    """Re-estimate the rest of the roadmap in this learner's own tempo."""
    if remaining_estimated <= 0:
        return 0
    if not pace.is_reliable:
        return remaining_estimated
    return int(round(remaining_estimated * pace.ratio))


def weeks_remaining(adjusted_minutes: int, weekly_hours: int | None) -> float | None:
    """How many weeks the remainder takes at the learner's stated budget.

    None when there is no budget to divide by — a forecast without one would be
    invented.
    """
    if not weekly_hours or weekly_hours <= 0 or adjusted_minutes <= 0:
        return None
    return round(adjusted_minutes / 60 / weekly_hours, 1)
