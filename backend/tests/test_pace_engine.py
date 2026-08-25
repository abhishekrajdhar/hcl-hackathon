"""Unit tests for the learning-pace model (no DB, no clock)."""

from __future__ import annotations

from app.engines.progress import (
    CompletedEffort,
    adjusted_remaining_minutes,
    compute_pace,
    weeks_remaining,
)


def test_too_few_items_is_unknown_not_a_guess() -> None:
    pace = compute_pace([CompletedEffort(60, 120), CompletedEffort(60, 120)])
    assert pace.label == "unknown"
    assert pace.ratio == 1.0
    assert not pace.is_reliable


def test_slower_learner() -> None:
    pace = compute_pace([CompletedEffort(60, 90)] * 4)
    assert pace.label == "slower"
    assert pace.ratio == 1.5


def test_faster_learner() -> None:
    pace = compute_pace([CompletedEffort(100, 50)] * 3)
    assert pace.label == "faster"
    assert pace.ratio == 0.5


def test_on_track_band() -> None:
    assert compute_pace([CompletedEffort(100, 100)] * 3).label == "on_track"
    assert compute_pace([CompletedEffort(100, 110)] * 3).label == "on_track"


def test_items_without_a_measurement_are_skipped_not_counted_as_instant() -> None:
    items = [CompletedEffort(60, 90), CompletedEffort(60, 90), CompletedEffort(60, 90),
             CompletedEffort(60, 0), CompletedEffort(0, 45)]
    pace = compute_pace(items)
    assert pace.sample_size == 3
    assert pace.ratio == 1.5


def test_ratio_is_clamped_against_one_mislogged_session() -> None:
    pace = compute_pace([CompletedEffort(1, 10_000)] * 3)
    assert pace.ratio == 4.0


def test_unknown_pace_leaves_the_estimate_alone() -> None:
    pace = compute_pace([])
    assert adjusted_remaining_minutes(600, pace) == 600


def test_remaining_is_rescaled_to_the_learners_tempo() -> None:
    pace = compute_pace([CompletedEffort(60, 90)] * 4)
    assert adjusted_remaining_minutes(600, pace) == 900


def test_weeks_needs_a_budget_to_divide_by() -> None:
    pace = compute_pace([CompletedEffort(60, 90)] * 4)
    assert weeks_remaining(adjusted_remaining_minutes(600, pace), None) is None
    assert weeks_remaining(adjusted_remaining_minutes(600, pace), 5) == 3.0


def test_nothing_left_is_zero_not_a_forecast() -> None:
    pace = compute_pace([CompletedEffort(60, 90)] * 4)
    assert adjusted_remaining_minutes(0, pace) == 0
    assert weeks_remaining(0, 10) is None
