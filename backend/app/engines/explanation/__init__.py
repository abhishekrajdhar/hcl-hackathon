"""Deterministic explanation templates and the grounding safeguard."""

from app.engines.explanation.grounding import GroundingResult, check_grounding
from app.engines.explanation.templates import render_template

__all__ = ["GroundingResult", "check_grounding", "render_template"]
