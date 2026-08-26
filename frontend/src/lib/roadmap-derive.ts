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
  const levelReached = m.gap <= 0;

  if (items.length === 0) return levelReached ? "completed" : "locked";
  if (items.some((i) => i.status === "in_progress")) return "current";

  const itemsDone = items.every((i) => i.status === "completed" || i.status === "skipped");
  // Finishing the material is not the same as reaching the level. Proficiency
  // moves on assessment evidence, so a learner can complete every resource and
  // still sit below the target — claiming "completed" there put a COMPLETED
  // badge directly above "75% → target 85%", which is a contradiction, not a
  // status. Until the level is met the milestone is still in progress.
  if (itemsDone) return levelReached ? "completed" : "current";

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
    // The item carries its own catalogue fields; the recommendation is only a
    // second opinion. Reading the item first matters because recommendations
    // are fetched for a handful of target skills, so most of the plan is
    // absent from them — resolving the URL through `rec` alone left the
    // majority of courses with no link to open.
    return {
      id: item.id,
      resourceId: item.resource_id ?? undefined,
      title: item.title,
      kind: item.kind,
      type: item.resource_type ?? res?.resource_type ?? item.kind,
      provider: item.provider ?? res?.provider ?? "",
      description: item.description ?? res?.description ?? "",
      url: item.url ?? res?.url ?? "",
      estimatedMinutes: item.estimated_minutes,
      difficulty: item.difficulty ?? res?.difficulty ?? 0,
      skills:
        item.skills?.length
          ? item.skills
          : res?.skills.map((s) => s.skill?.name ?? "").filter(Boolean) ?? [],
      // Only the recommender knows which prerequisites this learner has *not*
      // met; the item lists them all. Prefer the personalised set.
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
        skillSlug: m.skill_slug ?? undefined,
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
              description: m.project.description ?? "",
              estimatedMinutes: m.project.estimated_minutes,
              skills: m.project.skills?.length
                ? m.project.skills
                : m.skill_slug
                  ? [titleCase(m.skill_slug)]
                  : [],
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
