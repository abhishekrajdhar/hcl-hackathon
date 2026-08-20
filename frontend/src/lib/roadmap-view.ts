// Rich, presentation-ready model for the personalized roadmap interface.
// Decoupled from the raw API schemas: built in `roadmap-derive.ts` from the
// live roadmap + recommendations, or supplied by the bundled `roadmap-demo`.
// Components depend only on these types.

import type { PathItemStatus } from "@/lib/types";

/** The four visual states the roadmap renders. `current` = backend in_progress. */
export type RoadmapState = "completed" | "current" | "available" | "locked";

export const STATE_LABEL: Record<RoadmapState, string> = {
  completed: "COMPLETED",
  current: "CURRENT",
  available: "AVAILABLE",
  locked: "LOCKED",
};

/** Map a backend path-item status onto a roadmap state. */
export function toRoadmapState(status: PathItemStatus | string): RoadmapState {
  switch (status) {
    case "completed":
    case "skipped":
      return "completed";
    case "in_progress":
      return "current";
    case "available":
      return "available";
    default:
      return "locked";
  }
}

export interface RoadmapResource {
  id: string;
  title: string;
  /** Roadmap slot: resource | assessment | project | review. */
  kind: string;
  /** Catalogue type: course | tutorial | project | video | article | assessment. */
  type: string;
  provider: string;
  description: string;
  url: string;
  estimatedMinutes: number;
  difficulty: number; // 1..5
  skills: string[];
  prerequisites: string[];
  /** Why this resource was recommended (recommendation explanation). */
  why: string;
  status: RoadmapState;
  isOptional: boolean;
}

export interface RoadmapAssessment {
  id: string;
  title: string;
  estimatedMinutes: number;
  passingPct: number; // 0..1
  status: RoadmapState;
}

export interface RoadmapProject {
  id: string;
  title: string;
  description: string;
  estimatedMinutes: number;
  skills: string[];
  status: RoadmapState;
}

export interface RoadmapMilestone {
  id: string;
  title: string;
  skill: string;
  state: RoadmapState;
  current: number; // 0..1
  required: number; // 0..1
  completionPct: number; // 0..100
  estimatedMinutes: number;
  completionCriteria: string;
  /** Skills that gate this milestone — shown when locked. */
  prerequisites: string[];
  requiredSkills: string[];
  resources: RoadmapResource[];
  assessment: RoadmapAssessment | null;
  project: RoadmapProject | null;
}

export interface RoadmapPhase {
  index: number;
  title: string;
  objective: string;
  isCapstone: boolean;
  state: RoadmapState;
  estimatedMinutes: number;
  completionPct: number; // 0..100
  milestones: RoadmapMilestone[];
}

export interface RoadmapView {
  goal: string;
  role: string;
  progressPct: number; // 0..100
  totalPlannedHours: number;
  phases: RoadmapPhase[];
}
