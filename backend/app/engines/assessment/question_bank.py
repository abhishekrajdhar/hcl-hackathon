"""Deterministic multiple-choice question generation.

A dependency-free fallback (and the default when no LLM is configured) that
produces valid, gradeable MC questions for a skill from templates, drawing
distractors from other skills. Every question it yields satisfies the same
Pydantic validation an LLM-generated one must pass. Deterministic given the same
inputs (a seed derived from the skill id keeps option ordering stable).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillFact:
    skill_id: uuid.UUID
    name: str
    description: str | None = None
    category_name: str | None = None


@dataclass(frozen=True, slots=True)
class GeneratedMCQuestion:
    stem: str
    options: list[dict[str, str]]  # [{key, text}]
    correct_key: str
    explanation: str
    difficulty: int


_LETTERS = ["a", "b", "c", "d", "e"]


def _rotate(items: list, seed: int) -> list:
    """Deterministic rotation so the correct option is not always first."""
    if not items:
        return items
    k = seed % len(items)
    return items[k:] + items[:k]


def generate_mc_questions(
    skill: SkillFact,
    distractor_skills: list[SkillFact],
    *,
    count: int,
    difficulty: int,
) -> list[GeneratedMCQuestion]:
    """Build `count` MC questions about `skill` using templates + distractors."""
    described = skill.description or f"the core concepts of {skill.name}"
    others = [d for d in distractor_skills if d.skill_id != skill.skill_id]

    templates = [
        (
            f"Which of the following best describes {skill.name}?",
            described,
            lambda d: d.description or f"the study of {d.name}",
        ),
        (
            f"A learning resource on which topic most directly develops {skill.name}?",
            skill.name,
            lambda d: d.name,
        ),
        (
            f"Which skill area does '{skill.name}' most belong to?",
            skill.category_name or skill.name,
            lambda d: d.category_name or d.name,
        ),
    ]

    questions: list[GeneratedMCQuestion] = []
    seed_base = skill.skill_id.int
    for index in range(count):
        stem, correct_text, distractor_of = templates[index % len(templates)]
        picks = others[index % max(1, len(others)) : index % max(1, len(others)) + 3]
        if len(picks) < 3:
            picks = (picks + others)[:3]
        distractor_texts = [distractor_of(d) for d in picks][:3]

        options_text = _rotate([correct_text, *distractor_texts], seed_base + index)
        options = [{"key": _LETTERS[i], "text": text} for i, text in enumerate(options_text)]
        correct_key = next(o["key"] for o in options if o["text"] == correct_text)

        questions.append(
            GeneratedMCQuestion(
                stem=f"{stem} (Q{index + 1})",
                options=options,
                correct_key=correct_key,
                explanation=f"{correct_text} — the option most specific to {skill.name}.",
                difficulty=difficulty,
            )
        )
    return questions
