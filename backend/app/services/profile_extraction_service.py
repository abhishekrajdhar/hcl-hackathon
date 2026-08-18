"""LLM-powered profile extraction pipeline.

    message -> LLM -> validated ProfileExtraction -> business validation
            -> skill resolution -> ProfileDraft -> ProfileService -> database

The LLM only produces a typed `ProfileExtraction`; it never writes. Persistence
goes exclusively through `ProfileService.apply_draft`, and only skills that
resolve to existing catalogue rows are written — hallucinated or unknown skills
are reported, never created.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger
from app.llm.base import LLMError, LLMProvider
from app.llm.parsing import JsonExtractionError, extract_json_object
from app.llm.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_user_prompt
from app.llm.schemas import ProfileExtraction, extraction_json_schema
from app.repositories.skill import SkillRepository
from app.schemas.extraction import (
    ProfileExtractResponse,
    SkillCandidateRead,
    SkillResolutionRead,
)
from app.schemas.profile import ProfileDraft, SkillProficiencyDraft
from app.services.base import BaseService
from app.services.profile_service import ProfileService
from app.services.skill_resolver import SkillResolution, SkillResolver

logger = get_logger(__name__)

_TIMELINE_RE = re.compile(r"(\d{1,3})\s*(day|week|month|year)s?", re.IGNORECASE)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}
#: Default proficiency when a skill is mentioned without an implied level.
_DEFAULT_SKILL_PROFICIENCY = 0.5
#: Hint the model with a sample of catalogue names for canonical spellings.
_SKILL_HINT_LIMIT = 60


class ProfileExtractionService(BaseService):
    def __init__(self, session: AsyncSession, provider: LLMProvider) -> None:
        super().__init__(session)
        self.provider = provider
        self.resolver = SkillResolver(session)
        self.skills = SkillRepository(session)
        self.profiles = ProfileService(session)

    async def extract(
        self, user_id: uuid.UUID, message: str, *, apply: bool = False
    ) -> ProfileExtractResponse:
        # The profile write, if requested, needs the user to exist; check early
        # so we don't spend an LLM call on a bad request.
        await self.profiles._require_user(user_id)

        extraction = await self._call_and_validate(message)

        resolutions = await self.resolver.resolve_many([s.name for s in extraction.skills])
        proficiency_by_query = {
            s.name.strip().lower(): s.proficiency for s in extraction.skills
        }

        warnings = self._business_validation(extraction, resolutions)
        draft = self._to_draft(extraction, resolutions, proficiency_by_query)

        applied = False
        if apply:
            await self.profiles.apply_draft(user_id, draft)
            applied = True

        return ProfileExtractResponse(
            user_id=user_id,
            provider=self.provider.name,
            model=self.provider.model,
            extraction=extraction,
            resolved_skills=[
                self._resolution_read(r, proficiency_by_query.get(r.query.strip().lower()))
                for r in resolutions
            ],
            warnings=warnings,
            draft=draft,
            applied=applied,
        )

    # --- LLM call + robust validation ------------------------------------
    async def _call_and_validate(self, message: str) -> ProfileExtraction:
        """Call the provider and turn its output into a ProfileExtraction.

        Handles malformed JSON and schema violations with a bounded repair loop,
        then fails cleanly. The learner's text is passed as data only.
        """
        hint_names = [s.name for s in await self.skills.list(limit=_SKILL_HINT_LIMIT)]
        user_prompt = build_extraction_user_prompt(message, known_skill_names=hint_names)
        schema = extraction_json_schema()

        last_error = ""
        attempts = max(1, 1 + settings.LLM_MAX_REPAIR_ATTEMPTS)
        for attempt in range(attempts):
            prompt = user_prompt if attempt == 0 else self._repair_prompt(user_prompt, last_error)
            try:
                completion = await self.provider.complete(
                    system=EXTRACTION_SYSTEM_PROMPT,
                    user=prompt,
                    json_schema=schema,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                )
            except LLMError as exc:
                logger.error("llm transport error", extra={"provider": self.provider.name, "error": str(exc)})
                raise ServiceUnavailableError(
                    "The extraction service is temporarily unavailable",
                    error_code="llm_unavailable",
                ) from exc

            try:
                payload = extract_json_object(completion.text)
                return ProfileExtraction.model_validate(payload)
            except (JsonExtractionError, PydanticValidationError) as exc:
                last_error = str(exc)
                logger.warning(
                    "llm output failed validation",
                    extra={"provider": self.provider.name, "attempt": attempt, "error": last_error},
                )

        raise ServiceUnavailableError(
            "The model did not return a valid profile after retrying",
            error_code="llm_output_invalid",
            extra={"detail": last_error[:500]},
        )

    @staticmethod
    def _repair_prompt(original: str, error: str) -> str:
        return (
            f"{original}\n\nYour previous response could not be parsed into the "
            f"required schema. Error: {error}\nReturn ONLY a single valid JSON "
            "object that conforms to the schema."
        )

    # --- business validation --------------------------------------------
    @staticmethod
    def _business_validation(
        extraction: ProfileExtraction, resolutions: list[SkillResolution]
    ) -> list[str]:
        warnings: list[str] = []
        if not extraction.goal and not extraction.target_role:
            warnings.append("No clear goal or target role was stated; the extraction is ambiguous.")
        elif extraction.goal and len(extraction.goal.split()) < 2:
            warnings.append("The stated goal is very short and may be ambiguous.")

        if extraction.weekly_hours is None:
            warnings.append("Weekly available hours were not stated.")
        if not extraction.skills:
            warnings.append("No skills were detected in the message.")

        unknown = [r.query for r in resolutions if r.status == "unknown"]
        if unknown:
            warnings.append(
                "These skills were not found in the catalogue and were not added: "
                + ", ".join(unknown)
            )
        ambiguous = [r.query for r in resolutions if r.status == "ambiguous"]
        if ambiguous:
            warnings.append(
                "These skills matched more than one catalogue entry and need confirmation: "
                + ", ".join(ambiguous)
            )
        for note in extraction.ambiguities:
            warnings.append(f"Model flagged ambiguity: {note}")
        return warnings

    # --- mapping to the deterministic draft ------------------------------
    def _to_draft(
        self,
        extraction: ProfileExtraction,
        resolutions: list[SkillResolution],
        proficiency_by_query: dict[str, float | None],
    ) -> ProfileDraft:
        skills: list[SkillProficiencyDraft] = []
        for resolution in resolutions:
            # Only confident, unambiguous catalogue matches are ever written.
            if resolution.status != "matched" or resolution.skill is None:
                continue
            implied = proficiency_by_query.get(resolution.query.strip().lower())
            skills.append(
                SkillProficiencyDraft(
                    skill_id=resolution.skill.id,
                    proficiency=implied if implied is not None else _DEFAULT_SKILL_PROFICIENCY,
                    confidence=round(resolution.confidence, 4),
                )
            )

        preferred_modalities = self._extract_modalities(extraction)

        return ProfileDraft(
            goal_text_raw=extraction.goal,
            target_role=extraction.target_role,
            experience_level=extraction.experience_level,
            weekly_hours=extraction.weekly_hours,
            target_deadline=self._timeline_to_deadline(extraction.timeline),
            interests=extraction.interests or None,
            preferred_modalities=preferred_modalities,
            learning_preferences=extraction.learning_preferences or None,
            skills=skills,
            source_model=f"{self.provider.name}:{self.provider.model}",
            extraction_confidence=extraction.confidence,
        )

    @staticmethod
    def _extract_modalities(extraction: ProfileExtraction) -> list[str] | None:
        prefs = extraction.learning_preferences or {}
        for key in ("preferred_modalities", "modalities", "formats", "format"):
            value = prefs.get(key)
            if isinstance(value, list) and value:
                return [str(v) for v in value]
            if isinstance(value, str) and value:
                return [value]
        return None

    @staticmethod
    def _timeline_to_deadline(timeline: str | None, *, today: date | None = None) -> date | None:
        """Convert a free-text timeframe ('6 months') into a concrete date.

        Deterministic post-processing — the LLM only supplies free text; the date
        arithmetic is done here so it is reproducible and never hallucinated.
        """
        if not timeline:
            return None
        match = _TIMELINE_RE.search(timeline)
        if not match:
            return None
        amount = int(match.group(1))
        unit = match.group(2).lower()
        base = today or datetime.now(timezone.utc).date()
        return base + timedelta(days=amount * _UNIT_DAYS[unit])

    @staticmethod
    def _resolution_read(
        resolution: SkillResolution, proficiency: float | None
    ) -> SkillResolutionRead:
        return SkillResolutionRead(
            query=resolution.query,
            status=resolution.status,
            skill_id=resolution.skill.id if resolution.skill else None,
            slug=resolution.skill.slug if resolution.skill else None,
            name=resolution.skill.name if resolution.skill else None,
            confidence=resolution.confidence,
            proficiency=proficiency,
            method=resolution.method,
            candidates=[
                SkillCandidateRead(
                    skill_id=uuid.UUID(c.skill_id), slug=c.slug, name=c.name, score=c.score
                )
                for c in resolution.candidates
            ],
        )
