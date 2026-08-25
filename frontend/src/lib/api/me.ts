// Everything scoped to the signed-in learner: their profile, their recorded
// skills, their goals and their feedback. The backend derives the user from
// the bearer token, so nothing here takes a user id except the profile routes
// that are also reachable by an admin.

import type {
  FeedbackCreate,
  FeedbackSignal,
  FullLearnerProfile,
  LearnerProfile,
  Paginated,
  SkillProficiency,
  UUID,
} from "@/lib/types";
import { request } from "./client";

// --- profile ----------------------------------------------------------------
export function getMyProfile(): Promise<LearnerProfile> {
  return request<LearnerProfile>("/profile");
}

export function getFullProfile(userId: UUID): Promise<FullLearnerProfile> {
  return request<FullLearnerProfile>(`/profile/${userId}`);
}

export function createProfile(body: Partial<LearnerProfile>): Promise<LearnerProfile> {
  return request<LearnerProfile>("/profile", { method: "POST", body });
}

export function updateProfile(body: Partial<LearnerProfile>): Promise<LearnerProfile> {
  return request<LearnerProfile>("/profile", { method: "PATCH", body });
}

export function deleteProfile(): Promise<void> {
  return request<void>("/profile", { method: "DELETE" });
}

/** Consistency issues the profile engine found (e.g. "expert" with no skills). */
export function validateProfile(userId: UUID): Promise<{ issues: unknown[] }> {
  return request<{ issues: unknown[] }>(`/profile/${userId}/validate`);
}

/** Free text → a structured profile draft. `apply: false` previews it. */
export function extractProfile(body: {
  user_id: UUID;
  message: string;
  apply?: boolean;
}): Promise<unknown> {
  return request<unknown>("/profile/extract", { method: "POST", body });
}

// --- recorded skills --------------------------------------------------------
export function listMySkills(limit = 200): Promise<Paginated<unknown>> {
  return request<Paginated<unknown>>("/me/skills", { query: { limit } });
}

export function listProfileSkills(userId: UUID): Promise<SkillProficiency[]> {
  return request<SkillProficiency[]>(`/profile/${userId}/skills`);
}

/** Create-or-update one skill entry. */
export function upsertMySkill(body: {
  skill_id: UUID;
  current_level: number;
  target_level?: number;
  confidence?: number;
}): Promise<unknown> {
  return request<unknown>("/me/skills", { method: "PUT", body });
}

export function updateMySkill(
  skillId: UUID,
  body: { current_level?: number; target_level?: number; confidence?: number },
): Promise<unknown> {
  return request<unknown>(`/me/skills/${skillId}`, { method: "PATCH", body });
}

export function removeMySkill(skillId: UUID): Promise<void> {
  return request<void>(`/me/skills/${skillId}`, { method: "DELETE" });
}

// --- feedback ---------------------------------------------------------------
export function listFeedback(limit = 50): Promise<Paginated<unknown>> {
  return request<Paginated<unknown>>("/feedback", { query: { limit } });
}

export function sendFeedback(body: FeedbackCreate): Promise<unknown> {
  return request<unknown>("/feedback", { method: "POST", body });
}

/** Convenience for the common case: rate a resource. */
export function rateResource(resourceId: UUID, signal: FeedbackSignal, comment?: string) {
  return sendFeedback({
    target_type: "resource",
    target_id: resourceId,
    signal,
    comment,
  } as FeedbackCreate);
}
