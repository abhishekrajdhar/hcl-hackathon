"""Deterministic intent detection for the learning assistant.

Rule-based and pure: classifies a learner message into one intent and pulls out
the entities the tools need (a goal, a skill, a resource, a score, a query). No
model — the LLM only writes the final prose, never decides what application data
to fetch. Patterns are ordered most-specific first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class IntentKind(str, Enum):
    SET_GOAL = "set_goal"
    REPORT_SCORE = "report_score"
    REPORT_COMPLETION = "report_completion"
    EXPLAIN_RECOMMENDATION = "explain_recommendation"
    CAN_I_SKIP = "can_i_skip"
    NEXT_ACTION = "next_action"
    WEEKLY_PLAN = "weekly_plan"
    SHOW_PATH = "show_path"
    SHOW_GAPS = "show_gaps"
    SHOW_RECOMMENDATIONS = "show_recommendations"
    SHOW_PROGRESS = "show_progress"
    SHOW_PROFILE = "show_profile"
    SEARCH_RESOURCES = "search_resources"
    GREETING = "greeting"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Intent:
    kind: IntentKind
    goal_text: str | None = None
    skill_ref: str | None = None
    resource_ref: str | None = None
    score: float | None = None
    query: str | None = None
    raw: str = ""
    matched: list[str] = field(default_factory=list)


_GOAL_RE = re.compile(
    r"(?:i want to (?:become|be)|my goal is (?:to become|to be|)|i(?:'|')?d like to be(?:come)?|"
    r"become)\s+(?:an?\s+)?(?P<goal>[a-z][a-z0-9 /+\-]{2,60}?)(?:\.|,|;|!|\?|$| so | because )",
    re.IGNORECASE,
)
_SCORE_RE = re.compile(r"(?:scored|got|made)\s+(?P<score>\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE)
_SCORE_RE2 = re.compile(r"(?P<score>\d{1,3}(?:\.\d+)?)\s*%\s+on", re.IGNORECASE)
_COMPLETION_RE = re.compile(
    r"i(?:'|')?ve\s+|i\s+(?:just\s+)?(?:completed|finished|did|done)\s+(?:the\s+)?(?P<res>.+?)"
    r"(?:\s+course|\s+resource|\s+tutorial|\.|,|;|!|$)",
    re.IGNORECASE,
)
_COMPLETION_SIMPLE = re.compile(
    r"i\s+(?:just\s+)?(?:completed|finished)\s+(?:the\s+)?(?P<res>.+?)(?:\.|,|;|!|$)",
    re.IGNORECASE,
)
_WHY_RE = re.compile(
    r"why\s+(?:are you|do you|would you|did you)?\s*(?:recommend(?:ing)?|suggest(?:ing)?)?\s*"
    r"(?:the\s+)?(?P<res>[a-z0-9 /+\-]{2,60})",
    re.IGNORECASE,
)
_SKIP_RE = re.compile(
    r"(?:can i|should i|do i (?:have to|need to))\s+skip\s+(?:the\s+)?(?P<skill>[a-z0-9 /+\-]{2,60})",
    re.IGNORECASE,
)
_SEARCH_RE = re.compile(
    r"(?:find|search|show me|look for|any)\s+(?:me\s+)?(?:some\s+)?(?:courses?|resources?|"
    r"tutorials?|videos?|material)\s+(?:on|about|for)\s+(?P<q>.+?)(?:\.|,|;|!|\?|$)",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(r"^\s*(?:hi|hello|hey|yo|greetings)\b", re.IGNORECASE)


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split()).strip(" .,:;!?")
    return cleaned or None


def detect_intent(message: str) -> Intent:
    text = message.strip()
    low = text.lower()

    # 1) report an assessment score
    m = _SCORE_RE.search(text) or _SCORE_RE2.search(text)
    if m:
        return Intent(IntentKind.REPORT_SCORE, score=float(m.group("score")) / 100.0, raw=text,
                      matched=["score"])

    # 2) report a completed resource
    if re.search(r"\bi\s+(?:just\s+)?(?:completed|finished)\b", low):
        cm = _COMPLETION_SIMPLE.search(text)
        return Intent(
            IntentKind.REPORT_COMPLETION,
            resource_ref=_clean(cm.group("res")) if cm else None,
            raw=text, matched=["completed"],
        )

    # 3) set a goal
    gm = _GOAL_RE.search(text)
    if gm:
        return Intent(IntentKind.SET_GOAL, goal_text=_clean(gm.group("goal")), raw=text,
                      matched=["goal"])

    # 4) why this recommendation
    if low.startswith("why") or "why are you recommend" in low or "why recommend" in low:
        wm = _WHY_RE.search(text)
        return Intent(IntentKind.EXPLAIN_RECOMMENDATION,
                      resource_ref=_clean(wm.group("res")) if wm else None, raw=text,
                      matched=["why"])

    # 5) can I skip X
    sm = _SKIP_RE.search(text)
    if sm:
        return Intent(IntentKind.CAN_I_SKIP, skill_ref=_clean(sm.group("skill")), raw=text,
                      matched=["skip"])

    # 6) search resources
    qm = _SEARCH_RE.search(text)
    if qm:
        return Intent(IntentKind.SEARCH_RESOURCES, query=_clean(qm.group("q")), raw=text,
                      matched=["search"])

    # 7) weekly plan
    if "this week" in low or "for the week" in low or "weekly" in low:
        return Intent(IntentKind.WEEKLY_PLAN, raw=text, matched=["week"])

    # 8) what next
    if re.search(r"\b(?:what(?:'|')?s next|what should i (?:learn|do|study) next|what next|next step)\b", low):
        return Intent(IntentKind.NEXT_ACTION, raw=text, matched=["next"])

    # 9) show-* queries
    if any(k in low for k in ("my roadmap", "my learning path", "my path", "my plan", "roadmap")):
        return Intent(IntentKind.SHOW_PATH, raw=text, matched=["path"])
    if any(k in low for k in ("skill gap", "gaps", "what am i missing", "what do i need to learn")):
        return Intent(IntentKind.SHOW_GAPS, raw=text, matched=["gaps"])
    if any(k in low for k in ("recommend", "what should i study", "what should i learn", "suggest")):
        return Intent(IntentKind.SHOW_RECOMMENDATIONS, raw=text, matched=["recommendations"])
    if any(k in low for k in ("my progress", "how am i doing", "how far", "progress")):
        return Intent(IntentKind.SHOW_PROGRESS, raw=text, matched=["progress"])
    if any(k in low for k in ("my profile", "about me", "what do you know about me", "my skills")):
        return Intent(IntentKind.SHOW_PROFILE, raw=text, matched=["profile"])

    if _GREETING_RE.match(text):
        return Intent(IntentKind.GREETING, raw=text, matched=["greeting"])

    return Intent(IntentKind.UNKNOWN, raw=text)
