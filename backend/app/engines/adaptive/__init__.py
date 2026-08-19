"""Deterministic adaptive-learning engine: proficiency updates and decisions."""

from app.engines.adaptive.decisions import (
    AdaptiveDecision,
    LevelBand,
    decide,
    level_band,
)
from app.engines.adaptive.proficiency_updater import (
    recover_previous,
    update_from_assessment,
    update_from_completion,
)

__all__ = [
    "AdaptiveDecision",
    "LevelBand",
    "decide",
    "level_band",
    "recover_previous",
    "update_from_assessment",
    "update_from_completion",
]
