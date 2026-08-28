"""Deterministic view of what a learner has already done.

Two sources of prior learning, deliberately kept apart because they carry very
different evidence:

* **Recorded completions** — `user_progress` rows for a catalogue resource.
  Hard evidence: the learner finished that exact resource here.
* **Declared completions** — `learner_profiles.completed_courses`, which the
  learner typed or the extractor pulled out of a sentence. Soft evidence about
  something that may or may not correspond to a catalogue row.

Both end up suppressing a recommendation, but a declared course only matches a
catalogue resource when the match is unambiguous — an id, a URL, an exact
normalised title, or (last) a guarded token match. The guards exist because
silently hiding a resource the learner never took is a worse failure than
showing one they did: a token match needs at least two meaningful tokens, all
of them present in the candidate title, exactly ONE candidate may qualify,
and a stated provider disagreement still vetoes it.

Pure: no DB, no clock, no model.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Iterable, Literal

SuppressionReason = Literal["completed_here", "declared_completed"]


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    """The little a resource needs to expose to be matched against history."""

    resource_id: uuid.UUID
    title: str
    provider: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class DeclaredCourse:
    """A `completed_courses` entry off the learner profile."""

    title: str
    provider: str | None = None
    url: str | None = None
    resource_id: uuid.UUID | None = None


def _norm_title(value: str | None) -> str:
    """Case, punctuation and spacing folded away; nothing else."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


#: Words that carry no identity when comparing course titles — the fuzzy tier
#: matches on what names the course, not on how it is packaged.
_TITLE_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
    "full", "complete", "course", "tutorial", "class", "bootcamp", "guide",
    "beginner", "beginners", "introduction", "intro", "learn", "learning",
    "masterclass", "crash", "university", "free", "hours", "hour", "part",
})


def _title_tokens(value: str | None) -> frozenset[str]:
    return frozenset(
        tok for tok in _norm_title(value).split()
        if tok not in _TITLE_STOPWORDS and len(tok) > 1
    )


def _norm_url(value: str | None) -> str:
    """Scheme, `www.`, trailing slash and query string folded away."""
    if not value:
        return ""
    cleaned = value.strip().lower()
    cleaned = re.sub(r"^https?://", "", cleaned)
    cleaned = re.sub(r"^www\.", "", cleaned)
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]
    return cleaned.rstrip("/")


def match_declared_courses(
    declared: Iterable[DeclaredCourse],
    catalogue: Iterable[CatalogueEntry],
) -> dict[uuid.UUID, str]:
    """Resolve declared courses onto catalogue resource ids.

    Returns `{resource_id: the declaration that matched}`. Three ways to match,
    in descending confidence: an explicit `resource_id`, an equal URL, or an
    equal normalised title. A title match is rejected when both sides name a
    provider and the providers disagree — "Deep Learning" by two different
    publishers is two different resources.
    """
    entries = list(catalogue)
    by_id = {e.resource_id: e for e in entries}
    by_url: dict[str, CatalogueEntry] = {}
    by_title: dict[str, list[CatalogueEntry]] = {}
    for entry in entries:
        url = _norm_url(entry.url)
        if url:
            by_url.setdefault(url, entry)
        by_title.setdefault(_norm_title(entry.title), []).append(entry)

    matched: dict[uuid.UUID, str] = {}
    for course in declared:
        if course.resource_id and course.resource_id in by_id:
            matched.setdefault(course.resource_id, course.title)
            continue

        url = _norm_url(course.url)
        if url and url in by_url:
            matched.setdefault(by_url[url].resource_id, course.title)
            continue

        title = _norm_title(course.title)
        if not title:
            continue
        # An ambiguous title (two catalogue rows share it) is not a match.
        hits = by_title.get(title, [])
        if len(hits) == 1:
            hit = hits[0]
            if not _providers_disagree(course, hit):
                matched.setdefault(hit.resource_id, course.title)
                continue
        if hits:
            continue

        # Last tier: guarded token containment. "CS50 Python" should find
        # "Harvard CS50's ... with Python – Full University Course", but only
        # when the identity tokens all appear, exactly one candidate
        # qualifies, and no stated provider disagrees. Anything weaker shows
        # the course again rather than guessing.
        declared_tokens = _title_tokens(course.title)
        if len(declared_tokens) < 2:
            continue
        candidates = [
            entry for entry in entries
            if declared_tokens <= _title_tokens(entry.title)
            and not _providers_disagree(course, entry)
        ]
        if len(candidates) == 1:
            matched.setdefault(candidates[0].resource_id, course.title)

    return matched


def _providers_disagree(course: DeclaredCourse, entry: CatalogueEntry) -> bool:
    declared = _norm_title(course.provider)
    known = _norm_title(entry.provider)
    return bool(declared and known and declared != known)


def build_suppressions(
    completed_resource_ids: Iterable[uuid.UUID],
    declared_matches: dict[uuid.UUID, str],
) -> dict[uuid.UUID, SuppressionReason]:
    """Merge both histories. Recorded completion wins — it is the stronger claim."""
    suppressed: dict[uuid.UUID, SuppressionReason] = {
        rid: "declared_completed" for rid in declared_matches
    }
    for rid in completed_resource_ids:
        suppressed[rid] = "completed_here"
    return suppressed
