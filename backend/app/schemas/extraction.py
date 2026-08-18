"""Request/response schemas for the LLM profile-extraction endpoint."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.llm.schemas import ProfileExtraction
from app.schemas.profile import ProfileDraft


class ProfileExtractRequest(BaseModel):
    user_id: uuid.UUID
    message: str = Field(min_length=1, max_length=8000)
    apply: bool = Field(
        default=False,
        description="If true, persist the extraction via ProfileService after validation.",
    )


class SkillCandidateRead(BaseModel):
    skill_id: uuid.UUID
    slug: str
    name: str
    score: float


class SkillResolutionRead(BaseModel):
    query: str
    status: Literal["matched", "ambiguous", "unknown"]
    skill_id: uuid.UUID | None = None
    slug: str | None = None
    name: str | None = None
    confidence: float
    proficiency: float | None = None
    method: str
    candidates: list[SkillCandidateRead] = Field(default_factory=list)


class ProfileExtractResponse(BaseModel):
    user_id: uuid.UUID
    provider: str
    model: str
    #: The validated structured output — exactly what the LLM produced, typed.
    extraction: ProfileExtraction
    #: Per-skill catalogue resolution (matched / ambiguous / unknown).
    resolved_skills: list[SkillResolutionRead] = Field(default_factory=list)
    #: Non-fatal business-validation findings (ambiguous goal, unknown skills…).
    warnings: list[str] = Field(default_factory=list)
    #: The deterministic draft the extraction maps to. Persisted only if applied.
    draft: ProfileDraft | None = None
    applied: bool = False
