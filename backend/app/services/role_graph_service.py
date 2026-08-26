"""Dynamic role graphs — "the learner chooses the destination, the AI builds
the world".

The seeded catalogue cannot name every destination. When a goal does not
resolve to an existing skill, this service asks the model to DESIGN the role's
required-skill graph — reusing catalogue skills where they fit, proposing new
ones only where the catalogue is genuinely missing them — and then materialises
that design with deterministic code:

    goal text -> LLM role-graph spec (schema-validated)
             -> names resolved against the catalogue
             -> unresolved names become real skill rows
             -> prerequisite edges written through the cycle-checked graph API
             -> a target vector the ordinary gap/path engines plan from

The model designs; it never writes. Every row and edge goes through the same
validated services an admin would use, cycles are refused at write time, and
system-created skills are marked with their origin for audit. Two learners
naming the same new role converge on the same graph, because the second run
resolves what the first created.

Fallbacks, in order: exact catalogue match (no model needed), the model's
design, the curated career engine's nearest role, and finally a 422 that
points at career discovery instead of a dead end.
"""

from __future__ import annotations

import re

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, ValidationError
from app.core.logging import get_logger
from app.engines.discovery import suggest_careers as static_suggest
from app.llm.base import LLMError, LLMProvider
from app.llm.parsing import JsonExtractionError, extract_json_object
from app.llm.prompts import ROLE_GRAPH_SYSTEM_PROMPT, build_role_graph_user_prompt
from app.llm.schemas import RoleGraphSpec, role_graph_json_schema
from app.models.enums import RelationshipType
from app.models.skill import Skill
from app.repositories.skill import SkillCategoryRepository, SkillRepository
from app.schemas.skill import PrerequisiteCreate
from app.schemas.skill_gap import RequiredSkillInput
from app.services.base import BaseService
from app.services.skill_graph_service import SkillGraphService
from app.services.skill_resolver import SkillResolver

logger = get_logger(__name__)

#: Level used when a goal resolves directly to one catalogue skill.
DIRECT_GOAL_LEVEL = 0.8


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:128]


