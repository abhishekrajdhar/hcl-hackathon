"""Deterministic career discovery — the "uncertain goal" branch.

A learner who says "I don't know what I want to do" cannot be routed to the
gap engine, because the gap engine needs a target. This module supplies one:
a curated catalogue of career roles, each defined AS a set of target skills
from the seeded skill graph, scored against whatever the learner has told us —
interests, skills they already have, things they say they enjoy.

Pure and deterministic: same learner signals in, same ranked careers out.
No model — the scoring is transparent arithmetic, and every recommendation
carries the evidence that produced it. The LLM may later rephrase the pitch;
it never chooses the career.

Each role's `target_skills` use graph slugs, so a chosen career feeds straight
into the existing path generator with no translation step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CareerRole:
    slug: str
    title: str
    pitch: str
    #: (skill_slug, required_level) — the goal vector the generator plans for.
    target_skills: tuple[tuple[str, float], ...]
    #: Lowercase keywords matched against interests and free text.
    keywords: tuple[str, ...]
    #: Skills that, if the learner already has them, suggest a head start.
    springboards: tuple[str, ...] = ()


#: Curated against the seeded skill graph — every slug below exists in it.
ROLES: tuple[CareerRole, ...] = (
    CareerRole(
        "machine-learning-engineer", "Machine Learning Engineer",
        "Build and ship models that learn from data — the classic route into applied AI.",
        (("machine-learning", 0.8), ("deep-learning", 0.7), ("model-deployment", 0.6)),
        ("machine learning", "ml", "ai", "models", "prediction", "algorithms"),
        ("python", "statistics", "linear-algebra"),
    ),
    CareerRole(
        "data-scientist", "Data Scientist",
        "Turn messy data into decisions: statistics, experimentation and storytelling.",
        (("statistics", 0.8), ("machine-learning", 0.7), ("data-visualization", 0.7)),
        ("data", "statistics", "analysis", "insights", "experiments", "numbers"),
        ("python", "sql", "probability"),
    ),
    CareerRole(
        "data-engineer", "Data Engineer",
        "Design the pipelines and platforms every data team stands on.",
        (("etl-pipelines", 0.8), ("big-data-spark", 0.7), ("data-warehousing", 0.7)),
        ("pipelines", "infrastructure", "databases", "sql", "backend", "systems"),
        ("sql", "python", "docker-containers"),
    ),
    CareerRole(
        "nlp-engineer", "NLP Engineer",
        "Teach machines to read and write — from embeddings to transformers.",
        (("nlp-fundamentals", 0.8), ("transformers", 0.7), ("word-embeddings", 0.7)),
        ("language", "text", "nlp", "chatbots", "words", "writing", "translation"),
        ("python", "machine-learning", "deep-learning"),
    ),
    CareerRole(
        "computer-vision-engineer", "Computer Vision Engineer",
        "Give software eyes: detection, segmentation and image understanding.",
        (("computer-vision", 0.8), ("cnn", 0.7), ("image-processing", 0.7)),
        ("vision", "images", "video", "cameras", "photography", "robotics"),
        ("python", "deep-learning", "linear-algebra"),
    ),
    CareerRole(
        "generative-ai-engineer", "Generative AI Engineer",
        "Build with large language models: RAG systems, fine-tuning and agents.",
        (("large-language-models", 0.8), ("rag-systems", 0.7), ("prompt-engineering", 0.6)),
        ("llm", "gpt", "generative", "chatgpt", "agents", "prompts", "rag"),
        ("python", "transformers", "nlp-fundamentals"),
    ),
    CareerRole(
        "mlops-engineer", "MLOps Engineer",
        "Keep models alive in production: deployment, monitoring and automation.",
        (("mlops-fundamentals", 0.8), ("model-deployment", 0.7), ("ci-cd-ml", 0.7)),
        ("devops", "deployment", "production", "operations", "docker", "kubernetes", "automation"),
        ("docker-containers", "version-control-git", "python"),
    ),
)

#: Score weights — transparent, so a recommendation can explain itself.
INTEREST_MATCH = 3.0   # the learner said they like this kind of thing
SPRINGBOARD = 2.0      # they already hold a skill this career builds on
TARGET_HEADSTART = 1.0 # they already hold one of the career's target skills


@dataclass(frozen=True)
class CareerSuggestion:
    role: CareerRole
    score: float
    #: Human-readable evidence, e.g. "matches your interest in 'language'".
    reasons: tuple[str, ...] = field(default_factory=tuple)


def suggest_careers(
    interests: list[str],
    known_skills: dict[str, float],
    free_text: str = "",
    top_k: int = 3,
) -> list[CareerSuggestion]:
    """Rank careers by fit with what the learner has actually told us.

    With no signals at all, every role scores zero and the catalogue order is
    returned — a browsable menu rather than a fake ranking. Ties break on
    catalogue order, so results are stable.
    """
    # Whole-word matching: a substring check would score "ai" against
    # "snail" or "training" and "ml" against "html", polluting every ranking
    # with phantom interests.
    words = set(re.findall(r"[a-z0-9+#]+", (" ".join(interests) + " " + free_text).lower()))
    haystack_text = " ".join(i.lower() for i in interests) + " " + free_text.lower()

    suggestions: list[CareerSuggestion] = []
    for role in ROLES:
        score = 0.0
        reasons: list[str] = []

        for kw in role.keywords:
            matched = kw in words if " " not in kw else kw in haystack_text
            if matched:
                score += INTEREST_MATCH
                reasons.append(f"matches your interest in “{kw}”")

        for slug in role.springboards:
            level = known_skills.get(slug, 0.0)
            if level >= 0.4:
                score += SPRINGBOARD
                reasons.append(f"builds on your {slug.replace('-', ' ')} ({level:.0%})")

        for slug, _required in role.target_skills:
            if known_skills.get(slug, 0.0) >= 0.4:
                score += TARGET_HEADSTART
                reasons.append(f"you already have a start in {slug.replace('-', ' ')}")

        suggestions.append(CareerSuggestion(role=role, score=round(score, 2), reasons=tuple(reasons)))

    suggestions.sort(key=lambda s: -s.score)
    return suggestions[:top_k]
