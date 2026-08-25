"""Deterministic, grounded response composition for the assistant.

Turns an intent plus the tool results into a coach-style reply built ONLY from
what the tools returned. If a tool reports data is unavailable, the reply says so
rather than inventing anything. This is the grounded baseline; an LLM may later
rephrase it, but never adds facts.
"""

from __future__ import annotations

from app.engines.chat.intent import Intent, IntentKind
from app.services.chat_tools import ToolResult


def _by_name(results: list[ToolResult]) -> dict[str, ToolResult]:
    return {r.name: r for r in results}


def compose_reply(intent: Intent, results: list[ToolResult]) -> str:
    tools = _by_name(results)

    if intent.kind == IntentKind.GREETING:
        profile = tools.get("get_learner_profile")
        if profile and profile.available:
            role = profile.data.get("target_role") or profile.data.get("goal") or "your goal"
            return (
                f"Hi! I'm your learning coach. You're working toward {role}. "
                "Ask me what to learn next, why something is recommended, or tell me what you finished."
            )
        return (
            "Hi! I'm your learning coach. Tell me the role you want to grow into and I'll help you "
            "get there step by step."
        )

    if intent.kind == IntentKind.SET_GOAL:
        profile = tools.get("get_learner_profile")
        goal = intent.goal_text or (profile.data.get("target_role") if profile else None)
        return _compose_goal_reply(intent, goal, tools.get("get_goal_prerequisites"))

    if intent.kind == IntentKind.EXPLAIN_PREREQUISITE:
        rel = tools.get("explain_skill_relationship")
        if not (rel and rel.available):
            return rel.summary if rel else "I don't know that skill."
        return _compose_prerequisite_reply(rel)

    if intent.kind == IntentKind.GENERAL_QUESTION:
        # Answered by the LLM in the service when one is configured. This is
        # the fallback for the mock provider: point at the catalogue rather
        # than pretend to know.
        search = tools.get("search_resources")
        if search and search.available and search.data.get("resources"):
            titles = ", ".join(r["title"] for r in search.data["resources"][:3])
            return (
                "That's a general question rather than one about your path, and I don't "
                f"have a model configured to answer it. The closest material I have is: {titles}."
            )
        return (
            "That's a general question rather than one about your path, and I don't have a "
            "model configured to answer it. I can explain how skills depend on each other "
            "though — try \"why do I need linear algebra for machine learning?\""
        )

    if intent.kind == IntentKind.NEXT_ACTION:
        return _relay(tools.get("get_next_action"),
                      unavailable="You don't have an active learning path yet. "
                                  "Tell me your goal and I'll build one.")

    if intent.kind == IntentKind.WEEKLY_PLAN:
        path = tools.get("get_current_learning_path")
        progress = tools.get("get_progress")
        if not (path and path.available):
            return ("You don't have an active path yet, so I can't plan your week. "
                    "Set a goal first and I'll lay out a schedule.")
        first = next((ph for ph in path.data["phases"] if not ph["is_capstone"]), None)
        milestones = ", ".join(first["milestones"][:2]) if first else "your current milestone"
        done = progress.data.get("completion_pct", 0) if progress else 0
        return (
            f"This week, focus on {milestones} in the '{first['phase'] if first else 'current'}' phase. "
            f"You're {done:.0f}% through your roadmap — keep the momentum going."
        )

    if intent.kind == IntentKind.EXPLAIN_RECOMMENDATION:
        recs = tools.get("get_recommendations")
        target = (intent.resource_ref or "").lower()
        if not (recs and recs.available):
            return ("I don't have any active recommendations to explain yet. "
                    "Generate recommendations or a learning path first.")
        match = next(
            (r for r in recs.data["recommendations"]
             if r["title"] and target and target in r["title"].lower()),
            None,
        )
        if match is None:
            listed = ", ".join(r["title"] for r in recs.data["recommendations"][:3] if r["title"])
            return (
                f"I'm not currently recommending '{intent.resource_ref}'. "
                f"My current recommendations are: {listed}."
            )
        return f"I recommend '{match['title']}' because: {match['reason'] or 'it best fits your current gaps.'}"

    if intent.kind == IntentKind.CAN_I_SKIP:
        gaps = tools.get("get_skill_gaps")
        skill = (intent.skill_ref or "").lower()
        if not (gaps and gaps.available):
            return ("I can't check that without an active learning path. "
                    "Set a goal and I'll tell you what's safe to skip.")
        match = next((g for g in gaps.data["gaps"] if skill in g["skill"].lower()), None)
        if match is None:
            return (
                f"'{intent.skill_ref}' isn't a gap in your current path, so yes — you can skip it."
            )
        return (
            f"I wouldn't skip {match['skill']} yet: you're at "
            f"{match['current_level'] * 100:.0f}% and your goal needs "
            f"{match['required_level'] * 100:.0f}%. It's a prerequisite for later milestones."
        )

    if intent.kind == IntentKind.SHOW_PATH:
        path = tools.get("get_current_learning_path")
        if not (path and path.available):
            return "You don't have an active learning path yet. Tell me your goal to generate one."
        phases = " → ".join(p["phase"] for p in path.data["phases"])
        return f"Your roadmap ({path.data['total_hours']}h): {phases}."

    if intent.kind == IntentKind.SHOW_GAPS:
        gaps = tools.get("get_skill_gaps")
        if not (gaps and gaps.available):
            return gaps.summary if gaps else "No skill gaps are available yet."
        lines = [
            f"{g['skill']} ({g['current_level'] * 100:.0f}% → {g['required_level'] * 100:.0f}%)"
            for g in gaps.data["gaps"][:6]
        ]
        return "Your current skill gaps: " + "; ".join(lines) + "."

    if intent.kind == IntentKind.SHOW_RECOMMENDATIONS:
        return _relay(tools.get("get_recommendations"),
                      unavailable="You have no recommendations yet. "
                                  "Generate a learning path and I'll suggest resources.",
                      render=lambda r: "I recommend: " + ", ".join(
                          x["title"] for x in r.data["recommendations"] if x["title"]) + ".")

    if intent.kind == IntentKind.SHOW_PROGRESS:
        return _relay(tools.get("get_progress"))

    if intent.kind == IntentKind.SHOW_PROFILE:
        return _relay(tools.get("get_learner_profile"),
                      unavailable="I don't have a profile for you yet. "
                                  "Tell me your goal and current skills to get started.")

    if intent.kind == IntentKind.SEARCH_RESOURCES:
        search = tools.get("search_resources")
        if not (search and search.available) or not search.data.get("results"):
            return f"I couldn't find catalogue resources for '{intent.query}'."
        titles = ", ".join(r["title"] for r in search.data["results"][:5])
        return f"Here are resources on '{intent.query}': {titles}."

    if intent.kind in (IntentKind.REPORT_SCORE, IntentKind.REPORT_COMPLETION):
        update = tools.get("update_learning_progress")
        if not (update and update.available):
            return update.summary if update else "I couldn't record that — can you rephrase?"
        parts = [update.summary]
        if update.data.get("unlocked_milestones"):
            parts.append("Unlocked: " + ", ".join(update.data["unlocked_milestones"]) + ".")
        if update.data.get("newly_recommended"):
            parts.append("I've added: " + ", ".join(update.data["newly_recommended"]) + ".")
        if update.data.get("next_action"):
            parts.append(update.data["next_action"])
        return " ".join(parts)

    # UNKNOWN
    return (
        "I can help you set a goal, show your roadmap and skill gaps, recommend what to learn next, "
        "explain recommendations, search for resources, and record what you've completed. "
        "What would you like to do?"
    )




