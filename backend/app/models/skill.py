"""Skill taxonomy, the prerequisite DAG, and per-learner mastery."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import EvidenceSource, RelationshipType
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.user import User


class SkillCategory(UUIDMixin, TimestampMixin, Base):
    """A top-level grouping of the taxonomy (Programming, Statistics, MLOps...).

    Kept as a table rather than an enum so the taxonomy can grow without a
    migration, and so categories can carry ordering and presentation metadata.
    """

    __tablename__ = "skill_categories"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    skills: Mapped[list["Skill"]] = relationship(back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SkillCategory {self.slug}>"


class Skill(UUIDMixin, TimestampMixin, Base):
    """A canonical skill. Free-text skill names are always resolved to one of these."""

    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="difficulty_range"),
        Index("ix_skills_category_id_difficulty", "category_id", "difficulty"),
    )

    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("skill_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    #: Intrinsic difficulty of the skill itself, 1 (introductory) to 5 (expert).
    #: Independent of the learner and of how deep it sits in the graph.
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    domain: Mapped[str | None] = mapped_column(String(128))
    level_scale: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Free-form metadata (typical time-to-learn, external ids, tags...).
    #: Named `extra` because `metadata` is reserved by SQLAlchemy's declarative
    #: API; the same convention is used by `resources` and `learner_profiles`.
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    category: Mapped["SkillCategory"] = relationship(back_populates="skills")
    user_skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    prerequisites: Mapped[list["Prerequisite"]] = relationship(
        back_populates="source_skill",
        foreign_keys="Prerequisite.source_skill_id",
        cascade="all, delete-orphan",
    )
    dependents: Mapped[list["Prerequisite"]] = relationship(
        back_populates="prerequisite_skill",
        foreign_keys="Prerequisite.prerequisite_skill_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Skill {self.slug}>"


class UserSkill(UUIDMixin, TimestampMixin, Base):
    """The learner's current mastery of a single skill (0..level_scale)."""

    __tablename__ = "user_skills"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skills_user_id_skill_id"),
        CheckConstraint("current_level >= 0 AND current_level <= 10", name="current_level_range"),
        CheckConstraint(
            "target_level IS NULL OR (target_level >= 0 AND target_level <= 10)",
            name="target_level_range",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_level: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    evidence_source: Mapped[EvidenceSource] = mapped_column(
        pg_enum(EvidenceSource, "evidence_source"),
        nullable=False,
        default=EvidenceSource.SELF_REPORT,
    )
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="skills")
    skill: Mapped["Skill"] = relationship(back_populates="user_skills")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<UserSkill user={self.user_id} skill={self.skill_id} level={self.current_level}>"


class Prerequisite(UUIDMixin, TimestampMixin, Base):
    """A directed edge of the skill DAG.

    Read as: `source_skill` requires `prerequisite_skill`. Acyclicity across all
    ordering edge types is enforced on write by the graph service — a cycle here
    would make sequence generation non-terminating.
    """

    __tablename__ = "prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "source_skill_id",
            "prerequisite_skill_id",
            name="uq_prerequisites_source_skill_id_prerequisite_skill_id",
        ),
        CheckConstraint("source_skill_id <> prerequisite_skill_id", name="no_self_prerequisite"),
        CheckConstraint("min_level >= 0 AND min_level <= 10", name="min_level_range"),
        CheckConstraint("strength >= 0 AND strength <= 1", name="strength_range"),
    )

    source_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prerequisite_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        pg_enum(RelationshipType, "relationship_type"),
        nullable=False,
        default=RelationshipType.HARD_PREREQUISITE,
        index=True,
    )
    #: How strongly the prerequisite matters, 0..1. Used as a ranking weight;
    #: it never changes whether an ordering is *valid* — relationship_type does.
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    #: Mastery level the prerequisite must reach before the source is unlocked.
    min_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    rationale: Mapped[str | None] = mapped_column(Text)

    source_skill: Mapped["Skill"] = relationship(
        back_populates="prerequisites", foreign_keys=[source_skill_id]
    )
    prerequisite_skill: Mapped["Skill"] = relationship(
        back_populates="dependents", foreign_keys=[prerequisite_skill_id]
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Prerequisite {self.source_skill_id} <- {self.prerequisite_skill_id}>"
