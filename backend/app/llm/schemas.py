"""Structured-output contracts for LLM extraction.

`ProfileExtraction` is the ONLY shape an extraction LLM is allowed to return.
It is enforced with Pydantic: the raw model output is parsed and validated into
this type before any other code touches it, and it is deliberately decoupled
from the ORM — nothing here can write to the database.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


# --- assessment question generation ----------------------------------------
class GeneratedOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = Field(min_length=1, max_length=4)
    text: str = Field(min_length=1, max_length=500)


class GeneratedQuestion(BaseModel):
    """One multiple-choice question the LLM proposes. Validated before use — a
    malformed or unkeyed question is rejected, never scored."""

    model_config = ConfigDict(extra="ignore")

    stem: str = Field(min_length=1, max_length=1000)
    options: list[GeneratedOption] = Field(min_length=2, max_length=6)
    correct_key: str = Field(min_length=1, max_length=4)
    explanation: str = Field(default="", max_length=1000)
    difficulty: int = Field(default=1, ge=1, le=5)

    @model_validator(mode="after")
    def _correct_key_in_options(self) -> "GeneratedQuestion":
        keys = [o.key for o in self.options]
        if self.correct_key not in keys:
            raise ValueError("correct_key must match one of the option keys")
        if len(keys) != len(set(keys)):
            raise ValueError("option keys must be unique")
        return self


class GeneratedAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=30)


def generated_assessment_schema() -> dict[str, Any]:
    return GeneratedAssessment.model_json_schema()


# --- career discovery --------------------------------------------------------
class CareerDirection(BaseModel):
    """One career direction the model proposes for an uncertain learner.

    `target_skills` are catalogue skill NAMES; they are resolved against the
    real graph after validation, and any that do not resolve are dropped. A
    direction whose skills all fail to resolve is discarded entirely — the
    model may reason about careers, but it cannot invent the skills they
    require.
    """

    title: str = Field(min_length=3, max_length=80)
    pitch: str = Field(min_length=10, max_length=240)
    #: Why THIS learner — must reference their stated signals, not generics.
    why: str = Field(min_length=5, max_length=240)
    target_skills: list[str] = Field(min_length=1, max_length=5)


class CareerAdvice(BaseModel):
    """Validated container for the model's career suggestions."""

    careers: list[CareerDirection] = Field(min_length=1, max_length=5)


def career_advice_json_schema() -> dict:
    return CareerAdvice.model_json_schema()


# --- goal intelligence -------------------------------------------------------
class GoalReading(BaseModel):
    """The model's reading of what a learner's message wants.

    Used to route between goal-setting and career discovery; the deterministic
    regex classifier remains the fallback, so a bad reading degrades to the
    old behaviour rather than to nothing.
    """

    is_goal: bool
    #: True when the learner is expressing uncertainty about direction.
    uncertain: bool = False
    goal_text: str | None = Field(default=None, max_length=120)
    goal_type: Literal["career", "internship", "transition", "skill"] | None = None


def goal_reading_json_schema() -> dict:
    return GoalReading.model_json_schema()


# --- role graph generation ---------------------------------------------------
class RoleSkillSpec(BaseModel):
    """One skill in a generated role graph.

    Names are resolved against the catalogue afterwards; a name that does not
    resolve becomes a NEW catalogue skill, so the model is told to reuse
    existing names wherever they fit and invent only what is genuinely
    missing. `prerequisites` may only reference catalogue skills or other
    skills in this same spec.
    """

    name: str = Field(min_length=2, max_length=80)
    required_level: float = Field(ge=0.3, le=1.0)
    prerequisites: list[str] = Field(default_factory=list, max_length=4)
    #: One of the catalogue's category names; used when the skill is new.
    category: str | None = Field(default=None, max_length=80)
    difficulty: int = Field(default=3, ge=1, le=5)


class RoleGraphSpec(BaseModel):
    """A generated target-skill graph for a role the catalogue does not name."""

    role_title: str = Field(min_length=3, max_length=80)
    skills: list[RoleSkillSpec] = Field(min_length=3, max_length=12)


def role_graph_json_schema() -> dict:
    return RoleGraphSpec.model_json_schema()
