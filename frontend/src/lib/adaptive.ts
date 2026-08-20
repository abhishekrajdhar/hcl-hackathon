// Turn an adaptive-update result into (a) a learner-facing notification and
// (b) an in-place patch of the unified DashboardData so skill/roadmap bars
// animate from their old value to the new one immediately. In live mode the
// authoritative refresh still comes from re-reading the backend; the patch just
// makes the change visible instantly. In demo mode `simulateAdaptive` produces
// the same result shape locally so the whole loop is demonstrable offline.

import type { DashboardData, MilestoneDatum, SkillDatum } from "@/lib/dashboard-data";
import type {
  AdaptiveMilestoneRead,
  AdaptiveUpdateResponse,
  UpdatedSkillRead,
} from "@/lib/types";
import type {
  RoadmapMilestone,
  RoadmapPhase,
  RoadmapState,
  RoadmapView,
} from "@/lib/roadmap-view";
import { masteryFromPct } from "@/lib/derive";

export interface SkillDelta {
  name: string;
  before: number; // 0..1
  after: number; // 0..1
  mastery: string;
}

export interface AdaptiveNotice {
  title: string;
  body: string;
  deltas: SkillDelta[];
}

function masteryPhrase(mastery: string): string {
  if (mastery.startsWith("strong")) return "strong";
  if (mastery.startsWith("good")) return "solid";
  if (mastery.startsWith("partial")) return "developing";
  return "early";
}

function levelBand(p: number): UpdatedSkillRead["level_band"] {
  if (p >= 0.75) return "advanced";
  if (p >= 0.5) return "intermediate";
  if (p >= 0.3) return "foundational";
  return "remedial";
}

/** Compose the "Your roadmap has been updated." notification from the result. */
export function buildAdaptiveNotice(res: AdaptiveUpdateResponse): AdaptiveNotice {
  const deltas: SkillDelta[] = res.updated_skills.map((s) => ({
    name: s.skill_name ?? "Skill",
    before: s.previous_proficiency,
    after: s.new_proficiency,
    mastery: s.mastery_level,
  }));

  const top = [...res.updated_skills].sort((a, b) => b.delta - a.delta)[0];
  const unlocked = res.unlocked_milestones[0];
  const completed = res.completed_milestones[0];
  let body = res.next_recommended_action || "Your plan has been recalculated.";

  if (res.trigger === "assessment" && top) {
    body = `Based on your assessment result, you've demonstrated ${masteryPhrase(top.mastery_level)} ${top.skill_name ?? "skill"} fundamentals.`;
    if (unlocked) body += ` We've moved you to ${unlocked.title}.`;
    else if (res.next_recommended_action) body += ` ${res.next_recommended_action}`;
  } else if (res.trigger === "resource_completed") {
    if (completed) {
      body = `You completed the ${completed.title} milestone.`;
      body += unlocked ? ` Next up: ${unlocked.title}.` : ` ${res.next_recommended_action}`;
    }
  } else if (res.trigger === "resource_skipped") {
    body = `Skipped. ${res.next_recommended_action}`;
  }

  return { title: "Your roadmap has been updated.", body, deltas };
}

// ---- local patch ------------------------------------------------------------

const norm = (s: string) => s.trim().toLowerCase();

