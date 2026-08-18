"""In-process mock provider — no network, fully deterministic.

Two modes:
- Seeded: hand it a queue of canned response strings (including deliberately
  malformed ones) to drive tests of the parsing/repair path.
- Heuristic: with no queue it does a tiny rule-based extraction so the whole
  pipeline is demonstrable in dev without any API key.

It is the default provider, so the app and CI run with zero credentials.
"""

from __future__ import annotations

import json
import re
from collections import deque
from typing import Any

from app.llm.base import LLMCompletion, LLMProvider

_HOURS = re.compile(r"(\d{1,3})\s*(?:hours?|hrs?|h)\s*(?:per|/|a|each)?\s*week", re.IGNORECASE)
_ROLE = re.compile(
    r"(?:become|be|work as|role of|career as|transition into|get into)\s+(?:an?\s+)?"
    r"([a-z][a-z0-9 /+\-]{2,60}?)(?:\.|,|;|$| and | so | because )",
    re.IGNORECASE,
)
_EXPERIENCE = {
    "beginner": ("beginner", "just starting", "new to", "first-year", "first year", "no experience"),
    "intermediate": ("second-year", "second year", "intermediate", "some experience", "few projects", "two projects"),
    "advanced": ("advanced", "senior", "several years", "final-year", "final year"),
    "expert": ("expert", "years of experience", "professional", "lead"),
}
# A few well-known skill phrasings the heuristic can spot. The real model sees
# far more; catalogue resolution happens downstream regardless.
_SKILL_HINTS = {
    "python": ("python",),
    "scikit-learn": ("scikit-learn", "sklearn", "scikit learn"),
    "machine learning": ("machine learning", "ml"),
    "computer vision": ("computer vision",),
    "deep learning": ("deep learning",),
    "statistics": ("statistics", "stats"),
    "sql": ("sql",),
    "pytorch": ("pytorch",),
}


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, model: str = "mock-extractor-v1", responses: list[str] | None = None) -> None:
        self._model = model
        self._queue: deque[str] = deque(responses or [])

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMCompletion:
        if self._queue:
            return LLMCompletion(text=self._queue.popleft(), provider=self.name, model=self._model)
        return LLMCompletion(
            text=json.dumps(self._heuristic(user)), provider=self.name, model=self._model
        )

    def _heuristic(self, message: str) -> dict[str, Any]:
        text = message.strip()
        lowered = text.lower()

        weekly_hours: int | None = None
        if (m := _HOURS.search(text)) is not None:
            weekly_hours = min(168, int(m.group(1)))

        target_role: str | None = None
        if (m := _ROLE.search(text)) is not None:
            target_role = m.group(1).strip().rstrip(".")

        experience_level: str | None = None
        for level, cues in _EXPERIENCE.items():
            if any(cue in lowered for cue in cues):
                experience_level = level
                break

        skills: list[dict[str, Any]] = []
        for canonical, cues in _SKILL_HINTS.items():
            if any(cue in lowered for cue in cues):
                strong = any(w in lowered for w in ("well", "strong", "proficient", "expert in"))
                skills.append(
                    {
                        "name": canonical,
                        "proficiency": 0.75 if strong else 0.5,
                        "evidence": None,
                    }
                )

        goal: str | None = None
        if target_role:
            goal = f"Become a {target_role}"

        return {
            "experience_level": experience_level,
            "goal": goal,
            "target_role": target_role,
            "interests": [],
            "skills": skills,
            "weekly_hours": weekly_hours,
            "timeline": None,
            "learning_preferences": {},
            "confidence": 0.4,
            "ambiguities": [] if target_role else ["target role not clearly stated"],
        }
