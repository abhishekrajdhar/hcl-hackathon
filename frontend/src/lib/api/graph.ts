import type {
  Paginated,
  SkillDependencyAnalysis,
  SkillGraphResponse,
  SkillListItem,
  UUID,
} from "@/lib/types";
import { request } from "./client";

/** The whole catalogue in one page (MAX_PAGE_SIZE is 200; the seed has ~49). */
export function listSkills(limit = 200): Promise<Paginated<SkillListItem>> {
  return request<Paginated<SkillListItem>>("/skills", { query: { limit } });
}

/**
 * Transitive prerequisite closure of one skill, as a flat node/edge list.
 * Edges carry `relationship_type` and `rationale`, which the detail panel
 * quotes rather than inventing a reason of its own.
 */
export function getSkillGraph(skillId: UUID, depth = 16): Promise<SkillGraphResponse> {
  return request<SkillGraphResponse>(`/skills/${skillId}/graph`, { query: { depth } });
}

/**
 * Full dependency analysis. Used to answer "what can I build after this?" with
 * the whole catalogue in view, not just the part of it on the learner's path.
 */
export function getSkillDependencies(skillId: UUID): Promise<SkillDependencyAnalysis> {
  return request<SkillDependencyAnalysis>(`/skills/${skillId}/dependencies`);
}
