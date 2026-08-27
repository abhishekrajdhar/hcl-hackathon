"""HTTP layer. Routers stay thin: validate, delegate, serialise."""

from fastapi import APIRouter

from app.core.config import settings
from app.routers import (
    readiness,
    discovery,
    adaptive,
    assessments,
    auth,
    chat,
    feedback,
    goals,
    health,
    learning_path,
    paths,
    profiles,
    progress,
    public,
    recommendations,
    resources,
    search,
    skill_gap,
    skills,
    user_skills,
    users,
)

# Health probes live outside the versioned prefix so orchestrators can hit
# a stable path.
health_router = health.router

api_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(profiles.router)
api_router.include_router(user_skills.router)
api_router.include_router(skills.categories_router)
api_router.include_router(skills.router)
api_router.include_router(skills.prerequisites_router)
api_router.include_router(goals.router)
api_router.include_router(resources.router)
api_router.include_router(paths.router)
api_router.include_router(assessments.router)
api_router.include_router(assessments.results_router)
api_router.include_router(assessments.review_router)
api_router.include_router(progress.router)
api_router.include_router(feedback.router)
api_router.include_router(recommendations.router)
api_router.include_router(recommendations.admin_router)
api_router.include_router(search.router)
api_router.include_router(skill_gap.router)
api_router.include_router(learning_path.router)
api_router.include_router(adaptive.router)
api_router.include_router(chat.router)
api_router.include_router(discovery.router)
api_router.include_router(readiness.router)
api_router.include_router(public.router)

__all__ = ["api_router", "health_router"]
