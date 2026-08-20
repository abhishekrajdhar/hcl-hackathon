// Build the rich RoadmapView from the live API roadmap + recommendations.
// The roadmap items carry only ids/status; richer per-resource detail
// (description, skills, difficulty, "why") is enriched from the recommendation
// list by resource id, then by title. Best-effort: missing detail degrades
// gracefully rather than breaking the view.

import type {
  LearningPathRoadmap,
  RecommendationItem,
  RecommendationResponse,
  RoadmapItem,
  RoadmapMilestone as ApiMilestone,
  RoadmapPhase as ApiPhase,
} from "@/lib/types";
import {
  toRoadmapState,
  type RoadmapMilestone,
  type RoadmapPhase,
  type RoadmapResource,
  type RoadmapState,
  type RoadmapView,
} from "@/lib/roadmap-view";
import { titleCase } from "@/lib/format";

function milestoneState(m: ApiMilestone): RoadmapState {
  const items = [...m.resources, ...(m.assessment ? [m.assessment] : []), ...(m.project ? [m.project] : [])];
  if (items.length === 0) return m.gap <= 0 ? "completed" : "locked";
  if (items.some((i) => i.status === "in_progress")) return "current";
  if (items.every((i) => i.status === "completed" || i.status === "skipped")) return "completed";
  if (items.some((i) => i.status === "available")) return "available";
  return "locked";
}

function completionPct(items: { status: string }[], current: number, required: number): number {
  if (items.length) {
    const done = items.filter((i) => i.status === "completed" || i.status === "skipped").length;
    return Math.round((done / items.length) * 100);
  }
  if (required > 0) return Math.min(100, Math.round((current / required) * 100));
  return 0;
}

export function buildRoadmapView(
  roadmap: LearningPathRoadmap,
  recommendations: RecommendationResponse | null,
  goal: string,
  role: string,
  progressPct: number,
): RoadmapView {
  const recById = new Map<string, RecommendationItem>();
  const recByTitle = new Map<string, RecommendationItem>();
  for (const r of recommendations?.recommendations ?? []) {
    recById.set(r.resource.id, r);
    recByTitle.set(r.resource.title.toLowerCase(), r);
  }

  const enrichResource = (item: RoadmapItem): RoadmapResource => {
    const rec =
      (item.resource_id && recById.get(item.resource_id)) ||
      recByTitle.get(item.title.toLowerCase()) ||
      null;
    const res = rec?.resource;
    return {
      id: item.id,
      title: item.title,
      kind: item.kind,
      type: res?.resource_type ?? item.kind,
      provider: res?.provider ?? "",
      description: res?.description ?? "",
      url: res?.url ?? "",
      estimatedMinutes: item.estimated_minutes,
      difficulty: res?.difficulty ?? 0,
      skills: res?.skills.map((s) => s.skill?.name ?? "").filter(Boolean) ?? [],
      prerequisites: rec?.unmet_prerequisites.map((p) => p.name) ?? [],
      why: rec?.reason ?? "",
      status: toRoadmapState(item.status),
      isOptional: item.is_optional,
    };
  };

  const phases: RoadmapPhase[] = roadmap.phases.map((ph: ApiPhase) => {
    const milestones: RoadmapMilestone[] = ph.milestones.map((m) => {
      const items = [...m.resources, ...(m.assessment ? [m.assessment] : []), ...(m.project ? [m.project] : [])];
      const state = milestoneState(m);
      return {
        id: m.skill_id ?? m.skill_slug ?? m.title,
        title: m.title,
        skill: m.skill_slug ? titleCase(m.skill_slug) : m.title,
        state,
        current: m.current_level,
        required: m.required_level,
        completionPct: completionPct(items, m.current_level, m.required_level),
        estimatedMinutes: m.estimated_minutes,
        completionCriteria: m.completion_criteria,
        prerequisites: m.prerequisites.map(titleCase),
        requiredSkills: m.skill_slug ? [titleCase(m.skill_slug)] : [],
        resources: m.resources.map(enrichResource),
        assessment: m.assessment
          ? {
              id: m.assessment.id,
              title: m.assessment.title,
              estimatedMinutes: m.assessment.estimated_minutes,
              passingPct: 0.7,
              status: toRoadmapState(m.assessment.status),
            }
          : null,
        project: m.project
          ? {
              id: m.project.id,
              title: m.project.title,
              description: "",
              estimatedMinutes: m.project.estimated_minutes,
              skills: m.skill_slug ? [titleCase(m.skill_slug)] : [],
              status: toRoadmapState(m.project.status),
            }
          : null,
      };
    });

    const allItems = milestones.flatMap((m) => [
      ...m.resources,
      ...(m.assessment ? [m.assessment] : []),
      ...(m.project ? [m.project] : []),
    ]);
    const phaseState: RoadmapState = milestones.length
      ? milestones.some((m) => m.state === "current")
        ? "current"
        : milestones.every((m) => m.state === "completed")
          ? "completed"
          : milestones.some((m) => m.state === "available" || m.state === "current")
            ? "available"
            : "locked"
      : "locked";

    return {
      index: ph.index,
      title: ph.title,
      objective: ph.objective,
      isCapstone: ph.is_capstone,
      state: phaseState,
      estimatedMinutes: ph.estimated_minutes,
      completionPct: completionPct(allItems, 0, 0),
      milestones,
    };
  });

  return {
    goal,
    role,
    progressPct,
    totalPlannedHours: Math.round(roadmap.total_estimated_minutes / 60),
    phases,
  };
}
