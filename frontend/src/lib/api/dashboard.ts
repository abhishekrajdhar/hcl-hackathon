import type {
  FullLearnerProfile,
  LearningPathRoadmap,
  Paginated,
  ProgressEvent,
  ProgressSummary,
  RecommendationResponse,
  SkillProficiency,
  UUID,
} from "@/lib/types";
import { request } from "./client";

export function getFullProfile(userId: UUID): Promise<FullLearnerProfile> {
  return request<FullLearnerProfile>(`/profile/${userId}`);
}

export function getSkills(userId: UUID): Promise<SkillProficiency[]> {
  return request<SkillProficiency[]>(`/profile/${userId}/skills`);
}

export function getLearningPath(userId: UUID): Promise<LearningPathRoadmap> {
  return request<LearningPathRoadmap>(`/learning-path/${userId}`);
}

export function getProgressSummary(): Promise<ProgressSummary> {
  return request<ProgressSummary>("/progress/summary");
}

export function getProgressEvents(limit = 60): Promise<Paginated<ProgressEvent>> {
  return request<Paginated<ProgressEvent>>("/progress/events", { query: { limit } });
}

export function getRecommendations(
  userId: UUID,
  goalText: string,
  targetSkills: { skill_slug: string; required_level: number }[],
): Promise<RecommendationResponse> {
  return request<RecommendationResponse>("/recommendations", {
    method: "POST",
    body: { user_id: userId, goal_text: goalText, target_skills: targetSkills, top_k: 6 },
  });
}

/** Grounded "why is this on my path?" for one roadmap item. The backend
 * composes it from the item's persisted rationale and the learner's current
 * records; the model only rephrases, behind a grounding check. */
export interface PathItemExplanation {
  item_id: UUID;
  kind: string;
  explanation: string;
  grounded: boolean;
  source: "llm" | "template";
}

export function explainPathItem(
  pathId: UUID,
  itemId: UUID,
  kind = "why_course",
): Promise<PathItemExplanation> {
  return request<PathItemExplanation>(`/learning-paths/${pathId}/items/${itemId}/explanation`, {
    method: "POST",
    body: { kind },
  });
}

/** Rebuild the roadmap from the current profile and catalogue. The old path
 * is superseded; item progress starts fresh on the new one. */
export function regeneratePath(pathId: UUID): Promise<LearningPathRoadmap> {
  return request<LearningPathRoadmap>(`/learning-path/${pathId}/regenerate`, {
    method: "POST",
    body: {},
  });
}
