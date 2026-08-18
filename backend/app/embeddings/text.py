"""Canonical text representations built before embedding.

One deterministic string per entity, assembled from the same fields every time,
so re-embedding is reproducible and two resources with the same content embed
identically. Pure functions — no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable


def _clean(value: str | None) -> str:
    return " ".join(value.split()) if value else ""


def _join_names(names: Iterable[str]) -> str:
    # Sort for determinism so link ordering never changes the embedding.
    unique = sorted({_clean(n) for n in names if _clean(n)})
    return ", ".join(unique)


def canonical_resource_text(
    *,
    title: str,
    description: str | None,
    resource_type: str,
    taught_skill_names: Iterable[str],
    prerequisite_skill_names: Iterable[str],
) -> str:
    """The text embedded for a resource: title, type, description, the skills it
    teaches, and the skills it assumes."""
    lines = [
        f"Title: {_clean(title)}",
        f"Type: {resource_type}",
    ]
    description = _clean(description)
    if description:
        lines.append(f"Description: {description}")
    taught = _join_names(taught_skill_names)
    if taught:
        lines.append(f"Teaches: {taught}")
    prereqs = _join_names(prerequisite_skill_names)
    if prereqs:
        lines.append(f"Prerequisites: {prereqs}")
    return "\n".join(lines)


def canonical_skill_query_text(
    *, name: str, description: str | None = None, aliases: Iterable[str] = ()
) -> str:
    parts = [_clean(name)]
    aka = _join_names(aliases)
    if aka:
        parts.append(f"also known as {aka}")
    description = _clean(description)
    if description:
        parts.append(description)
    return ". ".join(p for p in parts if p)


def canonical_goal_query_text(
    *,
    title: str | None = None,
    description: str | None = None,
    target_role: str | None = None,
    target_skill_names: Iterable[str] = (),
) -> str:
    parts: list[str] = []
    if _clean(title):
        parts.append(_clean(title))
    if _clean(target_role):
        parts.append(f"Target role: {_clean(target_role)}")
    if _clean(description):
        parts.append(_clean(description))
    skills = _join_names(target_skill_names)
    if skills:
        parts.append(f"Skills to develop: {skills}")
    return ". ".join(parts)


def canonical_profile_query_text(
    *,
    goal_text: str | None = None,
    target_role: str | None = None,
    interests: Iterable[str] = (),
    focus_skill_names: Iterable[str] = (),
) -> str:
    parts: list[str] = []
    if _clean(goal_text):
        parts.append(_clean(goal_text))
    if _clean(target_role):
        parts.append(f"Target role: {_clean(target_role)}")
    interest_text = _join_names(interests)
    if interest_text:
        parts.append(f"Interests: {interest_text}")
    skills = _join_names(focus_skill_names)
    if skills:
        parts.append(f"Focus skills: {skills}")
    return ". ".join(parts)
