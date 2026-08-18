"""User identity and the structured learner profile."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ExperienceLevel, UserRole
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.assessment import AssessmentResult
    from app.models.feedback import Feedback
    from app.models.goal import LearningGoal
    from app.models.path import LearningPath
    from app.models.progress import UserProgress
    from app.models.recommendation import Recommendation
    from app.models.skill import UserSkill


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.LEARNER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["LearnerProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    goals: Mapped[list["LearningGoal"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    paths: Mapped[list["LearningPath"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    progress_events: Mapped[list["UserProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    assessment_results: Mapped[list["AssessmentResult"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email}>"


class LearnerProfile(UUIDMixin, TimestampMixin, Base):
    """Structured profile derived from the learner's free-text goal.

    Populated deterministically today; the LLM extraction stage will write the
    same columns in a later phase.
    """

    __tablename__ = "learner_profiles"
    __table_args__ = (
        CheckConstraint("weekly_hours >= 0 AND weekly_hours <= 168", name="weekly_hours_range"),
        CheckConstraint(
            "extraction_confidence IS NULL OR (extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="extraction_confidence_range",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    headline: Mapped[str | None] = mapped_column(String(255))
    # (1) personal learning goal, in the learner's own words.
    goal_text_raw: Mapped[str | None] = mapped_column(Text)
    # (2) target career / role the learner is aiming for.
    target_role: Mapped[str | None] = mapped_column(String(255))
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        pg_enum(ExperienceLevel, "experience_level"),
        nullable=False,
        default=ExperienceLevel.BEGINNER,
    )
    weekly_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    target_deadline: Mapped[date | None] = mapped_column(Date)
    preferred_modalities: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list
    )
    preferred_languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)), nullable=False, default=lambda: ["en"]
    )
    learning_style: Mapped[str | None] = mapped_column(String(64))
    budget_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # (8) interests / topics the learner cares about.
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False, default=list)
    # (6, 7) self-reported completed courses and projects. Each item is a small
    # dict (title, provider, url, completed_at, ...); kept as JSONB so the shape
    # can evolve without a migration.
    completed_courses: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    completed_projects: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # (12) structured learning preferences (pace, difficulty tolerance, ...).
    learning_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Provenance of the extraction step, so low-confidence profiles can be
    # re-confirmed with the learner later.
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    extraction_model: Mapped[str | None] = mapped_column(String(128))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    user: Mapped["User"] = relationship(back_populates="profile")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LearnerProfile user={self.user_id}>"