class RoleGraphService(BaseService):
    def __init__(self, session: AsyncSession, provider: LLMProvider | None) -> None:
        super().__init__(session)
        self.provider = provider
        self.resolver = SkillResolver(session)
        self.skills = SkillRepository(session)
        self.categories = SkillCategoryRepository(session)
        self.graph = SkillGraphService(session)

    # --- public entry ------------------------------------------------------
    async def targets_for_goal(self, goal_text: str | None) -> list[RequiredSkillInput]:
        """Turn any goal phrase into a target-skill vector the engines can plan
        from, growing the graph when the destination is new."""
        text = (goal_text or "").strip()
        if not text:
            raise ValidationError(
                "Tell me the goal you want to plan for, or pick target skills.",
                error_code="no_goal",
            )

        # 1) The goal names a catalogue skill: no model needed.
        resolution = await self.resolver.resolve(text)
        if resolution.status == "matched" and resolution.skill is not None:
            return [
                RequiredSkillInput(
                    skill_id=resolution.skill.id, required_level=DIRECT_GOAL_LEVEL
                )
            ]

        # 2) Agentic: the model designs the role graph; we materialise it.
        if self.provider is not None and settings.LLM_PROVIDER != "mock":
            spec = await self._design(text)
            if spec is not None:
                targets = await self._materialise(spec)
                if targets:
                    return targets
                logger.warning("role graph spec materialised to nothing; falling back")

        # 3) Curated fallback: the nearest role in the static career engine.
        nearest = static_suggest([], {}, free_text=text, top_k=1)
        if nearest and nearest[0].score > 0:
            role = nearest[0].role
            logger.info(
                "goal mapped to nearest curated role",
                extra={"goal": text[:60], "role": role.slug},
            )
            targets: list[RequiredSkillInput] = []
            for slug, level in role.target_skills:
                skill = await self.skills.get_by_slug(slug)
                if skill is not None:
                    targets.append(
                        RequiredSkillInput(skill_id=skill.id, required_level=level)
                    )
            if targets:
                return targets

        # 4) An honest wall, with a door in it.
        suggestions = ", ".join(c.name for c in resolution.candidates[:3])
        hint = f" Did you mean: {suggestions}?" if suggestions else ""
        raise ValidationError(
            f"I couldn't map '{text}' onto a learning route yet.{hint} "
            "Try career discovery and I'll suggest directions that fit you.",
            error_code="goal_unresolved",
        )

    # --- model call --------------------------------------------------------
    async def _design(self, goal_text: str) -> RoleGraphSpec | None:
        assert self.provider is not None
        catalogue = await self._catalogue_by_category()
        user_prompt = build_role_graph_user_prompt(goal_text, catalogue)

        last_error = ""
        attempts = max(1, 1 + settings.LLM_MAX_REPAIR_ATTEMPTS)
        for attempt in range(attempts):
            prompt = user_prompt if attempt == 0 else (
                f"{user_prompt}\n\nYour previous answer was rejected: {last_error}\n"
                "Respond again with ONLY a valid JSON object for the schema."
            )
            try:
                completion = await self.provider.complete(
                    system=ROLE_GRAPH_SYSTEM_PROMPT,
                    user=prompt,
                    json_schema=role_graph_json_schema(),
                    max_tokens=900,
                )
                return RoleGraphSpec.model_validate(extract_json_object(completion.text))
            except (LLMError, JsonExtractionError, PydanticValidationError) as exc:
                last_error = str(exc)[:300]
                logger.warning(
                    "role graph design attempt failed",
                    extra={"attempt": attempt, "error": last_error},
                )
        return None

    async def _catalogue_by_category(self) -> dict[str, list[str]]:
        categories = {c.id: c.name for c in await self.categories.list(limit=100)}
        grouped: dict[str, list[str]] = {}
        for skill in await self.skills.list(limit=500):
            grouped.setdefault(categories.get(skill.category_id, "Other"), []).append(skill.name)
        return grouped

    # --- deterministic materialisation --------------------------------------
    async def _materialise(self, spec: RoleGraphSpec) -> list[RequiredSkillInput]:
        """Write the design into the graph through the validated services.

        Names resolve to existing skills where possible; the rest are created.
        Edges go through the cycle-checked graph API — an edge that would close
        a cycle or already exists is skipped, never forced. Idempotent: running
        the same spec twice resolves what the first run created.
        """
        by_name: dict[str, Skill] = {}
        for entry in spec.skills:
            skill = await self._resolve_or_create(entry.name, entry.category, entry.difficulty)
            if skill is not None:
                by_name[entry.name.strip().lower()] = skill

        # Edges after all nodes exist, so in-spec prerequisites resolve.
        for entry in spec.skills:
            source = by_name.get(entry.name.strip().lower())
            if source is None:
                continue
            for prereq_name in entry.prerequisites:
                prereq = by_name.get(prereq_name.strip().lower())
                if prereq is None:
                    resolution = await self.resolver.resolve(prereq_name)
                    prereq = resolution.skill if resolution.status == "matched" else None
                if prereq is None or prereq.id == source.id:
                    continue
                try:
                    await self.graph.add_prerequisite(
                        PrerequisiteCreate(
                            source_skill_id=source.id,
                            prerequisite_skill_id=prereq.id,
                            relationship_type=RelationshipType.HARD_PREREQUISITE,
                            rationale=f"Generated for role: {spec.role_title}",
                        )
                    )
                except ConflictError:
                    pass  # edge already there — two learners, same role
                except ValidationError as exc:
                    # A cycle the model failed to avoid. The graph's integrity
                    # wins; the edge is dropped and the route still plans.
                    logger.warning(
                        "role graph edge refused",
                        extra={"source": source.slug, "prereq": prereq.slug, "why": str(exc)[:120]},
                    )

        return [
            RequiredSkillInput(
                skill_id=by_name[entry.name.strip().lower()].id,
                required_level=entry.required_level,
            )
            for entry in spec.skills
            if entry.name.strip().lower() in by_name
        ]

    async def _resolve_or_create(
        self, name: str, category_name: str | None, difficulty: int
    ) -> Skill | None:
        resolution = await self.resolver.resolve(name)
        if resolution.status == "matched" and resolution.skill is not None:
            return resolution.skill

        slug = _slugify(name)
        if not slug:
            return None
        existing = await self.skills.get_by_slug(slug)
        if existing is not None:
            return existing

        category = await self._category_for(category_name)
        skill = await self.skills.create(
            {
                "slug": slug,
                "name": name.strip()[:255],
                "description": f"Added automatically while planning a route to a learner's goal.",
                "category_id": category.id,
                "difficulty": difficulty,
                # Audit trail: these rows were grown by the role-graph service,
                # not curated by hand.
                "extra": {"origin": "role_graph"},
            }
        )
        await self.session.flush()
        logger.info("skill grown for role graph", extra={"slug": slug})
        return skill

    async def _category_for(self, category_name: str | None):
        if category_name:
            for cat in await self.categories.list(limit=100):
                if cat.name.strip().lower() == category_name.strip().lower():
                    return cat
        # A stable home for grown skills whose category the model got wrong.
        existing = await self.categories.get_by_slug("emerging")
        if existing is not None:
            return existing
        cat = await self.categories.create(
            {
                "slug": "emerging",
                "name": "Emerging",
                "description": "Skills grown dynamically from learner goals.",
                "display_order": 99,
            }
        )
        await self.session.flush()
        return cat
