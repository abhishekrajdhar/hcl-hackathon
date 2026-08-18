from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EvidenceSource, PrerequisiteStrength
from app.schemas.common import TimestampedModel


# --- Skill -----------------------------------------------------------------
class SkillBase(BaseModel):
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)
    domain: str | None = Field(default=None, max_length=128)
    level_scale: int = Field(default=5, ge=1, le=10)
    aliases: list[str] = Field(default_factory=list)
    is_active: bool = True


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=128)
    domain: str | None = Field(default=None, max_length=128)
    level_scale: int | None = Field(default=None, ge=1, le=10)
    aliases: list[str] | None = None
    is_active: bool | None = None


class SkillRead(SkillBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)


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


# --- Prerequisite ----------------------------------------------------------
class PrerequisiteBase(BaseModel):
    skill_id: uuid.UUID
    prerequisite_skill_id: uuid.UUID
    strength: PrerequisiteStrength = PrerequisiteStrength.HARD
    min_level: float = Field(default=1.0, ge=0, le=10)
    rationale: str | None = None


class PrerequisiteCreate(PrerequisiteBase):
    pass


class PrerequisiteUpdate(BaseModel):
    strength: PrerequisiteStrength | None = None
    min_level: float | None = Field(default=None, ge=0, le=10)
    rationale: str | None = None


class PrerequisiteRead(PrerequisiteBase, TimestampedModel):
    model_config = ConfigDict(from_attributes=True)


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
