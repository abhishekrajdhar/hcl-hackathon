"""Bootstrap data.

Idempotent: safe to run on every deploy. Currently seeds only the first admin
account, from FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD.

    python -m app.db.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.seeds.skill_graph import CATEGORIES, EDGES, SKILLS
from app.db.session import SessionLocal, dispose_engine
from app.models.enums import RelationshipType, UserRole
from app.repositories.skill import (
    PrerequisiteRepository,
    SkillCategoryRepository,
    SkillRepository,
)
from app.repositories.user import UserRepository
from app.services.skill_graph_service import SkillGraphService

logger = get_logger(__name__)


async def seed_admin() -> None:
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        logger.info("no bootstrap admin configured; skipping")
        return

    async with SessionLocal() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(settings.FIRST_ADMIN_EMAIL)
        if existing is not None:
            if existing.role != UserRole.ADMIN:
                existing.role = UserRole.ADMIN
                await session.commit()
                logger.info("promoted existing user to admin", extra={"email": existing.email})
            else:
                logger.info("bootstrap admin already present", extra={"email": existing.email})
            return

        await users.create(
            {
                "email": settings.FIRST_ADMIN_EMAIL.lower(),
                "hashed_password": hash_password(settings.FIRST_ADMIN_PASSWORD),
                "full_name": "Administrator",
                "role": UserRole.ADMIN,
            }
        )
        await session.commit()
        logger.info("bootstrap admin created", extra={"email": settings.FIRST_ADMIN_EMAIL})


async def seed_skill_graph() -> None:
    """Upsert categories, skills and prerequisite edges.

    Idempotent and safe to re-run: rows are matched by slug and edges by their
    (source, prerequisite) pair. Every ordering edge is checked against the live
    graph before insertion, so the seed can never introduce a cycle even if the
    seed file is edited incorrectly.
    """
    async with SessionLocal() as session:
        categories = SkillCategoryRepository(session)
        skills = SkillRepository(session)

        # --- categories ---
        category_ids: dict[str, object] = {}
        created_categories = 0
        for seed in CATEGORIES:
            existing = await categories.get_by_slug(seed.slug)
            if existing is None:
                existing = await categories.create(
                    {
                        "slug": seed.slug,
                        "name": seed.name,
                        "description": seed.description,
                        "display_order": seed.display_order,
                    }
                )
                created_categories += 1
            category_ids[seed.slug] = existing.id
        await session.commit()

        # --- skills ---
        created_skills = 0
        for seed in SKILLS:
            existing = await skills.get_by_slug(seed.slug)
            if existing is None:
                await skills.create(
                    {
                        "slug": seed.slug,
                        "name": seed.name,
                        "description": seed.description,
                        "category_id": category_ids[seed.category],
                        "difficulty": seed.difficulty,
                        "aliases": list(seed.aliases),
                        "extra": dict(seed.extra),
                    }
                )
                created_skills += 1
        await session.commit()

        logger.info(
            "seeded taxonomy",
            extra={
                "categories_created": created_categories,
                "skills_created": created_skills,
                "categories_total": len(CATEGORIES),
                "skills_total": len(SKILLS),
            },
        )

        await _seed_edges(session)


async def _seed_edges(session: AsyncSession) -> None:
    skills = SkillRepository(session)
    prerequisites = PrerequisiteRepository(session)
    graph_service = SkillGraphService(session)

    slug_to_id = {s.slug: s.id for s in await skills.get_many_by_slug([e.source for e in EDGES] + [e.prerequisite for e in EDGES])}

    created_edges = 0
    skipped = 0
    for edge in EDGES:
        source_id = slug_to_id.get(edge.source)
        prereq_id = slug_to_id.get(edge.prerequisite)
        if source_id is None or prereq_id is None:
            logger.warning("edge references unknown skill", extra={"edge": f"{edge.source}<-{edge.prerequisite}"})
            skipped += 1
            continue
        if await prerequisites.get_edge(source_id, prereq_id) is not None:
            continue
        try:
            # add_prerequisite performs the cycle check and commits.
            await graph_service.add_prerequisite(
                _edge_payload(source_id, prereq_id, edge)
            )
            created_edges += 1
        except Exception as exc:  # pragma: no cover - defensive; seed is validated
            logger.error(
                "refused seed edge",
                extra={"edge": f"{edge.source}<-{edge.prerequisite}", "error": str(exc)},
            )
            skipped += 1

    logger.info(
        "seeded prerequisites",
        extra={"edges_created": created_edges, "skipped": skipped, "edges_total": len(EDGES)},
    )


def _edge_payload(source_id: object, prereq_id: object, edge: object):  # type: ignore[no-untyped-def]
    from app.schemas.skill import PrerequisiteCreate

    return PrerequisiteCreate(
        source_skill_id=source_id,  # type: ignore[arg-type]
        prerequisite_skill_id=prereq_id,  # type: ignore[arg-type]
        relationship_type=RelationshipType(edge.relationship_type),  # type: ignore[attr-defined]
        strength=edge.strength,  # type: ignore[attr-defined]
        min_level=edge.min_level,  # type: ignore[attr-defined]
    )


async def main() -> None:
    configure_logging()
    try:
        await seed_admin()
        await seed_skill_graph()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
