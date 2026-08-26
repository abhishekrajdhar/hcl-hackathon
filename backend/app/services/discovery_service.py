"""Agentic career discovery and goal intelligence.

The model does the reasoning here — which careers fit these signals, what a
message is really asking for — because fit and phrasing are judgement, not
lookup. What keeps it honest is the seam around it:

    signals -> LLM -> schema-validated proposal -> grounded against the graph
            -> anything unresolvable dropped -> deterministic fallback if empty

The model proposes careers but cannot invent the skills they require: every
target skill is resolved against the real catalogue and silently-dropped
hallucinations are logged. With no provider configured (or a provider that
fails), the curated deterministic engine answers instead — degraded, never
down.
"""

from __future__ import annotations

import re
import uuid

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.engines.discovery import (
    ROLES,
    SCRIPTED_INTERVIEW,
    TRAITS,
    infer_traits,
    score_by_traits,
)
from app.engines.discovery import suggest_careers as static_suggest
from app.llm.base import LLMError, LLMProvider
from app.llm.parsing import JsonExtractionError, extract_json_object
from app.llm.prompts import (
    DISCOVERY_SYSTEM_PROMPT,
    GOAL_READING_SYSTEM_PROMPT,
    INTERVIEW_SYSTEM_PROMPT,
    build_discovery_user_prompt,
    build_goal_reading_user_prompt,
    build_interview_user_prompt,
)
from app.llm.schemas import (
    CareerAdvice,
    GoalReading,
    InterviewTurn,
    career_advice_json_schema,
    goal_reading_json_schema,
    interview_turn_json_schema,
)
from app.repositories.skill import SkillCategoryRepository, SkillRepository
from app.schemas.discovery import CareerSuggestionRead, CareerTargetSkill
from app.services.base import BaseService
from app.services.profile_service import ProfileService
from app.services.skill_resolver import SkillResolver

logger = get_logger(__name__)

#: Required level for a direction's first (defining) skill vs the rest.
PRIMARY_TARGET_LEVEL = 0.8
SECONDARY_TARGET_LEVEL = 0.7


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


