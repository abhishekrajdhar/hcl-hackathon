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
