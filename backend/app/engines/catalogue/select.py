"""Deterministic selection of learning videos from raw candidates.

The provider hands over whatever the internet returned; this decides what is
actually worth putting in front of a learner. Pure functions over dataclasses —
no DB, no clock, no model, no network — so the same candidates always yield the
same picks and the rules can be argued with in a test rather than in production.

The rules exist because raw search results are bad in specific, repeatable
ways: three-minute teasers titled like full courses, "roadmap to become an X"
career-advice videos that teach nothing, the same course re-uploaded by five
channels, and content in a language the learner did not ask for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from app.catalogue.base import VideoRecord

#: Anything shorter is a teaser or an announcement, not a lesson. Nine minutes
#: is deliberately generous — plenty of good single-concept explainers sit just
#: above it.
MIN_HOURS = 0.15
#: Beyond this a single item swamps a learner's entire weekly budget and the
#: roadmap's time estimate stops being useful.
MAX_HOURS = 30.0
#: Below this a candidate does not credibly cover the skill it was found for.
MIN_RELEVANCE = 0.5
#: Runtime at or above this reads as a course rather than a single video.
COURSE_HOURS = 1.0

#: Titles that describe a career rather than teach a subject. These rank highly
#: in search and teach nothing.
_NOISE_PATTERNS = (
    r"\broadmap\b",
    r"\bsalary\b",
    r"\bhow (much|do) .* (make|earn)\b",
    r"\bcareer (path|options|guide)\b",
    r"\bday in the life\b",
    r"\bshould you (learn|become)\b",
    r"\bcourse (announcement|launch)\b",
)
_NOISE = tuple(re.compile(p, re.IGNORECASE) for p in _NOISE_PATTERNS)

#: Words that carry no signal when matching a title against a skill name.
_STOPWORDS = frozenset({"and", "or", "the", "of", "for", "in", "to", "a", "an", "&"})


@dataclass(frozen=True, slots=True)
class Selection:
    """A chosen video, with the reasoning that chose it."""

    video: VideoRecord
    score: float
    resource_type: str  # "course" | "video"
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _terms(text: str) -> list[str]:
    """Meaningful lowercase words. Punctuation and stopwords dropped so
    "Data Structures & Algorithms" matches "data structures algorithms"."""
    words = re.findall(r"[a-z0-9+#]+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def relevance(title: str, skill_name: str, aliases: Sequence[str] = ()) -> float:
    """How much of the skill's vocabulary the title actually contains, in [0, 1].

    Matching is on whole words: a substring test would score "AI" against
    "snail" and "OS" against "closed". An alias that matches in full is worth
    the same as the skill name itself — "unity" is as good a signal for game
    engines as "game engines" is.
    """
    haystack = set(_terms(title))
    if not haystack:
        return 0.0

    best = 0.0
    for phrase in (skill_name, *aliases):
        needles = _terms(phrase)
        if not needles:
            continue
        hit = sum(1 for n in needles if n in haystack)
        best = max(best, hit / len(needles))
    return round(best, 4)


def _is_noise(title: str) -> bool:
    return any(p.search(title) for p in _NOISE)


def _length_fit(hours: float) -> float:
    """Preference for runtimes that fit a learning session, in [0, 1].

    A gentle curve rather than a cliff: an hour-long tutorial and a six-hour
    course are both fine, a 40-second clip and a 25-hour marathon are not.
    """
    if hours < MIN_HOURS or hours > MAX_HOURS:
        return 0.0
    if 0.5 <= hours <= 8.0:
        return 1.0
    if hours < 0.5:
        return 0.6
    return 0.7  # long but usable


#: Titles that declare their own language. When the provider reports no
#: language (the scraper never does), a title saying "in Hindi" is the only
#: signal available — and creators reliably advertise it, because it is a
#: selling point to the right audience.
_TITLE_LANGUAGE = re.compile(
    r"\bin (hindi|urdu|tamil|telugu|bengali|marathi|spanish|french|german|"
    r"portuguese|arabic|russian|japanese|chinese|korean|indonesian|vietnamese|turkish)\b"
    r"|[ऀ-ॿ؀-ۿ一-鿿぀-ヿ가-힯]",
    re.IGNORECASE,
)


def _language_ok(record: VideoRecord, want: str = "en") -> bool:
    """Unknown language passes. Only a *stated* mismatch is disqualifying —
    most providers report nothing, and rejecting on absence would empty the
    catalogue. A title that declares a non-English language (or is written in
    a non-Latin script) counts as stating it."""
    if record.language:
        return record.language.split("-")[0].lower() == want
    if want == "en" and _TITLE_LANGUAGE.search(record.title):
        return False
    return True


def score_candidate(
    record: VideoRecord, skill_name: str, aliases: Sequence[str] = (), *, language: str = "en"
) -> Selection | None:
    """Score one candidate, or None when it fails a hard rule."""
    if not record.is_available:
        return None
    if not _language_ok(record, language):
        return None
    if _is_noise(record.title):
        return None

    fit = _length_fit(record.duration_hours)
    if fit == 0.0:
        return None

    rel = relevance(record.title, skill_name, aliases)
    if rel < MIN_RELEVANCE:
        return None

    reasons = [f"title matches {int(rel * 100)}% of the skill's terms"]
    if record.duration_hours >= COURSE_HOURS:
        reasons.append(f"{record.duration_hours:.1f}h of material")
    if record.view_count:
        reasons.append(f"{record.view_count:,} views")

    # Relevance dominates: a perfectly-sized video about the wrong subject is
    # worse than an awkwardly-sized one about the right subject.
    score = round(0.7 * rel + 0.3 * fit, 4)
    return Selection(
        video=record,
        score=score,
        resource_type="course" if record.duration_hours >= COURSE_HOURS else "video",
        reasons=tuple(reasons),
    )


def select_videos(
    candidates: Sequence[VideoRecord],
    skill_name: str,
    aliases: Sequence[str] = (),
    *,
    limit: int = 2,
    exclude_ids: frozenset[str] = frozenset(),
    language: str = "en",
) -> list[Selection]:
    """The best `limit` candidates for a skill, best first.

    At most one pick per channel: search happily returns four parts of the same
    playlist, and a learner offered "Part 1" and "Part 2" as their two options
    for a skill has really been offered one.
    """
    scored: list[Selection] = []
    seen_ids: set[str] = set(exclude_ids)
    for record in candidates:
        if record.video_id in seen_ids:
            continue
        seen_ids.add(record.video_id)
        selection = score_candidate(record, skill_name, aliases, language=language)
        if selection is not None:
            scored.append(selection)

    # Stable ordering: score, then longer material, then id so ties never
    # depend on the order the provider happened to return.
    scored.sort(key=lambda s: (-s.score, -s.video.duration_hours, s.video.video_id))

    picked: list[Selection] = []
    channels: set[str] = set()
    for selection in scored:
        channel = selection.video.channel.strip().lower()
        if channel in channels:
            continue
        channels.add(channel)
        picked.append(selection)
        if len(picked) >= limit:
            break
    return picked


def teaching_band(difficulty: int) -> tuple[float, float]:
    """Where material of this difficulty takes a learner, on the 0-1 scale.

    Mirrors the band table the seed generator uses, so discovered resources and
    seeded ones describe their coverage the same way.
    """
    return {
        1: (0.0, 0.55),
        2: (0.0, 0.65),
        3: (0.2, 0.75),
        4: (0.4, 0.85),
        5: (0.55, 0.95),
    }.get(difficulty, (0.0, 0.65))