class CareerDiscoveryService(BaseService):
    def __init__(self, session: AsyncSession, provider: LLMProvider | None) -> None:
        super().__init__(session)
        self.provider = provider
        self.resolver = SkillResolver(session)
        self.skills = SkillRepository(session)
        self.categories = SkillCategoryRepository(session)
        self.profiles = ProfileService(session)

    # --- signals ---------------------------------------------------------
    async def _learner_signals(
        self, user_id: uuid.UUID, interests: list[str]
    ) -> tuple[list[str], dict[str, float]]:
        merged = list(interests)
        known: dict[str, float] = {}
        try:
            profile = await self.profiles.get_for_user(user_id)
            merged.extend(i for i in (profile.interests or []) if i not in merged)
        except Exception:  # noqa: BLE001 - a missing profile is the expected case
            pass
        try:
            for entry in await self.profiles.list_skills(user_id):
                if entry.skill is not None:
                    known[entry.skill.slug] = entry.proficiency
        except Exception:  # noqa: BLE001
            pass
        return merged, known

    async def _catalogue_by_category(self) -> dict[str, list[str]]:
        categories = {c.id: c.name for c in await self.categories.list(limit=100)}
        grouped: dict[str, list[str]] = {}
        for skill in await self.skills.list(limit=500):
            grouped.setdefault(categories.get(skill.category_id, "Other"), []).append(skill.name)
        return grouped

    # --- discovery -------------------------------------------------------
    async def discover(
        self,
        user_id: uuid.UUID,
        *,
        interests: list[str],
        free_text: str,
        top_k: int = 3,
    ) -> list[CareerSuggestionRead]:
        merged, known = await self._learner_signals(user_id, interests)

        if self._agentic_enabled():
            advised = await self._advise(merged, known, free_text)
            if advised:
                return advised[:top_k]
            logger.info("agentic discovery yielded nothing usable; using static engine")

        return self._static(merged, known, free_text, top_k)

    def _agentic_enabled(self) -> bool:
        # The mock provider answers every prompt with profile-extraction JSON;
        # spending its repair loop on discovery every call buys nothing.
        return self.provider is not None and settings.LLM_PROVIDER != "mock"

    async def _advise(
        self, interests: list[str], known: dict[str, float], free_text: str
    ) -> list[CareerSuggestionRead]:
        catalogue = await self._catalogue_by_category()
        user_prompt = build_discovery_user_prompt(interests, known, free_text, catalogue)

        advice = await self._call_and_validate(user_prompt)
        if advice is None:
            return []

        # Ground every proposed skill against the real graph. The resolver is
        # deterministic; a name that does not resolve confidently is dropped.
        out: list[CareerSuggestionRead] = []
        for direction in advice.careers:
            resolutions = await self.resolver.resolve_many(direction.target_skills)
            resolved = [r.skill for r in resolutions if r.status == "matched" and r.skill]
            dropped = [r.query for r in resolutions if r.status != "matched"]
            if dropped:
                logger.info(
                    "discovery skills dropped as unresolvable",
                    extra={"career": direction.title, "dropped": dropped[:5]},
                )
            if not resolved:
                continue  # a career built entirely on invented skills is not advice
            out.append(
                CareerSuggestionRead(
                    slug=_slugify(direction.title),
                    title=direction.title,
                    pitch=direction.pitch,
                    score=0.0,  # the model ranks by order; a fake number would imply arithmetic
                    reasons=[direction.why],
                    target_skills=[
                        CareerTargetSkill(
                            skill_slug=skill.slug,
                            required_level=(
                                PRIMARY_TARGET_LEVEL if i == 0 else SECONDARY_TARGET_LEVEL
                            ),
                        )
                        for i, skill in enumerate(resolved)
                    ],
                )
            )
        return out

    async def _call_and_validate(self, user_prompt: str) -> CareerAdvice | None:
        assert self.provider is not None
        last_error = ""
        attempts = max(1, 1 + settings.LLM_MAX_REPAIR_ATTEMPTS)
        for attempt in range(attempts):
            prompt = user_prompt if attempt == 0 else (
                f"{user_prompt}\n\nYour previous answer was rejected: {last_error}\n"
                "Respond again with ONLY a valid JSON object for the schema."
            )
            try:
                completion = await self.provider.complete(
                    system=DISCOVERY_SYSTEM_PROMPT,
                    user=prompt,
                    json_schema=career_advice_json_schema(),
                    max_tokens=800,
                )
                return CareerAdvice.model_validate(extract_json_object(completion.text))
            except (LLMError, JsonExtractionError, PydanticValidationError) as exc:
                last_error = str(exc)[:300]
                logger.warning(
                    "discovery advice attempt failed",
                    extra={"attempt": attempt, "error": last_error},
                )
        return None

    def _static(
        self, interests: list[str], known: dict[str, float], free_text: str, top_k: int
    ) -> list[CareerSuggestionRead]:
        return [
            CareerSuggestionRead(
                slug=s.role.slug,
                title=s.role.title,
                pitch=s.role.pitch,
                score=s.score,
                reasons=list(s.reasons),
                target_skills=[
                    CareerTargetSkill(skill_slug=slug, required_level=lvl)
                    for slug, lvl in s.role.target_skills
                ],
            )
            for s in static_suggest(interests, known, free_text=free_text, top_k=top_k)
        ]

    # --- conversational discovery ------------------------------------------
    #: The interview never runs longer than this many questions.
    MAX_INTERVIEW_TURNS = 4

    async def interview(
        self, turns: list[tuple[str, str]]
    ) -> tuple[str | None, dict[str, float], list[CareerSuggestionRead]]:
        """One step of the discovery interview.

        Returns (next_question, trait_vector, careers). `next_question` is None
        when the interview is done, at which point `careers` carries the
        ranking. The split of labour is deliberate: the model reads the human
        (question-asking and trait estimation are judgement), while the ranking
        of careers from the vector is pure arithmetic — the same vector always
        yields the same careers, whoever produced it.
        """
        vector: dict[str, float] = {}
        question: str | None = None
        # The turn limit ends the interview whatever the model thinks, so a
        # conversation can never run forever.
        done = len(turns) >= self.MAX_INTERVIEW_TURNS

        if self._agentic_enabled():
            reading = await self._read_interview(turns)
            if reading is not None:
                vector = {t: v for t, v in reading.traits.items() if t in TRAITS}
                question = reading.next_question
                # Readiness requires something to rank on. A model that
                # declares itself ready while returning no traits — which it
                # will do on an empty transcript, where there is genuinely
                # nothing to read — has told us nothing, and honouring it ended
                # the interview on turn zero with an empty list of careers.
                done = done or (bool(vector) and (reading.ready or not question))
        if not vector:
            # Scripted fallback: fixed questions, keyword-inferred vector.
            vector = infer_traits([a for _, a in turns])
            index = len(turns)
            question = (
                SCRIPTED_INTERVIEW[index]["question"]
                if index < len(SCRIPTED_INTERVIEW)
                else None
            )
            # Only the exhaustion of the script can finish this branch; the
            # turn limit above still applies.
            done = done or question is None

        if not done:
            return question, vector, []

        by_slug = {r.slug: r for r in ROLES}
        careers = [
            CareerSuggestionRead(
                slug=m.role_slug,
                title=by_slug[m.role_slug].title,
                pitch=by_slug[m.role_slug].pitch,
                score=round(m.fit * 100, 1),
                reasons=(
                    [f"strong fit on {', '.join(d.replace('_', ' ') for d in m.drivers)}"]
                    if m.drivers
                    else []
                ),
                target_skills=[
                    CareerTargetSkill(skill_slug=slug, required_level=lvl)
                    for slug, lvl in by_slug[m.role_slug].target_skills
                ],
            )
            for m in score_by_traits(vector, top_k=3)
            if m.role_slug in by_slug
        ]
        if not careers:
            # Finishing with nothing to offer is a dead end for the learner.
            # Keep asking while the script has questions left; only past that
            # do we admit we could not read a direction.
            index = len(turns)
            if index < len(SCRIPTED_INTERVIEW):
                return SCRIPTED_INTERVIEW[index]["question"], vector, []
            logger.warning(
                "discovery interview produced no careers",
                extra={"turns": len(turns), "traits": len(vector)},
            )
        return None, vector, careers

    async def _read_interview(self, turns: list[tuple[str, str]]) -> InterviewTurn | None:
        assert self.provider is not None
        try:
            completion = await self.provider.complete(
                system=INTERVIEW_SYSTEM_PROMPT.format(traits=", ".join(TRAITS)),
                user=build_interview_user_prompt(turns),
                json_schema=interview_turn_json_schema(),
                max_tokens=300,
            )
            return InterviewTurn.model_validate(extract_json_object(completion.text))
        except (LLMError, JsonExtractionError, PydanticValidationError) as exc:
            logger.warning("interview reading failed; scripted fallback", extra={"error": str(exc)[:200]})
            return None

    # --- goal intelligence -------------------------------------------------
    async def read_goal(self, message: str) -> GoalReading | None:
        """The model's reading of a message's goal, or None to keep the regex
        classifier's verdict. One attempt, no repair: this runs on hot chat
        turns and the fallback is always available."""
        if not self._agentic_enabled():
            return None
        assert self.provider is not None
        try:
            completion = await self.provider.complete(
                system=GOAL_READING_SYSTEM_PROMPT,
                user=build_goal_reading_user_prompt(message),
                json_schema=goal_reading_json_schema(),
                max_tokens=200,
            )
            return GoalReading.model_validate(extract_json_object(completion.text))
        except (LLMError, JsonExtractionError, PydanticValidationError) as exc:
            logger.warning("goal reading failed; regex verdict stands", extra={"error": str(exc)[:200]})
            return None
