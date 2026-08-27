"""Unauthenticated, read-only demo data.

The landing page renders the real Learning Universe before any sign-in, and the
visitor looking at it has no token. This one endpoint serves exactly what that
galaxy needs: the skill graph, and the seeded demo learner's proficiencies and
targets. It is read-only and speaks only about the catalogue taxonomy (public
by nature) and the demo account (public by design) — never about a real
learner. When no demo learner is seeded, it says so instead of pretending.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fastapi import APIRouter

from app.core.config import settings
from app.core.deps import SessionDep
from app.models.enums import PathStatus
from app.models.path import LearningPath
from app.models.skill import Prerequisite, Skill, UserSkill
from app.models.user import User
from app.schemas.skill import PrerequisiteRead, SkillGraphNode, SkillGraphResponse, SkillRead

router = APIRouter(prefix="/public", tags=["public"])


class DemoProficiency(BaseModel):
    slug: str
    current: float
    target: float | None


class DemoUniverse(BaseModel):
    """Everything the signed-out galaxy needs, in the same shapes the
    authenticated endpoints use, so the client derives one way for both."""

    available: bool
    goal: str | None = None
    catalogue: list[SkillRead] = []
    graph: SkillGraphResponse | None = None
    proficiencies: list[DemoProficiency] = []
    target_slugs: list[str] = []


@router.get("/demo/universe", response_model=DemoUniverse, summary="The demo learner's universe")
async def demo_universe(session: SessionDep) -> DemoUniverse:
    if not settings.DEMO_LEARNER_EMAIL:
        return DemoUniverse(available=False)
    user = (
        await session.execute(
            select(User).where(User.email == settings.DEMO_LEARNER_EMAIL.lower())
        )
    ).scalar_one_or_none()
    if user is None:
        return DemoUniverse(available=False)

    skills = (
        (
            await session.execute(
                select(Skill)
                .where(Skill.is_active.is_(True))
                .options(selectinload(Skill.category))
                .order_by(Skill.slug)
            )
        )
        .scalars()
        .all()
    )
    edges = (await session.execute(select(Prerequisite))).scalars().all()
    entries = (
        (
            await session.execute(
                select(UserSkill)
                .where(UserSkill.user_id == user.id)
                .options(selectinload(UserSkill.skill))
            )
        )
        .scalars()
        .all()
    )

    path = (
        await session.execute(
            select(LearningPath).where(
                LearningPath.user_id == user.id, LearningPath.status == PathStatus.ACTIVE
            )
        )
    ).scalar_one_or_none()
    by_id = {str(s.id): s for s in skills}
    target_slugs: list[str] = []
    goal: str | None = None
    if path is not None:
        goal = path.title
        for target in (path.constraints_snapshot or {}).get("target_skills", []):
            skill = by_id.get(str(target.get("skill_id")))
            if skill is not None:
                target_slugs.append(skill.slug)

    return DemoUniverse(
        available=True,
        goal=goal,
        catalogue=[SkillRead.model_validate(s) for s in skills],
        graph=SkillGraphResponse(
            root_skill_id=skills[0].id if skills else user.id,
            nodes=[
                SkillGraphNode(skill_id=s.id, slug=s.slug, name=s.name, depth=0)
                for s in skills
            ],
            edges=[PrerequisiteRead.model_validate(e) for e in edges],
        ),
        proficiencies=[
            DemoProficiency(
                slug=e.skill.slug,
                current=e.proficiency,
                target=(e.target_level / e.skill.level_scale) if e.target_level else None,
            )
            for e in entries
            if e.skill is not None
        ],
        target_slugs=target_slugs,
    )
