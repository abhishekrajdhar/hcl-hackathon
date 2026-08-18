from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidenceSource, RelationshipType
from app.schemas.common import TimestampedModel


# --- SkillCategory ---------------------------------------------------------
class SkillCategoryBase(BaseModel):
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class SkillCategoryCreate(SkillCategoryBase):
    pass


class SkillCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class SkillCategoryRead(SkillCategoryBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)


# --- Skill -----------------------------------------------------------------
class SkillBase(BaseModel):
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category_id: uuid.UUID
    difficulty: int = Field(default=1, ge=1, le=5)
    domain: str | None = Field(default=None, max_length=128)
    level_scale: int = Field(default=5, ge=1, le=10)
    aliases: list[str] = Field(default_factory=list)
    is_active: bool = True
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form metadata. Named `extra` because `metadata` is reserved by the ORM.",
    )


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category_id: uuid.UUID | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    domain: str | None = Field(default=None, max_length=128)
    level_scale: int | None = Field(default=None, ge=1, le=10)
    aliases: list[str] | None = None
    is_active: bool | None = None
    extra: dict[str, Any] | None = None


class SkillRead(SkillBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    category: SkillCategoryRead | None = None


class SkillSummary(BaseModel):
    """Compact node representation used throughout the graph responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    difficulty: int
    category_id: uuid.UUID | None = None


# --- Prerequisite ----------------------------------------------------------
class PrerequisiteBase(BaseModel):
    source_skill_id: uuid.UUID
    prerequisite_skill_id: uuid.UUID
    relationship_type: RelationshipType = RelationshipType.HARD_PREREQUISITE
    strength: float = Field(default=1.0, ge=0, le=1)
    min_level: float = Field(default=1.0, ge=0, le=10)
    rationale: str | None = None


class PrerequisiteCreate(PrerequisiteBase):
    pass


class PrerequisiteUpdate(BaseModel):
    relationship_type: RelationshipType | None = None
    strength: float | None = Field(default=None, ge=0, le=1)
    min_level: float | None = Field(default=None, ge=0, le=10)
    rationale: str | None = None


class PrerequisiteRead(PrerequisiteBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)


class PrerequisiteEdgeRead(PrerequisiteRead):
    """A prerequisite edge with the skill on the far end resolved."""

    prerequisite_skill: SkillSummary | None = None


class DependentEdgeRead(PrerequisiteRead):
    """A dependent edge with the requiring skill resolved."""

    source_skill: SkillSummary | None = None


# --- Graph responses -------------------------------------------------------
class PrerequisiteTreeNode(BaseModel):
    """Recursive prerequisite tree. Shared sub-trees are expanded once and then
    marked `already_visited` so the response stays finite."""

    skill: SkillSummary
    depth: int
    relationship_type: RelationshipType | None = None
    strength: float | None = None
    min_level: float | None = None
    already_visited: bool = False
    prerequisites: list["PrerequisiteTreeNode"] = Field(default_factory=list)


class PrerequisiteTreeResponse(BaseModel):
    root: PrerequisiteTreeNode
    total_prerequisites: int
    max_depth: int
    truncated: bool = False


class SkillGraphNode(BaseModel):
    skill_id: uuid.UUID
    slug: str
    name: str
    depth: int


class SkillGraphResponse(BaseModel):
    """Transitive prerequisite closure for one skill."""

    root_skill_id: uuid.UUID
    nodes: list[SkillGraphNode]
    edges: list[PrerequisiteRead]


class SkillDependencyAnalysis(BaseModel):
    """Everything a learner must clear before attempting `skill`."""

    skill: SkillSummary
    direct_prerequisites: list[SkillSummary]
    all_prerequisites: list[SkillSummary]
    total_prerequisites: int
    max_depth: int
    #: Minimum number of sequential steps, however much is studied in parallel.
    critical_path: list[SkillSummary]
    critical_path_length: int
    #: Prerequisites grouped into levels that can be tackled concurrently.
    levels: list[list[SkillSummary]]
    #: Deterministic order in which to learn the whole dependency set.
    learning_sequence: list[SkillSummary]
    unlocks: list[SkillSummary]


class LearningSequenceRequest(BaseModel):
    target_skill_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    #: Skills the learner already has; excluded from the sequence along with
    #: any prerequisite they alone were pulling in.
    known_skill_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    include_soft_prerequisites: bool = True


class LearningSequenceStep(BaseModel):
    position: int
    level: int
    skill: SkillSummary
    is_target: bool
    prerequisite_ids: list[uuid.UUID] = Field(default_factory=list)


class LearningSequenceResponse(BaseModel):
    sequence: list[LearningSequenceStep]
    levels: list[list[SkillSummary]]
    total_skills: int
    target_skill_ids: list[uuid.UUID]
    skipped_known_skill_ids: list[uuid.UUID] = Field(default_factory=list)


class OrderViolationRead(BaseModel):
    skill_id: uuid.UUID
    prerequisite_id: uuid.UUID
    relationship_type: RelationshipType
    reason: Literal["missing_prerequisite", "out_of_order"]
    severity: Literal["error", "warning"]
    skill_position: int
    prerequisite_position: int | None = None
    message: str


class ValidateOrderRequest(BaseModel):
    skill_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class ValidateOrderResponse(BaseModel):
    is_valid: bool
    violations: list[OrderViolationRead]
    missing_prerequisites: list[SkillSummary]
    unknown_skill_ids: list[uuid.UUID]
    suggested_order: list[SkillSummary]


class CycleReport(BaseModel):
    """Integrity check over the whole stored graph."""

    is_acyclic: bool
    cycle_count: int
    cycles: list[list[SkillSummary]]


# --- UserSkill -------------------------------------------------------------
class UserSkillBase(BaseModel):
    skill_id: uuid.UUID
    current_level: float = Field(default=0.0, ge=0, le=10)
    target_level: float | None = Field(default=None, ge=0, le=10)
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence_source: EvidenceSource = EvidenceSource.SELF_REPORT
    last_practiced_at: datetime | None = None
    notes: str | None = None


class UserSkillCreate(UserSkillBase):
    pass


class UserSkillUpdate(BaseModel):
    current_level: float | None = Field(default=None, ge=0, le=10)
    target_level: float | None = Field(default=None, ge=0, le=10)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_source: EvidenceSource | None = None
    last_practiced_at: datetime | None = None
    notes: str | None = None


class UserSkillRead(UserSkillBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    skill: SkillRead | None = None
