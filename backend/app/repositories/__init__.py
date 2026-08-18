"""Data-access layer."""

from app.repositories.assessment import (
    AssessmentQuestionRepository,
    AssessmentRepository,
    AssessmentResultRepository,
)
from app.repositories.base import BaseRepository
from app.repositories.feedback import FeedbackRepository
from app.repositories.goal import LearningGoalRepository, LearningGoalSkillRepository
from app.repositories.path import LearningPathItemRepository, LearningPathRepository
from app.repositories.progress import UserProgressRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.resource import (
    ResourcePrerequisiteRepository,
    ResourceRepository,
    ResourceSkillRepository,
)
from app.repositories.skill import (
    PrerequisiteRepository,
    SkillCategoryRepository,
    SkillRepository,
    UserSkillRepository,
)
from app.repositories.user import LearnerProfileRepository, UserRepository

__all__ = [
    "AssessmentQuestionRepository",
    "AssessmentRepository",
    "AssessmentResultRepository",
    "BaseRepository",
    "FeedbackRepository",
    "LearnerProfileRepository",
    "LearningGoalRepository",
    "LearningGoalSkillRepository",
    "LearningPathItemRepository",
    "LearningPathRepository",
    "PrerequisiteRepository",
    "RecommendationRepository",
    "ResourcePrerequisiteRepository",
    "ResourceRepository",
    "ResourceSkillRepository",
    "SkillCategoryRepository",
    "SkillRepository",
    "UserProgressRepository",
    "UserRepository",
    "UserSkillRepository",
]