/** Apply an adaptive result to the in-memory dashboard for instant feedback. */
export function patchDashboardFromAdaptive(
  data: DashboardData,
  res: AdaptiveUpdateResponse,
): DashboardData {
  const newBySkill = new Map<string, number>();
  for (const s of res.updated_skills) {
    if (s.skill_name) newBySkill.set(norm(s.skill_name), s.new_proficiency);
  }
  const completedTitles = new Set(res.completed_milestones.map((m) => norm(m.title)));
  const unlockedTitles = new Set(res.unlocked_milestones.map((m) => norm(m.title)));

  const skills: SkillDatum[] = data.skills.map((sk) =>
    newBySkill.has(norm(sk.name)) ? { ...sk, current: newBySkill.get(norm(sk.name))! } : sk,
  );

  const patchMilestone = (m: RoadmapMilestone): RoadmapMilestone => {
    let next = m;
    const bumped = newBySkill.get(norm(m.skill)) ?? newBySkill.get(norm(m.title));
    if (bumped !== undefined) {
      const completionPct = m.required > 0 ? Math.min(100, Math.round((bumped / m.required) * 100)) : m.completionPct;
      next = { ...next, current: bumped, completionPct };
    }
    if (completedTitles.has(norm(m.title))) {
      next = { ...next, state: "completed", completionPct: 100 };
    } else if (unlockedTitles.has(norm(m.title)) && next.state === "locked") {
      next = { ...next, state: "available" };
    }
    return next;
  };

  const phases: RoadmapPhase[] = data.roadmap.phases.map((ph) => {
    const milestones = ph.milestones.map(patchMilestone);
    const state: RoadmapState = milestones.length
      ? milestones.some((m) => m.state === "current")
        ? "current"
        : milestones.every((m) => m.state === "completed")
          ? "completed"
          : milestones.some((m) => m.state === "available")
            ? "available"
            : "locked"
      : ph.state;
    const completionPct = milestones.length
      ? Math.round(milestones.reduce((a, m) => a + m.completionPct, 0) / milestones.length)
      : ph.completionPct;
    return { ...ph, milestones, state, completionPct };
  });

  const allMs = phases.flatMap((p) => p.milestones);
  const doneCount = allMs.filter((m) => m.state === "completed").length;
  const progressPct = allMs.length ? Math.round((doneCount / allMs.length) * 100) : data.progressPct;

  const roadmap: RoadmapView = { ...data.roadmap, phases, progressPct };

  // keep the flat MilestoneDatum list (SkillProgress/Milestones cards) in sync
  const milestones: MilestoneDatum[] = data.milestones.map((m) => {
    const bumped = newBySkill.get(norm(m.title));
    let next = bumped !== undefined ? { ...m, current: bumped } : m;
    if (completedTitles.has(norm(m.title))) next = { ...next, status: "completed" };
    else if (unlockedTitles.has(norm(m.title)) && next.status === "locked") next = { ...next, status: "available" };
    return next;
  });

  return { ...data, skills, roadmap, milestones, progressPct };
}

// ---- demo-mode simulation ---------------------------------------------------

export type SimAction =
  | { kind: "assessment"; skill: string; score: number }
  | { kind: "complete"; skill: string; resourceTitle: string }
  | { kind: "skip"; skill: string; resourceTitle: string };

function asMilestoneRead(m: RoadmapMilestone, phase: RoadmapPhase): AdaptiveMilestoneRead {
  return { skill_id: null, title: m.title, phase_title: phase.title, phase_index: phase.index };
}

/** The first still-locked milestone in reading order (what completion unlocks). */
function nextLocked(view: RoadmapView, excludeTitle: string): { m: RoadmapMilestone; p: RoadmapPhase } | null {
  for (const p of view.phases) {
    for (const m of p.milestones) {
      if (m.state === "locked" && norm(m.title) !== norm(excludeTitle)) return { m, p };
    }
  }
  return null;
}

function findMilestone(view: RoadmapView, skill: string): { m: RoadmapMilestone; p: RoadmapPhase } | null {
  for (const p of view.phases) {
    for (const m of p.milestones) {
      if (norm(m.skill) === norm(skill) || norm(m.title) === norm(skill)) return { m, p };
    }
  }
  return null;
}

/** Produce an AdaptiveUpdateResponse locally so demo mode exercises the full loop. */
export function simulateAdaptive(data: DashboardData, action: SimAction): AdaptiveUpdateResponse {
  const view = data.roadmap;
  const found = findMilestone(view, action.skill);
  const base: AdaptiveUpdateResponse = {
    user_id: "demo",
    trigger: "explicit",
    updated_skills: [],
    completed_milestones: [],
    unlocked_milestones: [],
    removed_resources: [],
    newly_recommended_resources: [],
    next_recommended_action: "Keep going — your plan is on track.",
  };
  if (!found) return base;
  const { m, p } = found;

  if (action.kind === "skip") {
    return {
      ...base,
      trigger: "resource_skipped",
      next_recommended_action: `Skipped "${action.resourceTitle}". Moving on to the next resource in ${m.title}.`,
    };
  }

  const before = m.current;
  const after =
    action.kind === "assessment" ? action.score : Math.min(1, Math.max(before + 0.18, before));
  const passed = after >= m.required;
  const updated: UpdatedSkillRead = {
    skill_id: "demo",
    skill_name: m.skill,
    previous_proficiency: before,
    new_proficiency: after,
    delta: after - before,
    mastery_level: masteryFromPct(after),
    level_band: levelBand(after),
  };

  const unlocked = passed ? nextLocked(view, m.title) : null;
  return {
    ...base,
    trigger: action.kind === "assessment" ? "assessment" : "resource_completed",
    updated_skills: [updated],
    completed_milestones: passed ? [asMilestoneRead(m, p)] : [],
    unlocked_milestones: unlocked ? [asMilestoneRead(unlocked.m, unlocked.p)] : [],
    next_recommended_action: unlocked
      ? `Start ${unlocked.m.title} in the ${unlocked.p.title} phase.`
      : `Great progress on ${m.title} — keep building toward your goal.`,
  };
}
