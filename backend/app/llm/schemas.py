"""Structured-output contracts for LLM extraction.

`ProfileExtraction` is the ONLY shape an extraction LLM is allowed to return.
It is enforced with Pydantic: the raw model output is parsed and validated into
this type before any other code touches it, and it is deliberately decoupled
from the ORM — nothing here can write to the database.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExperienceLevel


class ExtractedSkill(BaseModel):
    """A skill the learner mentioned, as understood from the text.

    `name` is free text exactly as inferred; it is resolved against the canonical
    skill catalogue later — the model never invents catalogue ids.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=128)
    proficiency: float | None = Field(
        default=None, ge=0, le=1, description="Implied proficiency in [0,1], null if unclear"
    )
    evidence: str | None = Field(
        default=None, max_length=280, description="What in the message implied this skill"
    )


class ProfileExtraction(BaseModel):
    """Validated structured profile extracted from one message.

    Every field is optional: a learner rarely states all of them, and a missing
    field must never be fabricated. `ignore` on extras means a chatty model that
    adds stray keys does not break validation.
    """

    model_config = ConfigDict(extra="ignore")

    experience_level: ExperienceLevel | None = None
    goal: str | None = Field(default=None, max_length=1000)
    target_role: str | None = Field(default=None, max_length=255)
    interests: list[str] = Field(default_factory=list, max_length=32)
    skills: list[ExtractedSkill] = Field(default_factory=list, max_length=64)
    weekly_hours: int | None = Field(default=None, ge=0, le=168)
    timeline: str | None = Field(
        default=None, max_length=128, description="Free-text timeframe, e.g. '6 months'"
    )
    learning_preferences: dict[str, Any] = Field(default_factory=dict)

    # Model-reported meta. Advisory only; the service does its own validation.
    confidence: float | None = Field(default=None, ge=0, le=1)
    ambiguities: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Things the model was unsure about or that need clarification",
    )


#: JSON Schema handed to providers that support structured/tool output. Derived
#: from the model so it can never drift from the validated type.
def extraction_json_schema() -> dict[str, Any]:
    return ProfileExtraction.model_json_schema()
