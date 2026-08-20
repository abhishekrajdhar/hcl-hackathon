// Bundled demo dataset matching the requested design target, so the dashboard
// renders the exact requested content out of the box (before/without a seeded
// backend account). Shape-identical to what `derive.ts` produces from the API.
import type {
  ActivityDatum,
  DashboardData,
  MilestoneDatum,
  PhaseDatum,
  RecommendationDatum,
} from "@/lib/dashboard-data";

const skills = [
  { name: "Python", slug: "python", current: 0.9, target: 0.9 },
  { name: "Statistics", slug: "statistics", current: 0.65, target: 0.8 },
  { name: "Machine Learning", slug: "machine-learning", current: 0.75, target: 0.85 },
  { name: "Deep Learning", slug: "deep-learning", current: 0.42, target: 0.8 },
  { name: "PyTorch", slug: "pytorch", current: 0.31, target: 0.7 },
  { name: "MLOps", slug: "mlops", current: 0.15, target: 0.6 },
];

const milestones: MilestoneDatum[] = [
  { phaseTitle: "Foundations", phaseIndex: 0, title: "Statistics", status: "completed", current: 0.65, required: 0.8, gap: 0.15, estimatedMinutes: 1500, resourceCount: 2, hasAssessment: true, isCapstone: false, completionCriteria: "Score 70% on the Statistics checkpoint." },
  { phaseTitle: "Machine Learning", phaseIndex: 1, title: "Machine Learning", status: "completed", current: 0.75, required: 0.85, gap: 0.1, estimatedMinutes: 3600, resourceCount: 2, hasAssessment: true, isCapstone: false, completionCriteria: "Pass the ML foundations assessment." },
  { phaseTitle: "Deep Learning", phaseIndex: 2, title: "Deep Learning", status: "in_progress", current: 0.42, required: 0.8, gap: 0.38, estimatedMinutes: 4800, resourceCount: 3, hasAssessment: true, isCapstone: false, completionCriteria: "Complete the DL course and score 70% on the checkpoint." },
  { phaseTitle: "Deep Learning", phaseIndex: 2, title: "PyTorch", status: "available", current: 0.31, required: 0.7, gap: 0.39, estimatedMinutes: 1200, resourceCount: 2, hasAssessment: true, isCapstone: false, completionCriteria: "Finish PyTorch Fundamentals and the checkpoint." },
  { phaseTitle: "Deep Learning", phaseIndex: 2, title: "CNNs", status: "locked", current: 0.1, required: 0.7, gap: 0.6, estimatedMinutes: 2400, resourceCount: 2, hasAssessment: true, isCapstone: false, completionCriteria: "Build a CNN image classifier." },
  { phaseTitle: "Production", phaseIndex: 3, title: "MLOps", status: "locked", current: 0.15, required: 0.6, gap: 0.45, estimatedMinutes: 2400, resourceCount: 2, hasAssessment: false, isCapstone: false, completionCriteria: "Deploy and monitor a model API." },
  { phaseTitle: "Capstone", phaseIndex: 4, title: "ML Engineering Capstone", status: "locked", current: 0, required: 1, gap: 1, estimatedMinutes: 1200, resourceCount: 1, hasAssessment: false, isCapstone: true, completionCriteria: "Ship an end-to-end ML system for your goal." },
];

const phases: PhaseDatum[] = [
  { index: 0, title: "Foundations", objective: "Statistics and math for ML.", isCapstone: false, estimatedMinutes: 1500, status: "done", milestones: milestones.filter((m) => m.phaseIndex === 0) },
  { index: 1, title: "Machine Learning", objective: "Core supervised & unsupervised ML.", isCapstone: false, estimatedMinutes: 3600, status: "done", milestones: milestones.filter((m) => m.phaseIndex === 1) },
  { index: 2, title: "Deep Learning", objective: "Neural networks, PyTorch and CNNs.", isCapstone: false, estimatedMinutes: 8400, status: "active", milestones: milestones.filter((m) => m.phaseIndex === 2) },
  { index: 3, title: "Production", objective: "Deploy and operate ML systems.", isCapstone: false, estimatedMinutes: 2400, status: "upcoming", milestones: milestones.filter((m) => m.phaseIndex === 3) },
  { index: 4, title: "Capstone", objective: "A portfolio-grade ML project.", isCapstone: true, estimatedMinutes: 1200, status: "upcoming", milestones: milestones.filter((m) => m.phaseIndex === 4) },
];

const recommendations: RecommendationDatum[] = [
  { id: "r1", title: "PyTorch 60-Minute Blitz", type: "tutorial", difficulty: 3, estimatedHours: 2, skill: "PyTorch", reason: "Targets your PyTorch gap (31% → 70%). You meet all prerequisites and it starts at your level.", url: "https://example.com/pytorch-blitz", provider: "PyTorch", isReady: true, score: 0.82, cta: "Start tutorial" },
  { id: "r2", title: "Deep Learning Specialization", type: "course", difficulty: 4, estimatedHours: 80, skill: "Deep Learning", reason: "Directly advances your current Deep Learning milestone from 42% toward the 80% your goal needs.", url: "https://example.com/dl-spec", provider: "Coursera", isReady: true, score: 0.79, cta: "Continue course" },
  { id: "r3", title: "Train an Image Classifier in PyTorch", type: "project", difficulty: 4, estimatedHours: 10, skill: "PyTorch", reason: "Hands-on practice that consolidates PyTorch and prepares you for the CNN milestone.", url: "https://example.com/pytorch-project", provider: "MockLabs", isReady: true, score: 0.74, cta: "Build project" },
  { id: "r4", title: "MLOps Zoomcamp", type: "course", difficulty: 4, estimatedHours: 40, skill: "MLOps", reason: "Recommended for your Production phase once Deep Learning is complete.", url: "https://example.com/mlops", provider: "MockAcademy", isReady: false, score: 0.61, cta: "Preview" },
];

const assessments = [
  { id: "a1", title: "Statistics checkpoint", percentage: 0.86, passed: true, submittedAt: "2026-07-20", mastery: "good_understanding" },
  { id: "a2", title: "ML Foundations checkpoint", percentage: 0.92, passed: true, submittedAt: "2026-08-02", mastery: "strong_mastery" },
  { id: "a3", title: "Deep Learning checkpoint", percentage: 0.58, passed: false, submittedAt: "2026-08-14", mastery: "partial_understanding" },
];

const activity: ActivityDatum[] = (() => {
  const out: ActivityDatum[] = [];
  const base = new Date("2026-08-18");
  const mins = [45, 60, 0, 90, 30, 75, 120, 60, 0, 40, 80, 50, 100, 70];
  for (let i = 13; i >= 0; i--) {
    const d = new Date(base);
    d.setDate(base.getDate() - i);
    out.push({
      date: d.toISOString().slice(0, 10),
      label: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      minutes: mins[13 - i],
    });
  }
  return out;
})();

export const demoData: DashboardData = {
  goal: "Become a Machine Learning Engineer",
  role: "Machine Learning Engineer",
  progressPct: 68,
  weeklyHours: 10,
  skills,
  phases,
  milestones,
  currentMilestone: "Deep Learning",
  nextAction: {
    title: "Complete PyTorch Fundamentals",
    kind: "resource",
    phase: "Deep Learning",
    milestone: "PyTorch",
    estimatedMinutes: 120,
  },
  recommendations,
  assessments,
  activity,
  stats: {
    skillsTracked: skills.length,
    itemsCompleted: 11,
    itemsTotal: 16,
    hoursSpent: 64,
    totalPlannedHours: 292,
    avgAssessment: 0.79,
  },
  isDemo: true,
};
