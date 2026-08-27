// The unified shape every dashboard component consumes. Built from API
// responses in `derive.ts` (or the bundled demo). Components depend on this,
// never on raw API schemas.
import type { PathItemStatus } from "@/lib/types";
import type { RoadmapView } from "@/lib/roadmap-view";

export interface SkillDatum {
  name: string;
  slug: string;
  current: number; // 0..1
  target: number; // 0..1
}

export interface MilestoneDatum {
  phaseTitle: string;
  phaseIndex: number;
  title: string;
  status: PathItemStatus;
  current: number;
  required: number;
  gap: number;
  estimatedMinutes: number;
  resourceCount: number;
  hasAssessment: boolean;
  isCapstone: boolean;
  completionCriteria: string;
}

export interface PhaseDatum {
  index: number;
  title: string;
  objective: string;
  isCapstone: boolean;
  estimatedMinutes: number;
  status: "done" | "active" | "upcoming";
  milestones: MilestoneDatum[];
}

export interface NextActionDatum {
  title: string;
  kind: string;
  phase: string;
  milestone: string;
  estimatedMinutes: number;
}

export interface RecommendationDatum {
  id: string;
  title: string;
  type: string;
  difficulty: number;
  estimatedHours: number;
  skill: string;
  reason: string;
  url: string;
  provider: string;
  isReady: boolean;
  score: number;
  cta: string;
}

export interface AssessmentDatum {
  id: string;
  title: string;
  percentage: number;
  passed: boolean;
  submittedAt: string | null;
  mastery: string;
}

export interface ActivityDatum {
  date: string; // ISO date
  label: string;
  minutes: number;
}

/** Zero-state placeholder for loading and error states. Deliberately empty —
 * a journey nobody took must never be dressed up as data. */
export function emptyDashboardData(): DashboardData {
  return {
    goal: "",
    role: "",
    progressPct: 0,
    weeklyHours: 0,
    skills: [],
    phases: [],
    milestones: [],
    roadmap: { pathId: "", goal: "", role: "", progressPct: 0, totalPlannedHours: 0, phases: [] },
    currentMilestone: "—",
    nextAction: null,
    recommendations: [],
    assessments: [],
    activity: [],
    pace: { label: "unknown", ratio: 0, sampleSize: 0, weeksRemaining: null },
    stats: {
      skillsTracked: 0,
      itemsCompleted: 0,
      itemsTotal: 0,
      hoursSpent: 0,
      totalPlannedHours: 0,
      avgAssessment: 0,
    },
    isDemo: false,
  };
}

export interface DashboardData {
  goal: string;
  role: string;
  progressPct: number; // 0..100
  weeklyHours: number;
  skills: SkillDatum[];
  phases: PhaseDatum[];
  milestones: MilestoneDatum[];
  /** Rich roadmap model for the personalized roadmap interface. */
  roadmap: RoadmapView;
  currentMilestone: string;
  nextAction: NextActionDatum | null;
  recommendations: RecommendationDatum[];
  assessments: AssessmentDatum[];
  activity: ActivityDatum[];
  /** Actual-vs-estimated tempo and the forecast it implies. */
  pace: {
    label: "faster" | "on_track" | "slower" | "unknown";
    ratio: number;
    sampleSize: number;
    weeksRemaining: number | null;
  };
  stats: {
    skillsTracked: number;
    itemsCompleted: number;
    itemsTotal: number;
    hoursSpent: number;
    totalPlannedHours: number;
    avgAssessment: number;
  };
  isDemo: boolean;
}
