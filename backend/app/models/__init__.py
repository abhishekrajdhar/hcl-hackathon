"""ORM models. Importing this package registers every mapper."""

from app.models.assessment import Assessment, AssessmentQuestion, AssessmentResult
from app.models.base import Base
from app.models.feedback import Feedback
from app.models.goal import LearningGoal, LearningGoalSkill
from app.models.path import LearningPath, LearningPathItem
from app.models.progress import UserProgress
from app.models.recommendation import Recommendation
from app.models.resource import Resource, ResourcePrerequisite, ResourceSkill
from app.models.skill import Prerequisite, Skill, SkillCategory, UserSkill
from app.models.user import LearnerProfile, User

__all__ = [
    "Assessment",
    "AssessmentQuestion",
    "AssessmentResult",
    "Base",
    "Feedback",
    "LearnerProfile",
    "LearningGoal",
    "LearningGoalSkill",
    "LearningPath",
    "LearningPathItem",
    "Prerequisite",
    "Recommendation",
    "Resource",
    "ResourcePrerequisite",
    "ResourceSkill",
    "Skill",
    "SkillCategory",
    "User",
    "UserProgress",
    "UserSkill",
]
