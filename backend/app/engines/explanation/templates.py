"""Deterministic explanation templates built purely from evidence.

These are the grounded baseline (and the fallback when an LLM explanation fails
the grounding check). Each explanation kind frames the same structured facts
differently. No invented content — everything comes from the evidence object.
"""

from __future__ import annotations

from app.schemas.explanation import RecommendationEvidence


def _pct(value: float) -> str:
    return f"{round(value * 100)}%"


def _strengths_clause(evidence: RecommendationEvidence) -> str:
    if evidence.strengths:
        return f"You already have a solid foundation in {', '.join(evidence.strengths)}. "
    met = [p.skill for p in evidence.prerequisite_relationships if p.status == "met"]
    if met:
        return f"You already meet the prerequisites: {', '.join(met)}. "
    return ""


def _teaches_clause(evidence: RecommendationEvidence) -> str:
    skills = [rs.skill for rs in evidence.resource_skills]
    if not skills:
        return ""
    return f"This resource covers {', '.join(skills)}. "


def _roadmap_clause(evidence: RecommendationEvidence) -> str:
    pos = evidence.roadmap_position
    if pos is None:
        return ""
    unlocks = f", which prepares you for {', '.join(pos.unlocks)}" if pos.unlocks else ""
    return f"It sits in the '{pos.phase_title}' phase of your roadmap{unlocks}. "


def why_course(evidence: RecommendationEvidence) -> str:
    return (
        f"{_strengths_clause(evidence)}"
        f"Your current {evidence.learner_skill} proficiency is estimated at "
        f"{_pct(evidence.current_level)}, while your goal ({evidence.goal}) requires about "
        f"{_pct(evidence.required_level)}. "
        f"{_teaches_clause(evidence)}{_roadmap_clause(evidence)}"
    ).strip()


def why_now(evidence: RecommendationEvidence) -> str:
    met = [p.skill for p in evidence.prerequisite_relationships if p.status == "met"]
    unmet = [p.skill for p in evidence.prerequisite_relationships if p.status == "unmet"]
    if unmet:
        base = (
            f"This is not the right time yet: it assumes {', '.join(unmet)}, which you "
            f"have not reached. Build those first."
        )
    else:
        ready = f"You meet its prerequisites ({', '.join(met)}). " if met else ""
        base = (
            f"Now is the right time: {ready}with {evidence.learner_skill} at "
            f"{_pct(evidence.current_level)} and a target of {_pct(evidence.required_level)}, "
            f"this closes a gap of {_pct(evidence.skill_gap)}."
        )
    return base.strip()


def why_order(evidence: RecommendationEvidence) -> str:
    pos = evidence.roadmap_position
    prereqs = [p.skill for p in evidence.prerequisite_relationships]
    order_clause = (
        f"It follows {', '.join(prereqs)} because those are its prerequisites. "
        if prereqs
        else ""
    )
    place = (
        f"In your roadmap it belongs to the '{pos.phase_title}' phase"
        + (f", unlocking {', '.join(pos.unlocks)}. " if pos and pos.unlocks else ". ")
        if pos
        else ""
    )
    return (
        f"{order_clause}{place}"
        f"Learning {evidence.learner_skill} in this position keeps every prerequisite "
        f"before the skills that depend on it."
    ).strip()


def why_project(evidence: RecommendationEvidence) -> str:
    skills = [rs.skill for rs in evidence.resource_skills] or [evidence.learner_skill]
    return (
        f"This project applies {', '.join(skills)} toward {evidence.goal}. "
        f"With {evidence.learner_skill} at a target of {_pct(evidence.required_level)}, "
        f"building something end-to-end consolidates the skills in your roadmap into "
        f"demonstrable experience."
    ).strip()


def why_assessment(evidence: RecommendationEvidence) -> str:
    return (
        f"This checkpoint verifies your {evidence.learner_skill} before you advance. "
        f"Your current estimate is {_pct(evidence.current_level)} and the milestone targets "
        f"{_pct(evidence.required_level)}; a passing score confirms you are ready for the "
        f"skills that depend on it."
    ).strip()


TEMPLATES = {
    "why_course": why_course,
    "why_now": why_now,
    "why_order": why_order,
    "why_project": why_project,
    "why_assessment": why_assessment,
}


def render_template(evidence: RecommendationEvidence, kind: str) -> str:
    return TEMPLATES.get(kind, why_course)(evidence)
