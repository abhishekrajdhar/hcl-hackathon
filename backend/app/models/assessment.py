"""Assessments, their question bank, and learner attempts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AssessmentType, QuestionType
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.skill import Skill
    from app.models.user import User


class Assessment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("difficulty >= 1 AND difficulty <= 5", name="difficulty_range"),
        CheckConstraint(
            "passing_score >= 0 AND passing_score <= 1", name="passing_score_range"
        ),
    )

    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[AssessmentType] = mapped_column(
        pg_enum(AssessmentType, "assessment_type"), nullable=False, default=AssessmentType.CHECKPOINT
    )
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    passing_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Provenance for generated item banks; generated content stays inactive
    # until it has been reviewed.
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_model: Mapped[str | None] = mapped_column(String(128))

    skill: Mapped["Skill | None"] = relationship()
    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentQuestion.order_index",
    )
    results: Mapped[list["AssessmentResult"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Assessment {self.title}>"


class AssessmentQuestion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "assessment_questions"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id", "order_index", name="uq_assessment_questions_assessment_id_order_index"
        ),
        CheckConstraint("points > 0", name="points_positive"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL")
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        pg_enum(QuestionType, "question_type"), nullable=False, default=QuestionType.SINGLE_CHOICE
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    correct_answer: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # IRT parameters; seeded from priors and recalibrated from response data.
    difficulty_b: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discrimination_a: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    assessment: Mapped["Assessment"] = relationship(back_populates="questions")
    skill: Mapped["Skill | None"] = relationship()


class AssessmentResult(UUIDMixin, TimestampMixin, Base):
    """A single attempt. `responses` holds the per-question detail."""

    __tablename__ = "assessment_results"
    __table_args__ = (
        CheckConstraint("score >= 0", name="score_non_negative"),
        Index("ix_assessment_results_user_id_assessment_id", "user_id", "assessment_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_path_items.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    theta_estimate: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    responses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    user: Mapped["User"] = relationship(back_populates="assessment_results")
    assessment: Mapped["Assessment"] = relationship(back_populates="results")
