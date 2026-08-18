"""Enumerations shared by the ORM models and the Pydantic schemas."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String-valued enum (kept explicit for Python 3.10 compatibility)."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class UserRole(StrEnum):
    LEARNER = "learner"
    ADMIN = "admin"


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class EvidenceSource(StrEnum):
    SELF_REPORT = "self_report"
    ASSESSMENT = "assessment"
    COMPLETION = "completion"
    INFERRED = "inferred"


class GoalStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ACHIEVED = "achieved"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class ResourceType(StrEnum):
    COURSE = "course"
    PROJECT = "project"
    ARTICLE = "article"
    VIDEO = "video"
    BOOK = "book"
    TUTORIAL = "tutorial"
    LAB = "lab"
    ASSESSMENT = "assessment"


class Modality(StrEnum):
    VIDEO = "video"
    TEXT = "text"
    INTERACTIVE = "interactive"
    PROJECT = "project"
    AUDIO = "audio"
    MIXED = "mixed"


class PrerequisiteStrength(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class PathStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class PathItemStatus(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class PathItemType(StrEnum):
    RESOURCE = "resource"
    ASSESSMENT = "assessment"
    MILESTONE_REVIEW = "milestone_review"


class AssessmentType(StrEnum):
    DIAGNOSTIC = "diagnostic"
    CHECKPOINT = "checkpoint"
    FINAL = "final"
    PRACTICE = "practice"


class QuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class ProgressEventType(StrEnum):
    STARTED = "started"
    PROGRESSED = "progressed"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ABANDONED = "abandoned"


class FeedbackTargetType(StrEnum):
    RESOURCE = "resource"
    PATH = "path"
    PATH_ITEM = "path_item"
    RECOMMENDATION = "recommendation"
    ASSESSMENT = "assessment"


class FeedbackSignal(StrEnum):
    UP = "up"
    DOWN = "down"
    TOO_EASY = "too_easy"
    TOO_HARD = "too_hard"
    IRRELEVANT = "irrelevant"
    LOVED = "loved"


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"
