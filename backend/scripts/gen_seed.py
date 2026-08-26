"""Generate the catalogue seed from VERIFIED YouTube metadata + in-app items."""
import json, re

import sys
sys.path.insert(0, ".")
from app.db.seeds.skill_graph import EDGES

cat = json.load(open("/tmp/catalogue.json"))
inapp = json.load(open("/tmp/inapp.json"))

# Hard prerequisites straight from the skill graph, so the catalogue and the
# DAG cannot disagree about what gates what.
HARD_PREREQS: dict[str, list[str]] = {}
for e in EDGES:
    if e.relationship_type == "hard_prerequisite":
        HARD_PREREQS.setdefault(e.source, []).append(e.prerequisite)

#: How proficient a learner must be in a prerequisite before a resource at this
#: difficulty is a reasonable next step. Intro material (1-2) is never gated —
#: gating a beginner course behind prerequisites is how a learner gets stuck.
GATE_LEVEL = {3: 0.35, 4: 0.45, 5: 0.55}


def prereqs_for(primary: str, difficulty: int) -> list[tuple[str, float]]:
    level = GATE_LEVEL.get(difficulty)
    if level is None:
        return []
    return [(slug, level) for slug in sorted(HARD_PREREQS.get(primary, []))[:3]]

def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def band(diff):
    """Where a resource takes a learner, from its difficulty."""
    return {1: (0.0, 0.55), 2: (0.0, 0.65), 3: (0.2, 0.75), 4: (0.4, 0.85), 5: (0.55, 0.95)}[diff]

lines = []
lines.append('"""Declarative seed data for the learning-resource catalogue.')
lines.append("")
lines.append("Pure data — no I/O. `seed.py` upserts these. Resources reference skills by")
lines.append("slug (resolved to ids by the loader), so the catalogue stays decoupled from")
lines.append("skill uuids.")
lines.append("")
lines.append("The video catalogue is REAL: every title, channel, runtime and id below was")
lines.append("read from YouTube's oEmbed endpoint and watch page rather than written by")
lines.append("hand, so `estimated_hours` is the actual runtime and the URL resolves. Any")
lines.append("candidate that failed verification was dropped rather than guessed at.")
lines.append("Regenerate with `scripts/refresh_catalogue.py`.")
lines.append("")
lines.append("Projects and assessments are completed INSIDE the app, so they point at the")
lines.append("dashboard rather than an external page.")
lines.append("")
lines.append("difficulty: 1..5. `teaches` bands and prerequisite `min_proficiency` are on")
lines.append("the same 0..1 proficiency scale the learner profile uses.")
lines.append('"""')
lines.append("")
lines.append("from __future__ import annotations")
lines.append("")
lines.append("from dataclasses import dataclass, field")
lines.append("")
lines.append("")
lines.append("@dataclass(frozen=True)")
lines.append("class TeachSeed:")
lines.append("    skill: str  # skill slug")
lines.append("    level_from: float = 0.0")
lines.append("    level_to: float = 0.6")
lines.append("    is_primary: bool = False")
lines.append("")
lines.append("")
lines.append("@dataclass(frozen=True)")
lines.append("class ResourceSeed:")
lines.append("    external_id: str")
lines.append("    title: str")
lines.append("    resource_type: str")
lines.append("    provider: str")
lines.append("    url: str")
lines.append("    difficulty: int")
lines.append("    estimated_hours: float")
lines.append("    description: str")
lines.append("    teaches: tuple[TeachSeed, ...]")
lines.append("    prerequisites: tuple[tuple[str, float], ...] = ()")
lines.append("    quality_score: float | None = None")
lines.append("    rating: float | None = None")
lines.append("    rating_count: int = 0")
lines.append("    modality: str = \"mixed\"")
lines.append("    metadata: dict = field(default_factory=dict)")
lines.append("")
lines.append("")
lines.append("def _t(skill: str, lo: float = 0.0, hi: float = 0.6, primary: bool = True) -> TeachSeed:")
lines.append("    return TeachSeed(skill=skill, level_from=lo, level_to=hi, is_primary=primary)")
lines.append("")
lines.append("")
lines.append("#: Watched on YouTube; `external_id` is the video id.")
lines.append("_YT = \"https://www.youtube.com/watch?v=\"")
lines.append("")
lines.append("RESOURCES: tuple[ResourceSeed, ...] = (")
lines.append("    # ---------------------------------------------------- video catalogue")

for r in cat:
    lo, hi = band(r["difficulty"])
    teaches = [f'_t("{r["primary"]}", {lo}, {hi})']
    for e in r["extra"]:
        teaches.append(f'_t("{e}", {lo}, {round(hi - 0.15, 2)}, False)')
    desc = f'{r["type"].capitalize()} by {r["channel"]} on YouTube.'
    pr = prereqs_for(r["primary"], r["difficulty"])
    pr_src = ", ".join(f'("{sl}", {lv})' for sl, lv in pr)
    pr_src = f"({pr_src},)" if pr_src else "()"
    lines.append("    ResourceSeed(")
    lines.append(f'        "{r["id"]}", "{esc(r["title"])}",')
    lines.append(f'        "{r["type"]}", "{esc(r["channel"])}", _YT + "{r["id"]}",')
    lines.append(f'        {r["difficulty"]}, {r["hours"]},')
    lines.append(f'        "{esc(desc)}",')
    lines.append(f'        ({", ".join(teaches)},),')
    lines.append(f'        {pr_src},')
    lines.append(f'        modality="video",')
    lines.append("    ),")

lines.append("    # ------------------------------------- projects & checkpoints (in-app)")
for r in inapp:
    teaches = ", ".join(
        f'_t("{s}", {lo}, {hi}, {p})' for s, lo, hi, p in r["teaches"]
    )
    prereqs = ", ".join(f'("{s}", {lvl})' for s, lvl in r["prereqs"])
    prereqs = f"({prereqs},)" if prereqs else "()"
    q = r["quality"] if r["quality"] is not None else "None"
    lines.append("    ResourceSeed(")
    lines.append(f'        "{r["external_id"]}", "{esc(r["title"])}",')
    lines.append(f'        "{r["type"]}", "Pathwise", "/dashboard#roadmap",')
    lines.append(f'        {r["difficulty"]}, {r["hours"]},')
    lines.append(f'        "{esc(r["desc"])}",')
    lines.append(f'        ({teaches},),')
    lines.append(f'        {prereqs}, {q},')
    lines.append(f'        modality="{r["modality"]}",')
    lines.append("    ),")
lines.append(")")
lines.append("")

open("app/db/seeds/resources.py","w").write("\n".join(lines))
print(f"wrote {len(cat)} videos + {len(inapp)} in-app items = {len(cat)+len(inapp)} resources")
