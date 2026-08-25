// XP and level, derived rather than stored.
//
// A separate XP column would be one more thing that can disagree with the
// event log. These are pure functions of data the app already has, so the
// number can never drift from the work it represents.

import type { DashboardData } from "@/lib/dashboard-data";

/** What each kind of evidence is worth. */
export const XP_PER_ITEM = 100;
export const XP_PER_SKILL_POINT = 200; // × summed proficiency across tracked skills
export const XP_PER_ASSESSMENT_POINT = 300; // × average assessment score (0-1)

export function xpFromData(data: DashboardData): number {
  const fromItems = data.stats.itemsCompleted * XP_PER_ITEM;
  const fromSkills = data.skills.reduce((total, s) => total + s.current, 0) * XP_PER_SKILL_POINT;
  const fromAssessments = data.stats.avgAssessment * XP_PER_ASSESSMENT_POINT;
  return Math.round(fromItems + fromSkills + fromAssessments);
}

export interface Level {
  level: number;
  /** XP at which this level began. */
  startedAt: number;
  /** XP required for the next level. */
  nextAt: number;
  /** 0-1 progress through the current level. */
  progress: number;
}

/** Each level costs a little more than the last: 500, 600, 700, … */
const BASE = 500;
const STEP = 100;

export function levelFromData(xp: number): Level {
  let level = 1;
  let startedAt = 0;
  let cost = BASE;
  while (xp >= startedAt + cost) {
    startedAt += cost;
    cost += STEP;
    level += 1;
  }
  const nextAt = startedAt + cost;
  const span = nextAt - startedAt;
  return {
    level,
    startedAt,
    nextAt,
    progress: span > 0 ? Math.min(1, (xp - startedAt) / span) : 0,
  };
}