def _compose_prerequisite_reply(rel: ToolResult) -> str:
    """Explain a dependency straight from the graph — no opinion involved."""
    data = rel.data
    skill = data.get("skill", "that skill")
    target = data.get("target")

    if not target:
        unlocks = data.get("unlocks", [])
        if not unlocks:
            return f"Nothing in the catalogue lists {skill} as a prerequisite."
        return (
            f"{skill} is a prerequisite for {_join(unlocks[:4])}"
            f"{f' and {len(unlocks) - 4} more' if len(unlocks) > 4 else ''}."
        )

    relation = data.get("relation")
    if relation == "same":
        return f"{skill} and {target} are the same skill."
    if relation == "direct":
        return (
            f"{skill} is a direct prerequisite of {target} — the graph gates {target} "
            f"behind it, so it comes first on any route to {target}."
        )
    if relation == "transitive":
        chain = data.get("chain") or [skill, target]
        return (
            f"{skill} is an indirect prerequisite of {target}: {' → '.join(chain)}. "
            f"It is not required immediately, but {target} is unreachable without it."
        )
    direct = data.get("target_direct_prerequisites", [])
    tail = f" {target} depends on {_join(direct[:3])} instead." if direct else ""
    return f"{skill} is not a prerequisite of {target}.{tail}"


