"""Deterministic hybrid recommendation ranking."""

from app.engines.recommendation.history import (
    CatalogueEntry,
    DeclaredCourse,
    build_suppressions,
    match_declared_courses,
)
from app.engines.recommendation.scoring import (
    CandidateResource,
    LearnerContext,
    RecommendationWeights,
    ResourcePrerequisite,
    ScoredResource,
    ScoringConfig,
    TaughtSkill,
    score_resource,
    top_factors,
)

__all__ = [
    "CandidateResource",
    "CatalogueEntry",
    "DeclaredCourse",
    "build_suppressions",
    "match_declared_courses",
    "LearnerContext",
    "RecommendationWeights",
    "ResourcePrerequisite",
    "ScoredResource",
    "ScoringConfig",
    "TaughtSkill",
    "score_resource",
    "top_factors",
]
