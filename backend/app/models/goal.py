"""Learning goals and their target skill vector."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import GoalStatus
from app.models.types import pg_enum

if TYPE_CHECKING:
    from app.models.path import LearningPath
    from app.models.skill import Skill
    from app.models.user import User


class LearningGoal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learning_goals"
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 5", name="priority_range"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    raw_input: Mapped[str | None] = mapped_column(Text)
    target_role: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[GoalStatus] = mapped_column(
        pg_enum(GoalStatus, "goal_status"), nullable=False, default=GoalStatus.ACTIVE, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    target_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped["User"] = relationship(back_populates="goals")
    target_skills: Mapped[list["LearningGoalSkill"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan"
    )
    paths: Mapped[list["LearningPath"]] = relationship(back_populates="goal")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LearningGoal {self.title}>"


class LearningGoalSkill(UUIDMixin, TimestampMixin, Base):
    """One component of a goal's target vector: skill X at level Y, weighted."""

    __tablename__ = "learning_goal_skills"
    __table_args__ = (
        UniqueConstraint("goal_id", "skill_id", name="uq_learning_goal_skills_goal_id_skill_id"),
        CheckConstraint("required_level >= 0 AND required_level <= 10", name="required_level_range"),
        CheckConstraint("importance >= 0 AND importance <= 1", name="importance_range"),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("learning_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    required_level: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    goal: Mapped["LearningGoal"] = relationship(back_populates="target_skills")
    skill: Mapped["Skill"] = relationship()
