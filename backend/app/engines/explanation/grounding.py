"""Grounding safeguard for generated explanations.

Checks that a natural-language explanation makes no claim absent from the
structured evidence: every percentage it states must match an evidence value
(within tolerance), and every capitalised skill-like phrase it names must appear
in the evidence. Pure and deterministic. This is the guard that stops the LLM
inventing facts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_PERCENT_TOLERANCE = 2.0  # percentage points


@dataclass(frozen=True, slots=True)
class GroundingResult:
    grounded: bool
    unsupported_percentages: tuple[float, ...] = ()
    unsupported_terms: tuple[str, ...] = field(default=())


def _evidence_percentages(values: list[float]) -> list[float]:
    return [round(v * 100, 2) for v in values]


def check_grounding(
    text: str,
    *,
    allowed_levels: list[float],
    allowed_terms: list[str],
) -> GroundingResult:
    """Verify the text introduces no unsupported number or skill.

    `allowed_levels` are the 0-1 evidence levels (converted to %); `allowed_terms`
    are the skill/goal names that may be mentioned.
    """
    allowed_pct = _evidence_percentages(allowed_levels)
    unsupported_pct: list[float] = []
    for match in _PERCENT_RE.findall(text):
        value = float(match)
        if not any(abs(value - a) <= _PERCENT_TOLERANCE for a in allowed_pct):
            unsupported_pct.append(value)

    allowed_lower = {t.lower() for t in allowed_terms}
    # Candidate skill phrases: multi-word Title Case or known acronyms.
    unsupported_terms: list[str] = []
    for phrase in set(re.findall(r"\b([A-Z][A-Za-z0-9+\-]+(?:\s+[A-Z][A-Za-z0-9+\-]+)*)\b", text)):
        norm = phrase.lower()
        # ignore sentence-initial ordinary words by requiring it to look skill-ish:
        # either multi-word or contains a digit/+/- (e.g. "PyTorch", "CNN").
        if norm in allowed_lower:
            continue
        if any(norm in a or a in norm for a in allowed_lower):
            continue
        if " " in phrase or any(c.isdigit() for c in phrase) or phrase.isupper():
            unsupported_terms.append(phrase)

    grounded = not unsupported_pct and not unsupported_terms
    return GroundingResult(
        grounded=grounded,
        unsupported_percentages=tuple(unsupported_pct),
        unsupported_terms=tuple(unsupported_terms),
    )