def _compose_goal_reply(
    intent: Intent, goal: str | None, prereqs: ToolResult | None
) -> str:
    """The onboarding turn: confirm the goal, reflect back what else was said,
    propose a starting point, and ask ONE thing we genuinely do not know.

    A learner states a goal, a time budget and their existing skills in one
    breath. Acknowledging only the goal makes the coach feel deaf, and it also
    wastes what it was told — so each fact that was actually extracted gets a
    clause, and facts that were NOT stated get no clause at all rather than a
    guess.

    The closing question is asked only when a tool confirmed a real unmet
    prerequisite. If the goal did not resolve to a catalogue skill, the coach
    says what it can do next instead of inventing something to ask about.
    """
    parts: list[str] = [f"Got it — your goal is to become a {goal}." if goal else "Got it."]

    if intent.known_skills:
        # Echo the catalogue's spelling ("SQL", not "sql") when the claim
        # resolved to a real skill; otherwise repeat the learner's own words.
        claimed = [_canonical(name, prereqs) for name in intent.known_skills]
        parts.append(
            f"Since you're already comfortable with {_join(claimed)}, "
            f"I won't start you on beginner {claimed[0]} material."
        )

    unknown = list(prereqs.data.get("unknown", [])) if prereqs and prereqs.available else []
    if intent.weekly_hours:
        budget = f"With roughly {intent.weekly_hours} hours a week"
        if unknown:
            starting = _join([u["skill"] for u in unknown[:2]])
            parts.append(f"{budget}, I'd suggest starting with {starting}.")
        else:
            parts.append(f"{budget}, I'll pace the roadmap to fit.")
    elif unknown:
        starting = _join([u["skill"] for u in unknown[:2]])
        parts.append(f"I'd suggest starting with {starting}.")

    if unknown:
        parts.append(
            "Before I finalise the roadmap, can I ask how comfortable you are "
            f"with {unknown[0]['skill']}?"
        )
    else:
        parts.append(
            "Ask me to generate your learning path, or say 'what should I learn next?'."
        )
    return " ".join(parts)


def _canonical(name: str, prereqs: ToolResult | None) -> str:
    """The catalogue's name for a claimed skill, or the claim unchanged."""
    if prereqs and prereqs.available:
        for bucket in ("met", "unknown"):
            for entry in prereqs.data.get(bucket, []):
                if entry.get("skill", "").lower() == name.lower():
                    return str(entry["skill"])
    return name


def _join(items: list[str]) -> str:
    """'a', 'a and b', 'a, b and c' — spoken aloud, an Oxford comma reads oddly."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _relay(result: ToolResult | None, *, unavailable: str | None = None, render=None) -> str:  # type: ignore[no-untyped-def]
    if result is None:
        return unavailable or "That information isn't available right now."
    if not result.available:
        return unavailable or result.summary
    if render is not None:
        return render(result)
    return result.summary
