"""Career-discovery request/response shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CareerDiscoveryRequest(BaseModel):
    """What the uncertain learner can tell us. Everything optional — an empty
    request returns the browsable catalogue rather than an error."""

    interests: list[str] = Field(default_factory=list, max_length=32)
    free_text: str = Field(default="", max_length=2000)
    top_k: int = Field(default=3, ge=1, le=7)


class CareerTargetSkill(BaseModel):
    skill_slug: str
    required_level: float


class CareerSuggestionRead(BaseModel):
    slug: str
    title: str
    pitch: str
    score: float
    #: Transparent evidence for the ranking, e.g. "matches your interest in ...".
    reasons: list[str]
    #: Feeds straight into POST /learning-path/generate.
    target_skills: list[CareerTargetSkill]


class CareerDiscoveryResponse(BaseModel):
    count: int
    careers: list[CareerSuggestionRead]
