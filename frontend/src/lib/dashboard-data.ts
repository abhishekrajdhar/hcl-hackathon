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
