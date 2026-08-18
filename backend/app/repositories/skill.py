from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, literal, or_, select
from sqlalchemy.orm import joinedload

from app.models.enums import ORDERING_RELATIONSHIPS
from app.models.skill import Prerequisite, Skill, SkillCategory, UserSkill
from app.repositories.base import BaseRepository

#: Hard bound on recursive traversal in SQL, mirroring the engine's bound.
MAX_TRAVERSAL_DEPTH = 32

_ORDERING_VALUES = [t.value for t in ORDERING_RELATIONSHIPS]


class SkillCategoryRepository(BaseRepository[SkillCategory]):
    model = SkillCategory

    async def get_by_slug(self, slug: str) -> SkillCategory | None:
        return await self.get_by(slug=slug)

    async def list_ordered(self) -> list[SkillCategory]:
        stmt = select(SkillCategory).order_by(SkillCategory.display_order, SkillCategory.name)
        return list((await self.session.execute(stmt)).scalars().all())


class SkillRepository(BaseRepository[Skill]):
    model = Skill

    def _base_select(self) -> Select[tuple[Skill]]:
        # The category is part of every skill representation, so always join it.
        return select(Skill).options(joinedload(Skill.category))

    async def get_by_slug(self, slug: str) -> Skill | None:
        return await self.get_by(slug=slug)

    async def get_by(self, **filters: Any) -> Skill | None:
        stmt = self._base_select().filter_by(**filters).limit(1)
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def get_many(self, skill_ids: Sequence[uuid.UUID]) -> list[Skill]:
        if not skill_ids:
            return []
        stmt = self._base_select().where(Skill.id.in_(list(skill_ids)))
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def get_many_by_slug(self, slugs: Sequence[str]) -> list[Skill]:
        if not slugs:
            return []
        stmt = self._base_select().where(Skill.slug.in_(list(slugs)))
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def match_by_similarity(
        self, term: str, *, limit: int = 5, threshold: float = 0.3
    ) -> list[tuple[Skill, float]]:
        """Fuzzy-match a free-text name against skill name/slug via pg_trgm.

        Returns (skill, score) pairs ordered by descending trigram similarity,
        keeping only rows at or above `threshold`. This is the semantic fallback
        used when a mentioned skill has no exact catalogue name — it never
        creates anything, so an unknown or hallucinated skill simply yields a low
        score (or nothing) instead of polluting the catalogue.
        """
        cleaned = term.strip().lower()
        if not cleaned:
            return []
        score = func.greatest(
            func.similarity(func.lower(Skill.name), cleaned),
            func.similarity(Skill.slug, cleaned),
        ).label("score")
        stmt = (
            self._base_select()
            .add_columns(score)
            .where(Skill.is_active.is_(True), score >= threshold)
            .order_by(score.desc(), Skill.difficulty, Skill.slug)
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).unique().all()
        return [(row[0], float(row[1])) for row in rows]

    async def match_by_name_or_alias(self, term: str) -> Skill | None:
        """Exact, case-insensitive match on a skill's name or an alias element."""
        cleaned = term.strip().lower()
        if not cleaned:
            return None
        stmt = self._base_select().where(
            Skill.is_active.is_(True),
            or_(func.lower(Skill.name) == cleaned, Skill.aliases.any(cleaned)),
        )
        candidates = (await self.session.execute(stmt)).scalars().unique().all()
        # An exact name match wins over an alias-only match; both are exact, so
        # order by difficulty then slug for determinism.
        for skill in sorted(candidates, key=lambda s: (s.difficulty, s.slug)):
            if skill.name.strip().lower() == cleaned:
                return skill
        return candidates[0] if candidates else None

    @staticmethod
    def search_filter(term: str) -> Any:
        pattern = f"%{term.lower()}%"
        return or_(
            Skill.name.ilike(pattern),
            Skill.slug.ilike(pattern),
            Skill.aliases.any(term),  # exact alias match
        )


