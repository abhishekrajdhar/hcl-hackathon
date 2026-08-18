from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, or_, select, text
from sqlalchemy.orm import joinedload

from app.models.skill import Prerequisite, Skill, UserSkill
from app.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    model = Skill

    async def get_by_slug(self, slug: str) -> Skill | None:
        return await self.get_by(slug=slug)

    async def get_many(self, skill_ids: Sequence[uuid.UUID]) -> list[Skill]:
        if not skill_ids:
            return []
        stmt = select(Skill).where(Skill.id.in_(list(skill_ids)))
        return list((await self.session.execute(stmt)).scalars().all())

    @staticmethod
    def search_filter(term: str):  # type: ignore[no-untyped-def]
        pattern = f"%{term.lower()}%"
        return or_(
            Skill.name.ilike(pattern),
            Skill.slug.ilike(pattern),
            Skill.aliases.any(term),  # exact alias match
        )


class UserSkillRepository(BaseRepository[UserSkill]):
    model = UserSkill

    def _base_select(self) -> Select[tuple[UserSkill]]:
        return select(UserSkill).options(joinedload(UserSkill.skill))

    async def get_for_user(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> UserSkill | None:
        stmt = self._base_select().where(
            UserSkill.user_id == user_id, UserSkill.skill_id == skill_id
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()


class PrerequisiteRepository(BaseRepository[Prerequisite]):
    model = Prerequisite

    async def get_edge(
        self, skill_id: uuid.UUID, prerequisite_skill_id: uuid.UUID
    ) -> Prerequisite | None:
        return await self.get_by(skill_id=skill_id, prerequisite_skill_id=prerequisite_skill_id)

    async def list_for_skill(self, skill_id: uuid.UUID) -> list[Prerequisite]:
        stmt = select(Prerequisite).where(Prerequisite.skill_id == skill_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def closure(self, skill_id: uuid.UUID, max_depth: int = 16) -> list[tuple[uuid.UUID, int]]:
        """Transitive prerequisite closure via a recursive CTE.

        Returns (skill_id, depth) pairs excluding the root. Depth is bounded so a
        malformed graph can never produce an unbounded scan.
        """
        stmt = text(
            """
            WITH RECURSIVE closure(skill_id, depth) AS (
                SELECT p.prerequisite_skill_id, 1
                FROM prerequisites p
                WHERE p.skill_id = :root
              UNION
                SELECT p.prerequisite_skill_id, c.depth + 1
                FROM prerequisites p
                JOIN closure c ON p.skill_id = c.skill_id
                WHERE c.depth < :max_depth
            )
            SELECT skill_id, MIN(depth) AS depth
            FROM closure
            GROUP BY skill_id
            ORDER BY depth
            """
        )
        rows = await self.session.execute(stmt, {"root": skill_id, "max_depth": max_depth})
        return [(row.skill_id, row.depth) for row in rows]

    async def edges_within(self, skill_ids: Sequence[uuid.UUID]) -> list[Prerequisite]:
        if not skill_ids:
            return []
        ids = list(skill_ids)
        stmt = select(Prerequisite).where(
            Prerequisite.skill_id.in_(ids), Prerequisite.prerequisite_skill_id.in_(ids)
        )
        return list((await self.session.execute(stmt)).scalars().all())
