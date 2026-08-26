// The new-learner path: one sentence in, a real roadmap out.
//
// Nothing here is new backend surface — it sequences endpoints that already
// exist. `/chat` extracts the goal, weekly hours and any skills the learner
// claims from a single message and writes them to the profile; the generator
// then resolves the goal text to a catalogue skill and plans the route to it.

import type { ChatResponse, LearningPathRoadmap, UUID } from "@/lib/types";
import { request } from "./client";

/** Send the learner's description; the coach replies and updates the profile. */
export function describeGoal(message: string, conversationId?: UUID): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: { message, conversation_id: conversationId },
  });
}

/** Build the roadmap from the goal text the profile now holds. */
export function generatePath(userId: UUID, goalText: string): Promise<LearningPathRoadmap> {
  return request<LearningPathRoadmap>("/learning-path/generate", {
    method: "POST",
    body: { user_id: userId, goal_text: goalText, activate: true },
  });
}

// --- goal intelligence branches ---------------------------------------------

export interface CareerSuggestion {
  slug: string;
  title: string;
  pitch: string;
  score: number;
  reasons: string[];
  target_skills: { skill_slug: string; required_level: number }[];
}

/** The uncertain branch: signals in, ranked career directions out. */
export function discoverCareers(
  interests: string[],
  freeText: string,
): Promise<{ count: number; careers: CareerSuggestion[] }> {
  return request<{ count: number; careers: CareerSuggestion[] }>("/discovery/careers", {
    method: "POST",
    body: { interests, free_text: freeText, top_k: 3 },
  });
}

/** Resume intake: paste text, the extractor reads it into the profile. */
export function ingestResume(userId: UUID, text: string): Promise<unknown> {
  return request<unknown>(`/profile/${userId}/ingest`, {
    method: "POST",
    body: { text, apply: true },
  });
}

// --- conversational discovery ------------------------------------------------

export interface InterviewTurn {
  question: string;
  answer: string;
}

export interface InterviewStep {
  done: boolean;
  next_question: string | null;
  traits: Record<string, number>;
  careers: CareerSuggestion[];
}

/** One step of the discovery interview; the client carries the transcript. */
export function interviewStep(turns: InterviewTurn[]): Promise<InterviewStep> {
  return request<InterviewStep>("/discovery/interview", {
    method: "POST",
    body: { turns },
  });
}
