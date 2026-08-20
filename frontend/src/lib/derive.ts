// Transform raw API responses into the unified DashboardData the components use.
import type {
  ActivityDatum,
  DashboardData,
  MilestoneDatum,
  PhaseDatum,
  RecommendationDatum,
} from "@/lib/dashboard-data";
import type {
  FullLearnerProfile,
  LearningPathRoadmap,
  PathItemStatus,
  ProgressEvent,
  ProgressSummary,
  RecommendationResponse,
} from "@/lib/types";
import { buildRoadmapView } from "@/lib/roadmap-derive";
import { demoRoadmap } from "@/lib/roadmap-demo";

export function masteryFromPct(p: number): string {
  if (p >= 0.9) return "strong_mastery";
  if (p >= 0.7) return "good_understanding";
  if (p >= 0.5) return "partial_understanding";
  return "requires_remediation";
}

const ctaForType = (type: string): string =>
  ({
    course: "Continue course",
    tutorial: "Start tutorial",
    project: "Build project",
    video: "Watch",
    book: "Read",
    article: "Read",
    assessment: "Take assessment",
    documentation: "Open docs",
  }[type] ?? "Start");

function phaseStatus(ms: MilestoneDatum[]): PhaseDatum["status"] {
  if (ms.length && ms.every((m) => m.status === "completed" || m.status === "skipped")) return "done";
  if (ms.some((m) => m.status === "in_progress" || m.status === "available")) return "active";
  return "upcoming";
}

export function buildDashboardData(input: {
  profile: FullLearnerProfile;
  roadmap: LearningPathRoadmap | null;
  progress: ProgressSummary | null;
  recommendations: RecommendationResponse | null;
  events: ProgressEvent[];
}): DashboardData {
  const { profile, roadmap, progress, recommendations, events } = input;

  // required level per skill from the roadmap (fallback to target_proficiency).
  const requiredBySlug = new Map<string, number>();
  roadmap?.phases.forEach((ph) =>
    ph.milestones.forEach((m) => {
      if (m.skill_slug) requiredBySlug.set(m.skill_slug, m.required_level);
    }),
  );

  const skills = [...profile.skills]
    .sort((a, b) => b.proficiency - a.proficiency)
    .slice(0, 8)
    .map((s) => ({
      name: s.skill?.name ?? "Skill",
      slug: s.skill?.slug ?? "",
      current: s.proficiency,
      target:
        requiredBySlug.get(s.skill?.slug ?? "") ??
        s.target_proficiency ??
        Math.min(1, s.proficiency + 0.2),
    }));

  const milestones: MilestoneDatum[] = [];
  const phases: PhaseDatum[] = (roadmap?.phases ?? []).map((ph) => {
    const ms: MilestoneDatum[] = ph.milestones.map((m) => {
      const status =
        m.resources.find((r) => r.status === "in_progress")?.status ??
        (m.resources.every((r) => r.status === "completed" || r.status === "skipped") &&
        m.resources.length
          ? "completed"
          : m.resources.find((r) => r.status === "available")
            ? "available"
            : "locked");
      const datum: MilestoneDatum = {
        phaseTitle: ph.title,
        phaseIndex: ph.index,
        title: m.title,
        status,
        current: m.current_level,
        required: m.required_level,
        gap: m.gap,
        estimatedMinutes: m.estimated_minutes,
        resourceCount: m.resources.length,
        hasAssessment: !!m.assessment,
        isCapstone: ph.is_capstone,
        completionCriteria: m.completion_criteria,
      };
      milestones.push(datum);
      return datum;
    });
    return {
      index: ph.index,
      title: ph.title,
      objective: ph.objective,
      isCapstone: ph.is_capstone,
      estimatedMinutes: ph.estimated_minutes,
      status: phaseStatus(ms),
      milestones: ms,
    };
  });

  // next action = first available/in-progress item across the roadmap.
  let nextAction: DashboardData["nextAction"] = null;
  let currentMilestone = "";
  outer: for (const ph of roadmap?.phases ?? []) {
    for (const m of ph.milestones) {
      for (const item of [...m.resources, ...(m.assessment ? [m.assessment] : []), ...(m.project ? [m.project] : [])]) {
        if (item.status === "available" || item.status === "in_progress") {
          nextAction = {
            title: item.title,
            kind: item.kind,
            phase: ph.title,
            milestone: m.title,
            estimatedMinutes: item.estimated_minutes,
          };
          currentMilestone = m.title;
          break outer;
        }
      }
    }
  }

  const recs: RecommendationDatum[] = (recommendations?.recommendations ?? []).map((r, i) => ({
    id: r.resource.id ?? String(i),
    title: r.resource.title,
    type: r.resource.resource_type,
    difficulty: r.resource.difficulty,
    estimatedHours: r.resource.estimated_hours,
    skill: r.matched_skills[0]?.name ?? r.resource.skills[0]?.skill?.name ?? "—",
    reason: r.reason,
    url: r.resource.url,
    provider: r.resource.provider,
    isReady: r.is_ready,
    score: r.score,
    cta: ctaForType(r.resource.resource_type),
  }));

  const assessments = (profile.assessment_history.recent ?? []).map((a) => ({
    id: a.id,
    title: `Assessment ${a.assessment_id.slice(0, 8)}`,
    percentage: a.percentage,
    passed: a.passed,
    submittedAt: a.submitted_at,
    mastery: masteryFromPct(a.percentage),
  }));

  // activity: sum COMPLETED/PROGRESSED minutes per day over the last 14 days.
  const byDay = new Map<string, number>();
  events.forEach((e) => {
    const day = (e.occurred_at ?? "").slice(0, 10);
    if (day) byDay.set(day, (byDay.get(day) ?? 0) + e.time_spent_minutes);
  });
  const activity: ActivityDatum[] = [];
  const today = new Date();
  for (let i = 13; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    activity.push({
      date: key,
      label: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      minutes: byDay.get(key) ?? 0,
    });
  }

  const p = profile.profile;
  const goal = p.goal_text_raw || p.target_role || "Your learning goal";
  const role = p.target_role || "your goal";
  const progressPct = Math.round(progress?.completion_pct ?? 0);

  // Rich roadmap model — real when we have a path, else the demo so the
  // roadmap interface stays meaningful.
  const roadmapView = roadmap
    ? buildRoadmapView(roadmap, recommendations, goal, role, progressPct)
    : demoRoadmap;

  return {
    goal,
    role,
    progressPct,
    weeklyHours: p.weekly_hours,
    skills,
    phases,
    milestones,
    roadmap: roadmapView,
    currentMilestone: currentMilestone || milestones.find((m) => m.status === "in_progress")?.title || "—",
    nextAction,
    recommendations: recs,
    assessments,
    activity,
    stats: {
      skillsTracked: profile.skill_count,
      itemsCompleted: progress?.active_path_completed_items ?? 0,
      itemsTotal: progress?.active_path_total_items ?? 0,
      hoursSpent: Math.round((progress?.total_time_minutes ?? 0) / 60),
      totalPlannedHours: Math.round((roadmap?.total_estimated_minutes ?? 0) / 60),
      avgAssessment: profile.assessment_history.average_percentage ?? 0,
    },
    isDemo: false,
  };
}

