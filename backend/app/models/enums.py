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
    VIDEO = "video"
    ARTICLE = "article"
    BOOK = "book"
    PROJECT = "project"
    ASSESSMENT = "assessment"
    DOCUMENTATION = "documentation"
    TUTORIAL = "tutorial"
    LAB = "lab"


class Modality(StrEnum):
    VIDEO = "video"
    TEXT = "text"
    INTERACTIVE = "interactive"
    PROJECT = "project"
    AUDIO = "audio"
    MIXED = "mixed"


class RelationshipType(StrEnum):
    """How a prerequisite edge constrains ordering.

    Only HARD_PREREQUISITE can make a learning order *invalid*. HARD, SOFT and
    RECOMMENDED all constrain sequencing and all participate in cycle
    detection; RELATED is an association only and is excluded from the DAG.
    """

    HARD_PREREQUISITE = "hard_prerequisite"
    SOFT_PREREQUISITE = "soft_prerequisite"
    RECOMMENDED = "recommended"
    RELATED = "related"


#: Edge types that impose an ordering constraint on a learning sequence.
ORDERING_RELATIONSHIPS: frozenset[RelationshipType] = frozenset(
    {
        RelationshipType.HARD_PREREQUISITE,
        RelationshipType.SOFT_PREREQUISITE,
        RelationshipType.RECOMMENDED,
    }
)

#: Edge types whose violation makes a learning order invalid rather than merely
#: suboptimal.
BLOCKING_RELATIONSHIPS: frozenset[RelationshipType] = frozenset(
    {RelationshipType.HARD_PREREQUISITE}
)


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
    CODING = "coding"
    CONCEPTUAL = "conceptual"


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


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
