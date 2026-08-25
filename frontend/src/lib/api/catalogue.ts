// The shared catalogue: skills, categories, resources and goals.
//
// Reads are open to any signed-in learner; the writes here require the admin
// role and will return 403 for a learner, which the caller should surface
// rather than hide.

import type {
  GoalRead,
  Paginated,
  ResourceRead,
  SkillCategoryRead,
  SkillListItem,
  UUID,
} from "@/lib/types";
import { request } from "./client";

// --- skills -----------------------------------------------------------------
export function listSkills(params: {
  limit?: number;
  offset?: number;
  search?: string;
  category?: string;
} = {}): Promise<Paginated<SkillListItem>> {
  return request<Paginated<SkillListItem>>("/skills", { query: { limit: 200, ...params } });
}

export function getSkill(skillId: UUID): Promise<SkillListItem> {
  return request<SkillListItem>(`/skills/${skillId}`);
}

export function listCategories(): Promise<Paginated<SkillCategoryRead>> {
  return request<Paginated<SkillCategoryRead>>("/skill-categories", { query: { limit: 100 } });
}

/** Admin-only integrity check: any prerequisite cycles in the whole graph. */
export function detectCycles(): Promise<{ has_cycles: boolean; cycles: unknown[] }> {
  return request<{ has_cycles: boolean; cycles: unknown[] }>("/skills/graph/cycles");
}

// --- resources --------------------------------------------------------------
export function listResources(params: {
  limit?: number;
  offset?: number;
  search?: string;
  resource_type?: string;
} = {}): Promise<Paginated<ResourceRead>> {
  return request<Paginated<ResourceRead>>("/resources", { query: { limit: 50, ...params } });
}

export function getResource(resourceId: UUID): Promise<ResourceRead> {
  return request<ResourceRead>(`/resources/${resourceId}`);
}

export function getResourceSkills(resourceId: UUID): Promise<unknown[]> {
  return request<unknown[]>(`/resources/${resourceId}/skills`);
}

export function getResourcePrerequisites(resourceId: UUID): Promise<unknown[]> {
  return request<unknown[]>(`/resources/${resourceId}/prerequisites`);
}

// --- goals ------------------------------------------------------------------
export function listGoals(): Promise<Paginated<GoalRead>> {
  return request<Paginated<GoalRead>>("/goals", { query: { limit: 50 } });
}

export function getGoal(goalId: UUID): Promise<GoalRead> {
  return request<GoalRead>(`/goals/${goalId}`);
}

export function createGoal(body: {
  title: string;
  description?: string;
  target_date?: string;
}): Promise<GoalRead> {
  return request<GoalRead>("/goals", { method: "POST", body });
}

export function updateGoal(goalId: UUID, body: Partial<GoalRead>): Promise<GoalRead> {
  return request<GoalRead>(`/goals/${goalId}`, { method: "PATCH", body });
}

export function deleteGoal(goalId: UUID): Promise<void> {
  return request<void>(`/goals/${goalId}`, { method: "DELETE" });
}
