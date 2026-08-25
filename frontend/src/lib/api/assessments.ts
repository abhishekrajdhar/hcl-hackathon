// Assessments: taking them, reading results, and the reviewer queue for the
// short answers grading deliberately refuses to auto-mark.

import type {
  AssessmentAnswer,
  AssessmentQuestionRead,
  AssessmentRead,
  AssessmentResultRead,
  Paginated,
  PendingReview,
  UUID,
} from "@/lib/types";
import { request } from "./client";

export function listAssessments(params: { limit?: number; skill_id?: UUID } = {}) {
  return request<Paginated<AssessmentRead>>("/assessments", { query: { limit: 50, ...params } });
}

export function getAssessment(assessmentId: UUID): Promise<AssessmentRead> {
  return request<AssessmentRead>(`/assessments/${assessmentId}`);
}

/** Learner-facing questions — the answer key is not included. */
export function getQuestions(assessmentId: UUID): Promise<AssessmentQuestionRead[]> {
  return request<AssessmentQuestionRead[]>(`/assessments/${assessmentId}/questions`);
}

export function submit(
  assessmentId: UUID,
  answers: AssessmentAnswer[],
  durationSeconds?: number,
): Promise<AssessmentResultRead> {
  return request<AssessmentResultRead>(`/assessments/${assessmentId}/submit`, {
    method: "POST",
    body: { answers, duration_seconds: durationSeconds },
  });
}

/** Generate an assessment for a skill (LLM-drafted, validated before use). */
export function generate(body: {
  skill_id: UUID;
  question_count?: number;
}): Promise<AssessmentRead> {
  return request<AssessmentRead>("/assessments/generate", { method: "POST", body });
}

export function myResults(limit = 20): Promise<Paginated<AssessmentResultRead>> {
  return request<Paginated<AssessmentResultRead>>("/me/assessment-results", { query: { limit } });
}

export function getResult(resultId: UUID): Promise<AssessmentResultRead> {
  return request<AssessmentResultRead>(`/me/assessment-results/${resultId}`);
}

// --- reviewer queue (admin) -------------------------------------------------
export function pendingReviews(limit = 50): Promise<Paginated<PendingReview>> {
  return request<Paginated<PendingReview>>("/assessment-reviews", { query: { limit } });
}

export function reviewResponse(
  resultId: UUID,
  body: { question_id: UUID; is_correct: boolean; note?: string },
): Promise<AssessmentResultRead> {
  return request<AssessmentResultRead>(`/assessment-reviews/${resultId}`, {
    method: "POST",
    body,
  });
}
