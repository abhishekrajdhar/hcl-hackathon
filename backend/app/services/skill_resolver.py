"""Resolve free-text skill names to canonical catalogue skills.

The anti-hallucination boundary: an LLM may name any skill, but a name only
becomes a stored `user_skill` if it resolves to a row that already exists. This
never creates a skill. Resolution runs a deterministic ladder — exact slug →
exact name/alias → trigram similarity — and classifies the outcome so the caller
can auto-apply confident matches, surface ambiguous ones for confirmation, and
report unknown/hallucinated ones without touching the catalogue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill
from app.repositories.skill import SkillRepository

ResolutionStatus = Literal["matched", "ambiguous", "unknown"]

#: A trigram score at or above this is treated as a confident match.
CONFIDENT_THRESHOLD = 0.6
#: Below this a candidate is not even worth surfacing.
CANDIDATE_THRESHOLD = 0.3
#: If the top two candidates are within this, the match is ambiguous.
AMBIGUITY_GAP = 0.12

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-")


@dataclass(frozen=True, slots=True)
class Candidate:
    skill_id: str
    slug: str
    name: str
    score: float


@dataclass(frozen=True, slots=True)
class SkillResolution:
    query: str
    status: ResolutionStatus
    skill: Skill | None
    confidence: float
    method: str
    candidates: tuple[Candidate, ...]


class SkillResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.skills = SkillRepository(session)

    async def resolve(self, name: str) -> SkillResolution:
        query = name.strip()
        if not query:
            return SkillResolution(query, "unknown", None, 0.0, "empty", ())

        # 1) exact slug (handles "computer vision" -> "computer-vision")
        exact_slug = await self.skills.get_by_slug(_slugify(query))
        if exact_slug is not None:
            return SkillResolution(query, "matched", exact_slug, 1.0, "slug", ())

        # 2) exact name or alias
        exact = await self.skills.match_by_name_or_alias(query)
        if exact is not None:
            return SkillResolution(query, "matched", exact, 0.97, "name_or_alias", ())

        # 3) fuzzy trigram similarity
        matches = await self.skills.match_by_similarity(
            query, limit=5, threshold=CANDIDATE_THRESHOLD
        )
        if not matches:
            return SkillResolution(query, "unknown", None, 0.0, "no_match", ())

        candidates = tuple(
            Candidate(str(skill.id), skill.slug, skill.name, round(score, 4))
            for skill, score in matches
        )
        best_skill, best_score = matches[0]
        second_score = matches[1][1] if len(matches) > 1 else 0.0

        confident = best_score >= CONFIDENT_THRESHOLD
        clearly_ahead = (best_score - second_score) >= AMBIGUITY_GAP
        if confident and clearly_ahead:
            return SkillResolution(
                query, "matched", best_skill, round(best_score, 4), "similarity", candidates
            )
        # Best but not confident enough, or tied with the runner-up.
        return SkillResolution(
            query, "ambiguous", None, round(best_score, 4), "similarity", candidates
        )

    async def resolve_many(self, names: list[str]) -> list[SkillResolution]:
        # De-duplicate case-insensitively while preserving first-seen order.
        seen: dict[str, str] = {}
        for raw in names:
            key = raw.strip().lower()
            if key and key not in seen:
                seen[key] = raw
        return [await self.resolve(original) for original in seen.values()]
