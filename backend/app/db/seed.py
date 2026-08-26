"""Bootstrap data.

Idempotent: safe to run on every deploy. Currently seeds only the first admin
account, from FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD.

    python -m app.db.seed
"""

from __future__ import annotations

import asyncio

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.seeds.resources import RESOURCES
from app.db.seeds.skill_graph import CATEGORIES, EDGES, SKILLS
from app.db.session import SessionLocal, dispose_engine
from app.models.enums import RelationshipType, UserRole
from app.models.resource import Resource, ResourcePrerequisite, ResourceSkill
from app.repositories.resource import ResourceRepository
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


async def _reconcile_resource(session, resource, seed, slug_to_id) -> None:  # type: ignore[no-untyped-def]
    """Bring an existing catalogue row back in line with the seed.

    Scalar fields are overwritten; the skill and prerequisite links are
    replaced wholesale, which is simpler and safer than diffing them and keeps
    the row a faithful copy of the seed.
    """
    resource.title = seed.title
    resource.description = seed.description
    resource.url = seed.url
    resource.resource_type = seed.resource_type
    resource.modality = seed.modality
    resource.difficulty = seed.difficulty
    resource.estimated_hours = seed.estimated_hours
    resource.quality_score = seed.quality_score
    resource.rating = seed.rating
    resource.rating_count = seed.rating_count
    resource.extra = dict(seed.metadata)
    resource.is_active = True

    await session.execute(
        delete(ResourceSkill).where(ResourceSkill.resource_id == resource.id)
    )
    await session.execute(
        delete(ResourcePrerequisite).where(ResourcePrerequisite.resource_id == resource.id)
    )
    for teach in seed.teaches:
        skill_id = slug_to_id.get(teach.skill)
        if skill_id is None:
            continue
        session.add(
            ResourceSkill(
                resource_id=resource.id,
                skill_id=skill_id,
                teaches_level_from=teach.level_from,
                teaches_level_to=teach.level_to,
                is_primary=teach.is_primary,
            )
        )
    for slug, min_prof in seed.prerequisites:
        skill_id = slug_to_id.get(slug)
        if skill_id is None:
            continue
        session.add(
            ResourcePrerequisite(
                resource_id=resource.id, skill_id=skill_id, min_proficiency=min_prof
            )
        )


async def seed_resources() -> None:
    """Upsert the learning-resource catalogue with its skills and prerequisites.

    Idempotent: resources are matched by (provider, external_id); rows that
    already exist are left untouched. Skill slugs are resolved to ids, so an
    unknown slug is logged and skipped rather than corrupting a link.
    """
    async with SessionLocal() as session:
        resources = ResourceRepository(session)
        skills = SkillRepository(session)

        # Resolve every referenced slug once.
        referenced: set[str] = set()
        for seed in RESOURCES:
            referenced.update(t.skill for t in seed.teaches)
            referenced.update(slug for slug, _ in seed.prerequisites)
        slug_to_id = {s.slug: s.id for s in await skills.get_many_by_slug(sorted(referenced))}

        created = 0
        updated = 0
        for seed in RESOURCES:
            existing = await resources.get_by(
                provider=seed.provider, external_id=seed.external_id
            )
            if existing is not None:
                # Reconcile rather than skip. The catalogue is real content: a
                # video's title or runtime can change, and its skill links or
                # prerequisites can be corrected in the seed. Skipping meant a
                # re-seed silently did nothing, so edits never landed. The row
                # keeps its id, so learning paths pointing at it stay valid.
                await _reconcile_resource(session, existing, seed, slug_to_id)
                updated += 1
                continue

            resource = Resource(
                external_id=seed.external_id,
                provider=seed.provider,
                title=seed.title,
                description=seed.description,
                url=seed.url,
                resource_type=seed.resource_type,
                modality=seed.modality,
                difficulty=seed.difficulty,
                estimated_hours=seed.estimated_hours,
                quality_score=seed.quality_score,
                rating=seed.rating,
                rating_count=seed.rating_count,
                extra=dict(seed.metadata),
            )
            session.add(resource)
            await session.flush()  # assign resource.id

            for teach in seed.teaches:
                skill_id = slug_to_id.get(teach.skill)
                if skill_id is None:
                    logger.warning("resource teaches unknown skill", extra={"resource": seed.external_id, "skill": teach.skill})
                    continue
                session.add(
                    ResourceSkill(
                        resource_id=resource.id,
                        skill_id=skill_id,
                        teaches_level_from=teach.level_from,
                        teaches_level_to=teach.level_to,
                        is_primary=teach.is_primary,
                    )
                )
            for slug, min_prof in seed.prerequisites:
                skill_id = slug_to_id.get(slug)
                if skill_id is None:
                    logger.warning("resource requires unknown skill", extra={"resource": seed.external_id, "skill": slug})
                    continue
                session.add(
                    ResourcePrerequisite(
                        resource_id=resource.id, skill_id=skill_id, min_proficiency=min_prof
                    )
                )
            created += 1

        await session.commit()
        logger.info(
            "seeded resources",
            extra={
                "resources_created": created,
                "resources_updated": updated,
                "resources_total": len(RESOURCES),
            },
        )


async def seed_embeddings() -> None:
    """Generate embeddings for any resources that lack one.

    Uses the configured embedding provider (mock by default, so this runs with
    no heavy dependency). Idempotent: only-missing, so re-runs are cheap.
    """
    from app.embeddings.factory import get_embedding_provider
    from app.services.embedding_service import EmbeddingService

    provider = get_embedding_provider()
    async with SessionLocal() as session:
        result = await EmbeddingService(session, provider).embed_all(only_missing=True)
    logger.info(
        "seeded embeddings",
        extra={"embedded": result.embedded, "provider": provider.name, "dimension": result.dimension},
    )


async def main() -> None:
    configure_logging()
    try:
        await seed_admin()
        await seed_skill_graph()
        await seed_resources()
        await seed_embeddings()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
