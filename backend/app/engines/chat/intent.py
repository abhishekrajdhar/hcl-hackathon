"""Deterministic intent detection for the learning assistant.

Rule-based and pure: classifies a learner message into one intent and pulls out
the entities the tools need (a goal, a skill, a resource, a score, a query). No
model — the LLM only writes the final prose, never decides what application data
to fetch. Patterns are ordered most-specific first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum


class IntentKind(str, Enum):
    SET_GOAL = "set_goal"
    REPORT_SCORE = "report_score"
    REPORT_COMPLETION = "report_completion"
    EXPLAIN_RECOMMENDATION = "explain_recommendation"
    EXPLAIN_PREREQUISITE = "explain_prerequisite"
    GENERAL_QUESTION = "general_question"
    CAREER_DISCOVERY = "career_discovery"
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
    #: The second skill in a relationship question ("X ... for Y").
    related_skill_ref: str | None = None
    resource_ref: str | None = None
    score: float | None = None
    query: str | None = None
    raw: str = ""
    matched: list[str] = field(default_factory=list)
    #: Study time the learner mentioned, normalised to hours per week.
    weekly_hours: int | None = None
    #: Skills the learner claims to have already ("comfortable with Python").
    known_skills: list[str] = field(default_factory=list)
    #: What KIND of goal this is: career | internship | transition | skill.
    #: None when the message is not a goal at all.
    goal_type: str | None = None


# Learners phrase a goal many ways, and onboarding is the one turn where
# missing it costs the most — a goal that does not register leaves the learner
# with no profile and no roadmap. "become/be" alone was far too narrow; this
# also accepts learning, building, working in, moving into and mastering.
# Ordered alternatives, longest first, so "want to learn about X" does not
# match the shorter "want to learn" and capture "about X".
# --- goal intelligence -------------------------------------------------------
# The diagram's "Goal Intelligence" node: a goal is not just a string, it has a
# KIND, and the kind changes what the system should do next. Uncertainty is the
# important one — it routes to career discovery instead of the gap engine,
# which cannot plan toward "I don't know".
_UNCERTAIN_RE = re.compile(
    r"(?:i (?:don(?:'|\u2019)?t|do not) know what|not sure (?:what|which|where)|"
    r"unsure (?:what|which|about)|no idea what|help me (?:decide|choose|figure out|pick)|"
    r"can(?:'|\u2019)?t decide|what (?:career|role|path) (?:should|would|fits)|"
    r"which (?:career|role|path)|confused about (?:my )?(?:career|direction|path)|"
    r"explore (?:my )?(?:career )?options)",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(
    r"(?:switch(?:ing)? (?:from|careers?|to)|transition(?:ing)? (?:from|into|to)|"
    r"career change|move (?:from|out of) \w+|pivot(?:ing)? (?:from|to|into)|"
    r"coming from a|background in \w+ but)",
    re.IGNORECASE,
)
_INTERNSHIP_RE = re.compile(r"\bintern(?:ship)?s?\b", re.IGNORECASE)
#: Career-goal cue: the goal names a role rather than a topic.
_ROLE_WORD_RE = re.compile(
    r"\b(?:engineer|scientist|analyst|developer|architect|researcher|specialist)\b",
    re.IGNORECASE,
)


def classify_goal_type(text: str, goal_text: str | None) -> str | None:
    """The kind of goal a message expresses. Pure and order-sensitive:
    the more specific signals (internship, transition) win over the generic
    career/skill split, and a message with no goal has no kind."""
    if _INTERNSHIP_RE.search(text):
        return "internship"
    if _TRANSITION_RE.search(text):
        return "transition"
    if goal_text is None:
        return None
    return "career" if _ROLE_WORD_RE.search(goal_text) else "skill"


_GOAL_VERBS = (
    r"want to (?:become|be)|want to learn(?: about)?|want to build(?: with)?|"
    r"want to work (?:in|with|on)|want to get into|want to move into|"
    r"want to master|want to specialise in|want to specialize in|want a career in|"
    r"would like to (?:become|be|learn)|"
    r"goal is (?:to become|to be|to learn|)|"
    r"(?:'|\u2019)?d like to be(?:come)?|(?:'|\u2019)?m aiming to be(?:come)?|"
    r"help me (?:become|learn)|looking to (?:become|learn)|"
    # goal-with-a-kind phrasings: the goal follows an internship or a
    # from-clause, e.g. "switch from web development to machine learning"
    r"want an? internship in|looking for an? internship in|"
    r"want to switch (?:from [a-z ]+? )?(?:to|into)|"
    r"want to transition (?:from [a-z ]+? )?(?:to|into)|"
    r"switch(?:ing)? (?:from [a-z ]+? )?(?:to|into)|"
    r"transition(?:ing)? (?:from [a-z ]+? )?(?:to|into)|"
    r"pivot(?:ing)? (?:from [a-z ]+? )?(?:to|into)"
)
_GOAL_RE = re.compile(
    rf"(?:i\s+)?(?:{_GOAL_VERBS})\s+(?:an?\s+)?"
    r"(?P<goal>[a-z][a-z0-9 /+\-]{2,60}?)"
    r"(?:\.|,|;|!|\?|$| so | because | and i | but i | with about | with roughly )",
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
# --- "why do I need X (for Y)?" ----------------------------------------------
# Matched BEFORE the generic "why ..." branch, which otherwise swallows every
# question starting with the word and answers it as if it were about a
# recommendation. These are answerable straight from the prerequisite graph.
_PREREQ_WHY_RE = re.compile(
    r"why\s+(?:is|are|do i need|does)\s+(?P<skill>[a-z0-9 /+\-]{2,60}?)\s+"
    r"(?:important|necessary|required|needed|matter|useful|relevant)?\s*"
    r"(?:for|to|in|before)\s+(?P<related>[a-z0-9 /+\-]{2,60})",
    re.IGNORECASE,
)
_PREREQ_NEED_RE = re.compile(
    r"(?:do|will)\s+i\s+(?:really\s+)?need\s+(?P<skill>[a-z0-9 /+\-]{2,60}?)"
    r"(?:\s+(?:for|to|before)\s+(?P<related>[a-z0-9 /+\-]{2,60}))?(?:\.|,|;|!|\?|$)",
    re.IGNORECASE,
)
_PREREQ_RELATE_RE = re.compile(
    r"how\s+(?:does|do|is|are)\s+(?P<skill>[a-z0-9 /+\-]{2,60}?)\s+"
    r"(?:relate|related|connected|connect|lead)\s+to\s+(?P<related>[a-z0-9 /+\-]{2,60})",
    re.IGNORECASE,
)

# --- open subject-matter questions -------------------------------------------
# Not about the learner's own data at all — "what is X", "X vs Y", "explain X".
# Routed to a general-knowledge answer rather than a capability menu.
_GENERAL_Q_RE = re.compile(
    r"^\s*(?:what(?:'|\u2019)?s|what is|what are|explain|tell me about|difference between|"
    r"how does|how do|when should i use|which is better)\b",
    re.IGNORECASE,
)
_VERSUS_RE = re.compile(
    r"\b(?P<a>[a-z0-9+.#\-]{2,30})\s+(?:vs\.?|versus|or)\s+(?P<b>[a-z0-9+.#\-]{2,30})\s*\??\s*$",
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

# --- time budget ------------------------------------------------------------
# "an hour a day", "2 hours a day", "about 10 hours a week", "a couple of
# evenings a week". Everything is normalised to hours per WEEK, because that is
# the unit `learner_profiles.weekly_hours` stores and the path generator plans
# against. Spoken input is wordy, so the number may be a numeral or a word.
_WORD_NUMBERS: dict[str, float] = {
    "an": 1, "a": 1, "one": 1, "couple": 2, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "half an": 0.5, "half": 0.5,
}
_PER_WEEK = {"day": 7.0, "evening": 7.0, "night": 7.0, "week": 1.0, "weekend": 1.0}

_HOURS_RE = re.compile(
    r"(?:about|around|roughly|maybe|only|just)?\s*"
    r"(?P<qty>\d{1,3}(?:\.\d+)?|half an|half|an|a|one|couple(?:\s+of)?|two|three|four|five|"
    r"six|seven|eight|nine|ten)\s+"
    r"hours?\s*"
    r"(?:a|per|each|every)\s+(?P<unit>day|week|evening|night|weekend)",
    re.IGNORECASE,
)


def extract_weekly_hours(text: str) -> int | None:
    """Normalise a spoken time budget to whole hours per week.

    Returns None when nothing was said — never a guess. Rounds to the nearest
    hour and clamps to the profile's own 1..168 bound.
    """
    m = _HOURS_RE.search(text)
    if not m:
        return None
    raw_qty = " ".join(m.group("qty").lower().replace(" of", "").split())
    try:
        qty = float(raw_qty)
    except ValueError:
        qty = _WORD_NUMBERS.get(raw_qty, 0.0)
    if qty <= 0:
        return None
    per_week = _PER_WEEK.get(m.group("unit").lower(), 1.0)
    hours = round(qty * per_week)
    if hours < 1:
        return None
    return min(hours, 168)


# --- already-known skills ---------------------------------------------------
# "already comfortable with Python", "I know SQL and pandas", "I'm confident
# with linear algebra". Captures the phrase only; resolving it to a real skill
# id is the resolver's job, and an unresolvable claim is simply dropped.
_KNOWN_RE = re.compile(
    r"(?:already\s+)?(?:i(?:'|\u2019)?m\s+|i\s+am\s+|i\s+)?"
    r"(?:comfortable|confident|familiar|experienced|good|solid|strong|fine)\s+"
    r"(?:with|at|in|on)\s+(?P<skills>[a-z0-9 ,/+\-]{2,80}?)"
    r"(?:\.|;|!|\?|$|\band\b\s+i\b|\bbut\b|\bso\b)",
    re.IGNORECASE,
)
_KNOW_VERB_RE = re.compile(
    r"\bi\s+(?:already\s+)?know\s+(?P<skills>[a-z0-9 ,/+\-]{2,80}?)"
    r"(?:\.|;|!|\?|$|\band\b\s+i\b|\bbut\b|\bso\b)",
    re.IGNORECASE,
)
_SKILL_SPLIT_RE = re.compile(r"\s*(?:,|/|\band\b)\s*", re.IGNORECASE)
#: Words that survive the split but never name a skill.
_SKILL_STOPWORDS = {"the", "a", "an", "it", "that", "this", "some", "basics", "bit"}
#: A skill name is a noun phrase. Any of these means we caught a clause instead
#: — "I know that this is hard" is not a claim to know a skill called
#: "that this is hard".
_CLAUSE_WORDS = {
    "is", "are", "was", "were", "be", "been", "am", "will", "would", "can",
    "could", "should", "do", "does", "did", "have", "has", "had", "that",
    "this", "it", "there", "how", "what", "why", "when", "where", "you",
    "we", "they", "nothing", "anything", "much",
}
#: Longest plausible skill name ("natural language processing" is three).
_MAX_SKILL_WORDS = 4


def _looks_like_skill(name: str) -> bool:
    words = name.split()
    if not words or len(words) > _MAX_SKILL_WORDS:
        return False
    return not any(w in _CLAUSE_WORDS for w in words)


def extract_known_skills(text: str) -> list[str]:
    """Skill phrases the learner claims to already have. Order-preserving, deduped."""
    found: list[str] = []
    for pattern in (_KNOWN_RE, _KNOW_VERB_RE):
        for m in pattern.finditer(text):
            for part in _SKILL_SPLIT_RE.split(m.group("skills")):
                name = " ".join(part.split()).strip(" .,:;!?").lower()
                if not name or name in _SKILL_STOPWORDS or len(name) < 2:
                    continue
                if not _looks_like_skill(name):
                    continue
                if name not in found:
                    found.append(name)
    return found



def _clean(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split()).strip(" .,:;!?")
    return cleaned or None


def _classify(message: str) -> Intent:
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

    # 4a) why do I need X (for Y)? — answerable from the prerequisite graph
    for pattern in (_PREREQ_WHY_RE, _PREREQ_NEED_RE, _PREREQ_RELATE_RE):
        pm = pattern.search(text)
        if pm:
            groups = pm.groupdict()
            return Intent(
                IntentKind.EXPLAIN_PREREQUISITE,
                skill_ref=_clean(groups.get("skill")),
                related_skill_ref=_clean(groups.get("related")),
                raw=text,
                matched=["prerequisite_why"],
            )

    # 4b) why this recommendation
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

    # 12) an open question about the subject rather than about the learner
    if _GENERAL_Q_RE.search(text) or _VERSUS_RE.search(text) or low.rstrip("?").endswith(
        ("difference", "better")
    ):
        return Intent(IntentKind.GENERAL_QUESTION, query=_clean(text), raw=text,
                      matched=["general_question"])

    return Intent(IntentKind.UNKNOWN, raw=text)


def detect_intent(message: str) -> Intent:
    """Classify the message, then attach the facts that are orthogonal to it.

    A learner rarely says one thing at a time — "I want to be an ML engineer,
    I have an hour a day and I already know Python" is one goal, one time
    budget and one skill claim in a single breath, and that is even more true
    of speech than of typing. Classification picks the single intent; the time
    budget and skill claims ride along with whatever that intent turned out to
    be, so none of them is lost.
    """
    intent = _classify(message)
    # Uncertainty overrides a goal match: "I don't know what career fits me"
    # must reach discovery, not be mis-parsed as setting the goal "fits me".
    if intent.kind in (IntentKind.SET_GOAL, IntentKind.UNKNOWN, IntentKind.GENERAL_QUESTION) \
            and _UNCERTAIN_RE.search(message):
        intent = replace(intent, kind=IntentKind.CAREER_DISCOVERY, goal_text=None)
    return replace(
        intent,
        weekly_hours=extract_weekly_hours(message),
        known_skills=extract_known_skills(message),
        goal_type=classify_goal_type(message, intent.goal_text),
    )
