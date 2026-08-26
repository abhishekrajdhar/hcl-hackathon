"""The seam between natural-language input and the profile engine.

A `ProfileExtractor` turns free text (a chat message, a pasted resume) into a
schema-validated `ProfileDraft`. It does NOT write anything: `ProfileService`
applies the draft with deterministic code. This keeps the probabilistic step
(understanding language) strictly separated from the deterministic step
(updating the profile), so a future LLM implementation can drop in behind this
interface without any other part of the system trusting it with a write.

Today only `DeterministicProfileExtractor` exists — a dependency-free stub that
lets the whole ingestion path be wired and tested now. An
`LLMProfileExtractor(ProfileExtractor)` will be added in the LLM phase.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.engines.chat.intent import (
    IntentKind,
    detect_intent,
    extract_known_skills,
    extract_weekly_hours,
)
from app.schemas.profile import ProfileDraft, SkillProficiencyDraft

#: Very small keyword map so the stub extractor is demonstrably wired end to end
#: without pretending to do NLP. The real understanding arrives with the LLM.
_MODALITY_KEYWORDS = {
    "video": "video",
    "videos": "video",
    "reading": "text",
    "read": "text",
    "article": "text",
    "project": "project",
    "hands-on": "project",
    "interactive": "interactive",
}
_HOURS_PATTERN = re.compile(r"(\d{1,3})\s*(?:hours|hrs|h)\s*(?:per|/|a)\s*week", re.IGNORECASE)
#: Resume-style skill list: "Skills: Python, SQL, Docker" / "Tech stack — ...".
_SKILL_LINE_PATTERN = re.compile(
    r"(?:skills?|technologies|tech stack|tools|stack)\s*[:\-—]\s*(?P<skills>[^\n.]{3,160})",
    re.IGNORECASE,
)


class ProfileExtractor(ABC):
    """Turns natural language into a validated ProfileDraft. Never persists."""

    #: Identifier recorded on the profile as extraction provenance.
    name: str = "abstract"

    @abstractmethod
    async def extract(self, text: str, *, context: dict | None = None) -> ProfileDraft:
        """Return a ProfileDraft. Implementations must not perform any I/O writes."""
        raise NotImplementedError


class DeterministicProfileExtractor(ProfileExtractor):
    """Rule-based extractor: no model, fully deterministic.

    Reuses the chat engine's pure extractors (goal phrasing, "I know X and Y"
    skill claims, spoken time budgets) so a pasted resume gets the same reading
    quality as a chat message, plus one resume-specific rule for "Skills:
    Python, SQL, Docker" style lines. Unresolvable claims are carried as
    `skill_ref`s for the profile engine to resolve or drop — this module never
    guesses a skill id. Same text always yields the same draft.
    """

    name = "deterministic-v2"

    #: "Comfortable/known" self-report lands mid-band, same constant the chat
    #: pipeline uses, so the two intake routes cannot disagree about what a
    #: claim is worth.
    CLAIMED_PROFICIENCY = 0.7
    CLAIMED_CONFIDENCE = 0.45

    async def extract(self, text: str, *, context: dict | None = None) -> ProfileDraft:
        lowered = text.lower()

        weekly_hours: int | None = extract_weekly_hours(text)
        if weekly_hours is None:
            match = _HOURS_PATTERN.search(text)
            if match:
                weekly_hours = min(168, int(match.group(1)))

        modalities = sorted(
            {canonical for word, canonical in _MODALITY_KEYWORDS.items() if word in lowered}
        )

        # Skills: conversational claims ("I know Python and SQL") plus
        # resume-style list lines ("Skills: Python, SQL, Docker").
        names = list(extract_known_skills(text))
        for m in _SKILL_LINE_PATTERN.finditer(text):
            for part in re.split(r"[,;/•|]", m.group("skills")):
                name = part.strip().strip(".").lower()
                if 1 < len(name) <= 40 and name not in names:
                    names.append(name)
        skills = [
            SkillProficiencyDraft(
                skill_ref=name,
                proficiency=self.CLAIMED_PROFICIENCY,
                confidence=self.CLAIMED_CONFIDENCE,
            )
            for name in names[:12]
        ]

        # Goal, via the same phrasing rules the chat intake uses.
        intent = detect_intent(text)
        goal = intent.goal_text if intent.kind is IntentKind.SET_GOAL else None

        found_anything = bool(weekly_hours or modalities or skills or goal)
        return ProfileDraft(
            goal_text_raw=goal,
            target_role=goal,
            weekly_hours=weekly_hours,
            preferred_modalities=modalities or None,
            skills=skills,
            source_model=self.name,
            extraction_confidence=0.5 if found_anything else 0.0,
        )


#: Default extractor used by the API until the LLM implementation is registered.
default_extractor: ProfileExtractor = DeterministicProfileExtractor()
