"""Skill taxonomy, the prerequisite DAG, and per-learner mastery."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import EvidenceSource, PrerequisiteStrength
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.user import User


class Skill(UUIDMixin, TimestampMixin, Base):
    """A canonical skill. Free-text skill names are always resolved to one of these."""

    __tablename__ = "skills"
    __table_args__ = (
        Index("ix_skills_category_domain", "category", "domain"),
    )

    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(128))
    domain: Mapped[str | None] = mapped_column(String(128))
    level_scale: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.EMBEDDING_DIM))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user_skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    prerequisites: Mapped[list["Prerequisite"]] = relationship(
        back_populates="skill",
        foreign_keys="Prerequisite.skill_id",
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
    """A directed edge of the skill DAG: `skill` requires `prerequisite_skill`."""

    __tablename__ = "prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "skill_id", "prerequisite_skill_id", name="uq_prerequisites_skill_id_prerequisite_skill_id"
        ),
        CheckConstraint("skill_id <> prerequisite_skill_id", name="no_self_prerequisite"),
        CheckConstraint("min_level >= 0 AND min_level <= 10", name="min_level_range"),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prerequisite_skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strength: Mapped[PrerequisiteStrength] = mapped_column(
        pg_enum(PrerequisiteStrength, "prerequisite_strength"),
        nullable=False,
        default=PrerequisiteStrength.HARD,
    )
    min_level: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    rationale: Mapped[str | None] = mapped_column(Text)

    skill: Mapped["Skill"] = relationship(back_populates="prerequisites", foreign_keys=[skill_id])
    prerequisite_skill: Mapped["Skill"] = relationship(
        back_populates="dependents", foreign_keys=[prerequisite_skill_id]
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Prerequisite {self.skill_id} <- {self.prerequisite_skill_id}>"
