"""Deterministic preference-vector layer for conversational discovery.

The conversation itself is agentic (the model asks and interprets); what stays
pure is everything arithmetic: the trait taxonomy, per-role trait affinities,
scoring a vector against the roles, and the scripted fallback interview that
runs when no model is configured. Same vector in, same ranking out.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The trait taxonomy. Every vector is {trait: 0..1}; missing = unknown.
TRAITS: tuple[str, ...] = (
    "building",    # making things that run
    "math",        # formal/mathematical depth
    "data",        # analysing information
    "language",    # text and language systems
    "visual",      # images, video, spatial
    "research",    # open questions, reading, experimenting
    "operations",  # infrastructure, reliability, automation
    "people",      # communication, explaining, collaborating
)

#: How strongly each career expresses each trait (0..1). Rows need not sum
#: to anything — scoring normalises by the role's own magnitude.
ROLE_TRAITS: dict[str, dict[str, float]] = {
    "machine-learning-engineer": {"building": 0.9, "math": 0.7, "data": 0.7, "operations": 0.4, "research": 0.4},
    "data-scientist": {"data": 0.95, "math": 0.75, "people": 0.6, "research": 0.55, "building": 0.35},
    "data-engineer": {"building": 0.85, "operations": 0.8, "data": 0.65, "math": 0.2},
    "nlp-engineer": {"language": 0.95, "building": 0.7, "math": 0.5, "research": 0.5},
    "computer-vision-engineer": {"visual": 0.95, "building": 0.75, "math": 0.6, "research": 0.45},
    "generative-ai-engineer": {"language": 0.7, "building": 0.85, "research": 0.55, "data": 0.4},
    "mlops-engineer": {"operations": 0.95, "building": 0.8, "data": 0.3, "people": 0.35},
}


@dataclass(frozen=True, slots=True)
class TraitMatch:
    role_slug: str
    #: 0..1 cosine-like fit between the learner vector and the role profile.
    fit: float
    #: The traits that drove the match, strongest first.
    drivers: tuple[str, ...]


def score_by_traits(vector: dict[str, float], top_k: int = 3) -> list[TraitMatch]:
    """Rank roles against a preference vector. Deterministic; ties break on
    the stable ROLE_TRAITS insertion order."""
    known = {t: v for t, v in vector.items() if t in TRAITS and v is not None}
    if not known:
        return []

    matches: list[TraitMatch] = []
    for slug, profile in ROLE_TRAITS.items():
        num = sum(known.get(t, 0.0) * w for t, w in profile.items())
        denom = sum(w for w in profile.values())
        fit = num / denom if denom else 0.0
        drivers = tuple(
            t for t, _ in sorted(
                ((t, known.get(t, 0.0) * w) for t, w in profile.items()),
                key=lambda kv: -kv[1],
            )[:2]
            if known.get(t, 0.0) > 0.4
        )
        matches.append(TraitMatch(role_slug=slug, fit=round(fit, 4), drivers=drivers))

    matches.sort(key=lambda m: -m.fit)
    return matches[:top_k]


# --- scripted fallback interview ---------------------------------------------
#: Question order matters: broad split first, then the axes that separate the
#: remaining candidates. Each option nudges named traits by the given amount.
SCRIPTED_INTERVIEW: tuple[dict, ...] = (
    {
        "question": "What do you enjoy more: building things that run, analysing information, or explaining ideas to people?",
        "hints": {"build": {"building": 0.9}, "analys": {"data": 0.9}, "explain": {"people": 0.9},
                  "people": {"people": 0.8}, "information": {"data": 0.8}},
    },
    {
        "question": "Which sounds most fun to work with: text and language, images and video, numbers and statistics, or servers and infrastructure?",
        "hints": {"text": {"language": 0.9}, "language": {"language": 0.9},
                  "image": {"visual": 0.9}, "video": {"visual": 0.85},
                  "number": {"math": 0.7, "data": 0.7}, "statis": {"math": 0.8, "data": 0.7},
                  "server": {"operations": 0.9}, "infra": {"operations": 0.9}},
    },
    {
        "question": "Do you prefer well-defined problems with clear answers, or open questions where you experiment and read?",
        "hints": {"open": {"research": 0.85}, "experiment": {"research": 0.8}, "read": {"research": 0.6},
                  "defined": {"building": 0.5}, "clear": {"building": 0.5}},
    },
    {
        "question": "How much do you enjoy mathematics — love it, tolerate it, or avoid it when possible?",
        "hints": {"love": {"math": 0.95}, "tolerat": {"math": 0.5}, "avoid": {"math": 0.1},
                  "enjoy": {"math": 0.8}, "hate": {"math": 0.05}},
    },
)


def infer_traits(answers: list[str]) -> dict[str, float]:
    """Fold scripted-interview answers into a preference vector.

    Keyword nudges accumulate; repeated evidence for a trait takes the max
    rather than summing past 1. Crude next to the model's reading — which is
    exactly why it is only the fallback."""
    vector: dict[str, float] = {}
    for i, answer in enumerate(answers):
        if i >= len(SCRIPTED_INTERVIEW):
            break
        low = answer.lower()
        for needle, nudges in SCRIPTED_INTERVIEW[i]["hints"].items():
            if needle in low:
                for trait, value in nudges.items():
                    vector[trait] = max(vector.get(trait, 0.0), value)
    return vector
