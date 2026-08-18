from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidenceSource, ExperienceLevel
from app.schemas.common import TimestampedModel


# --- structured sub-objects -------------------------------------------------
class CompletedCourse(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    provider: str | None = Field(default=None, max_length=128)
    url: str | None = Field(default=None, max_length=2048)
    resource_id: uuid.UUID | None = None
    completed_at: date | None = None
    skills: list[str] = Field(default_factory=list, description="Skill slugs or names covered")


class CompletedProject(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    url: str | None = Field(default=None, max_length=2048)
    completed_at: date | None = None
    skills: list[str] = Field(default_factory=list)


# --- profile ----------------------------------------------------------------
class LearnerProfileBase(BaseModel):
    headline: str | None = Field(default=None, max_length=255)
    goal_text_raw: str | None = Field(default=None, description="Personal learning goal, free text")
    target_role: str | None = Field(default=None, max_length=255, description="Target career/role")
    experience_level: ExperienceLevel = ExperienceLevel.BEGINNER
    weekly_hours: int = Field(default=5, ge=0, le=168, description="Weekly available hours")
    target_deadline: date | None = Field(default=None, description="Target completion timeline")
    preferred_modalities: list[str] = Field(
        default_factory=list, description="Preferred learning formats (video, project, ...)"
    )
    preferred_languages: list[str] = Field(default_factory=lambda: ["en"])
    learning_style: str | None = Field(default=None, max_length=64)
    interests: list[str] = Field(default_factory=list, max_length=64)
    completed_courses: list[CompletedCourse] = Field(default_factory=list)
    completed_projects: list[CompletedProject] = Field(default_factory=list)
    learning_preferences: dict[str, Any] = Field(
        default_factory=dict, description="Structured preferences (pace, difficulty tolerance, ...)"
    )
    budget_ceiling: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    extra: dict[str, Any] = Field(default_factory=dict)


class LearnerProfileCreate(LearnerProfileBase):
    pass


class LearnerProfileUpdate(BaseModel):
    """Every field optional: PATCH-style partial update."""

    headline: str | None = Field(default=None, max_length=255)
    goal_text_raw: str | None = None
    target_role: str | None = Field(default=None, max_length=255)
    experience_level: ExperienceLevel | None = None
    weekly_hours: int | None = Field(default=None, ge=0, le=168)
    target_deadline: date | None = None
    preferred_modalities: list[str] | None = None
    preferred_languages: list[str] | None = None
    learning_style: str | None = Field(default=None, max_length=64)
    interests: list[str] | None = Field(default=None, max_length=64)
    completed_courses: list[CompletedCourse] | None = None
    completed_projects: list[CompletedProject] | None = None
    learning_preferences: dict[str, Any] | None = None
    budget_ceiling: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    extra: dict[str, Any] | None = None


class LearnerProfileRead(LearnerProfileBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    extraction_confidence: float | None = None
    extraction_model: str | None = None
    version: int


# --- skill proficiency (0..1) ----------------------------------------------
class SkillRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str


class SkillProficiencyRead(BaseModel):
    """A learner's proficiency in one skill, on the canonical [0, 1] scale."""

    model_config = ConfigDict(from_attributes=True)

    skill_id: uuid.UUID
    proficiency: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence_source: EvidenceSource
    target_proficiency: float | None = Field(default=None, ge=0, le=1)
    last_practiced_at: datetime | None = None
    notes: str | None = None
    updated_at: datetime
    skill: SkillRef | None = None


class SkillProficiencyCreate(BaseModel):
    skill_id: uuid.UUID
    proficiency: float = Field(ge=0, le=1, description="Proficiency in [0, 1], e.g. 0.85")
    confidence: float = Field(default=0.6, ge=0, le=1)
    target_proficiency: float | None = Field(default=None, ge=0, le=1)
    evidence_source: EvidenceSource = EvidenceSource.SELF_REPORT
    notes: str | None = None


class SkillProficiencyUpdate(BaseModel):
    proficiency: float | None = Field(default=None, ge=0, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    target_proficiency: float | None = Field(default=None, ge=0, le=1)
    evidence_source: EvidenceSource | None = None
    notes: str | None = None


# --- aggregate profile ------------------------------------------------------
class AssessmentHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    score: float
    max_score: float
    percentage: float
    passed: bool
    submitted_at: datetime | None = None


class AssessmentHistorySummary(BaseModel):
    total_attempts: int = 0
    passed_attempts: int = 0
    average_percentage: float = 0.0
    last_attempt_at: datetime | None = None
    recent: list[AssessmentHistoryItem] = Field(default_factory=list)


class FullLearnerProfile(BaseModel):
    """Everything the profile captures, assembled for the dashboard/API."""

    profile: LearnerProfileRead
    skills: list[SkillProficiencyRead]
    skill_count: int
    assessment_history: AssessmentHistorySummary


# --- validation -------------------------------------------------------------
class ValidationIssueRead(BaseModel):
    field: str
    code: str
    message: str
    severity: Literal["error", "warning"]


class ProfileValidationRead(BaseModel):
    is_valid: bool
    errors: list[ValidationIssueRead] = Field(default_factory=list)
    warnings: list[ValidationIssueRead] = Field(default_factory=list)


# --- proficiency-update reporting (e.g. after an assessment) ----------------
class ProficiencyChange(BaseModel):
    skill_id: uuid.UUID
    previous_proficiency: float
    new_proficiency: float
    delta: float
    observed: float
    evidence_source: EvidenceSource
    created: bool = False


class ProficiencyUpdateReport(BaseModel):
    user_id: uuid.UUID
    source: str
    changes: list[ProficiencyChange] = Field(default_factory=list)


# --- LLM ingestion abstraction ---------------------------------------------
class SkillProficiencyDraft(BaseModel):
    """A skill proficiency the extractor believes it found. `skill_id` xor
    `skill_ref` (a name/slug to be resolved deterministically)."""

    skill_id: uuid.UUID | None = None
    skill_ref: str | None = Field(default=None, description="Skill name or slug to resolve")
    proficiency: float = Field(ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)


class ProfileDraft(BaseModel):
    """A structured, validated profile update proposed by an extractor.

    This is the entire contract between any populate-from-conversation source
    (a future LLM, a form importer, a resume parser) and the profile engine. The
    source is never allowed to write the database directly: it returns a
    ProfileDraft, which is validated here and applied by deterministic code in
    ProfileService. Fields left None are not touched.
    """

    model_config = ConfigDict(extra="forbid")

    goal_text_raw: str | None = None
    target_role: str | None = Field(default=None, max_length=255)
    experience_level: ExperienceLevel | None = None
    weekly_hours: int | None = Field(default=None, ge=0, le=168)
    target_deadline: date | None = None
    preferred_modalities: list[str] | None = None
    interests: list[str] | None = Field(default=None, max_length=64)
    learning_style: str | None = Field(default=None, max_length=64)
    learning_preferences: dict[str, Any] | None = None
    completed_courses: list[CompletedCourse] | None = None
    completed_projects: list[CompletedProject] | None = None
    skills: list[SkillProficiencyDraft] = Field(default_factory=list)
    #: Extractor provenance, recorded on the profile for auditing.
    source_model: str | None = Field(default=None, max_length=128)
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)


class ProfileDraftIngestRequest(BaseModel):
    """Free-text input plus optional prior context for an extractor."""

    text: str = Field(min_length=1, max_length=8000)
    apply: bool = Field(
        default=False,
        description="If false, return the extracted draft for review without persisting it.",
    )


class ProfileDraftPreview(BaseModel):
    draft: ProfileDraft
    unresolved_skill_refs: list[str] = Field(default_factory=list)
    applied: bool = False
