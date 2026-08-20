// Learner-action endpoints that drive the adaptive backend. The backend remains
// the source of truth: these post an event, and the caller then re-reads the
// dashboard so skills, gaps, roadmap, milestones, recommendations and the next
// action all reflect the backend's recomputed state.
import type {
  AdaptiveUpdateRequest,
  AdaptiveUpdateResponse,
  FeedbackCreate,
  ProgressEventCreate,
  ProgressEvent,
  UUID,
} from "@/lib/types";
import { request } from "./client";

/**
 * Run the deterministic adaptive pipeline from a single learner event
 * (completion, skip, or an assessment/explicit skill score). Returns what
 * changed: updated skills, completed/unlocked milestones, and the next action.
 */
export function adaptiveUpdate(payload: AdaptiveUpdateRequest): Promise<AdaptiveUpdateResponse> {
  return request<AdaptiveUpdateResponse>("/adaptive/update", {
    method: "POST",
    body: payload,
  });
}

/** Append a raw progress event (started/progressed/completed/skipped). */
export function recordProgressEvent(payload: ProgressEventCreate): Promise<ProgressEvent> {
  return request<ProgressEvent>("/progress/events", {
    method: "POST",
    body: payload,
  });
}

/** Record thumbs up/down (or too easy/hard) on a resource or recommendation. */
export function submitFeedback(payload: FeedbackCreate): Promise<{ id: UUID }> {
  return request<{ id: UUID }>("/feedback", {
    method: "POST",
    body: payload,
  });
}
