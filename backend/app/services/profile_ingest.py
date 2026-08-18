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

from app.schemas.profile import ProfileDraft

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


class ProfileExtractor(ABC):
    """Turns natural language into a validated ProfileDraft. Never persists."""

    #: Identifier recorded on the profile as extraction provenance.
    name: str = "abstract"

    @abstractmethod
    async def extract(self, text: str, *, context: dict | None = None) -> ProfileDraft:
        """Return a ProfileDraft. Implementations must not perform any I/O writes."""
        raise NotImplementedError


class DeterministicProfileExtractor(ProfileExtractor):
    """Placeholder extractor: rule-based, no model, fully deterministic.

    Exists so the ingestion endpoint and `ProfileService.apply_draft` are live
    and testable before the LLM lands. It only extracts what a couple of trivial
    rules can (weekly hours, a few modality keywords) and leaves everything else
    untouched. Same text always yields the same draft.
    """

    name = "deterministic-stub-v1"

    async def extract(self, text: str, *, context: dict | None = None) -> ProfileDraft:
        lowered = text.lower()

        weekly_hours: int | None = None
        match = _HOURS_PATTERN.search(text)
        if match:
            weekly_hours = min(168, int(match.group(1)))

        modalities = sorted(
            {canonical for word, canonical in _MODALITY_KEYWORDS.items() if word in lowered}
        )

        return ProfileDraft(
            weekly_hours=weekly_hours,
            preferred_modalities=modalities or None,
            source_model=self.name,
            # A stub has no real confidence in its reading.
            extraction_confidence=0.2 if (weekly_hours or modalities) else 0.0,
        )


#: Default extractor used by the API until the LLM implementation is registered.
default_extractor: ProfileExtractor = DeterministicProfileExtractor()