class UserSkillRepository(BaseRepository[UserSkill]):
    model = UserSkill

    def _base_select(self) -> Select[tuple[UserSkill]]:
        return select(UserSkill).options(
            joinedload(UserSkill.skill).joinedload(Skill.category)
        )

    async def get_for_user(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> UserSkill | None:
        stmt = self._base_select().where(
            UserSkill.user_id == user_id, UserSkill.skill_id == skill_id
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()


class PrerequisiteRepository(BaseRepository[Prerequisite]):
    """Edges of the skill DAG.

    Traversal is done in SQL with recursive CTEs so only the relevant subgraph
    is pulled into memory; the algorithms themselves live in
    `app.engines.skill_graph` and stay pure.
    """

    model = Prerequisite

    def _base_select(self) -> Select[tuple[Prerequisite]]:
        return select(Prerequisite).options(
            joinedload(Prerequisite.prerequisite_skill).joinedload(Skill.category),
            joinedload(Prerequisite.source_skill).joinedload(Skill.category),
        )

    async def get_edge(
        self, source_skill_id: uuid.UUID, prerequisite_skill_id: uuid.UUID
    ) -> Prerequisite | None:
        stmt = self._base_select().where(
            Prerequisite.source_skill_id == source_skill_id,
            Prerequisite.prerequisite_skill_id == prerequisite_skill_id,
        )
        return (await self.session.execute(stmt)).scalars().unique().one_or_none()

    async def list_prerequisites(self, source_skill_id: uuid.UUID) -> list[Prerequisite]:
        """Direct prerequisites: what this skill requires."""
        stmt = self._base_select().where(Prerequisite.source_skill_id == source_skill_id)
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def list_dependents(self, prerequisite_skill_id: uuid.UUID) -> list[Prerequisite]:
        """Direct dependents: what requires this skill."""
        stmt = self._base_select().where(
            Prerequisite.prerequisite_skill_id == prerequisite_skill_id
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

    def _closure_cte(
        self, roots: Sequence[uuid.UUID], *, upward: bool, max_depth: int
    ) -> Any:
        """Recursive CTE walking the DAG in one direction.

        `upward` follows prerequisites (what must come first); otherwise it
        follows dependents. `related` edges are excluded — they are an
        association, not a dependency.
        """
        table = Prerequisite.__table__
        step_from = table.c.source_skill_id if upward else table.c.prerequisite_skill_id
        step_to = table.c.prerequisite_skill_id if upward else table.c.source_skill_id
        ordering = table.c.relationship_type.in_(_ORDERING_VALUES)

        base = (
            select(step_to.label("skill_id"), literal(1).label("depth"))
            .where(step_from.in_(list(roots)), ordering)
        )
        cte = base.cte("closure", recursive=True)

        step_from_r = table.c.source_skill_id if upward else table.c.prerequisite_skill_id
        step_to_r = table.c.prerequisite_skill_id if upward else table.c.source_skill_id
        recursive = (
            select(step_to_r, cte.c.depth + 1)
            .join(cte, step_from_r == cte.c.skill_id)
            .where(cte.c.depth < max_depth, ordering)
        )
        return cte.union(recursive)

    async def _closure(
        self, roots: Sequence[uuid.UUID], *, upward: bool, max_depth: int
    ) -> dict[uuid.UUID, int]:
        if not roots:
            return {}
        cte = self._closure_cte(roots, upward=upward, max_depth=max_depth)
        stmt = select(cte.c.skill_id, func.min(cte.c.depth)).group_by(cte.c.skill_id)
        rows = await self.session.execute(stmt)
        root_set = set(roots)
        return {row[0]: int(row[1]) for row in rows if row[0] not in root_set}

    async def ancestor_ids(
        self, roots: Sequence[uuid.UUID], max_depth: int = MAX_TRAVERSAL_DEPTH
    ) -> dict[uuid.UUID, int]:
        """Transitive prerequisites of the roots, mapped to shallowest depth."""
        return await self._closure(roots, upward=True, max_depth=max_depth)

    async def descendant_ids(
        self, roots: Sequence[uuid.UUID], max_depth: int = MAX_TRAVERSAL_DEPTH
    ) -> dict[uuid.UUID, int]:
        """Skills transitively unlocked by the roots."""
        return await self._closure(roots, upward=False, max_depth=max_depth)

    async def edges_within(self, skill_ids: Sequence[uuid.UUID]) -> list[Prerequisite]:
        """Every edge whose endpoints both lie inside the given set."""
        if not skill_ids:
            return []
        ids = list(skill_ids)
        stmt = self._base_select().where(
            Prerequisite.source_skill_id.in_(ids),
            Prerequisite.prerequisite_skill_id.in_(ids),
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def all_edges(self) -> list[Prerequisite]:
        """Whole graph. Used by the integrity check, not by request paths."""
        stmt = select(Prerequisite)
        return list((await self.session.execute(stmt)).scalars().all())
