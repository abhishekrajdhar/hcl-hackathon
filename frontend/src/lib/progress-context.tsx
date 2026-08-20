"use client";

// Bridges learner actions in the UI to the adaptive backend. Deep components
// call `useProgress().completeResource(...)` etc. without prop-drilling. Each
// action: (1) sends the appropriate API request (adaptive update / feedback),
// (2) applies the result locally so bars animate instantly, (3) re-reads the
// dashboard so the backend stays the source of truth, and (4) shows the
// "Your roadmap has been updated." notification. In demo mode the same result
// is produced locally via `simulateAdaptive` so the loop is fully demonstrable.

import { createContext, useCallback, useContext, useState } from "react";
import { progressApi } from "@/lib/api";
import { useToast } from "@/lib/hooks/useToast";
import {
  buildAdaptiveNotice,
  simulateAdaptive,
  type SimAction,
} from "@/lib/adaptive";
import type { DashboardData } from "@/lib/dashboard-data";
import type { RoadmapMilestone, RoadmapResource } from "@/lib/roadmap-view";
import type { AdaptiveUpdateResponse, FeedbackSignal } from "@/lib/types";

interface ProgressActions {
  pending: boolean;
  completeResource: (m: RoadmapMilestone, r: RoadmapResource) => Promise<void>;
  skipResource: (m: RoadmapMilestone, r: RoadmapResource) => Promise<void>;
  submitAssessment: (m: RoadmapMilestone, score: number) => Promise<void>;
  sendFeedback: (r: RoadmapResource, signal: FeedbackSignal) => Promise<void>;
}

const Ctx = createContext<ProgressActions | null>(null);

export function ProgressProvider({
  data,
  isDemo,
  userId,
  applyAdaptive,
  reload,
  children,
}: {
  data: DashboardData;
  isDemo: boolean;
  userId: string | null;
  applyAdaptive: (res: AdaptiveUpdateResponse) => void;
  reload: () => void;
  children: React.ReactNode;
}) {
  const { notify } = useToast();
  const [pending, setPending] = useState(false);

  // Live when we have a real account and the item carries a backend id; else demo.
  const canGoLive = !isDemo && !!userId;

  // Run a real adaptive call or the local simulation, then animate + notify + refresh.
  const runAdaptive = useCallback(
    async (
      live: (() => Promise<AdaptiveUpdateResponse>) | null,
      sim: SimAction,
    ) => {
      if (pending) return;
      setPending(true);
      try {
        const res = live ? await live() : simulateAdaptive(data, sim);
        applyAdaptive(res); // instant before→after animation
        notify(buildAdaptiveNotice(res));
        if (live) reload(); // reconcile with backend truth
      } catch {
        notify({
          title: "Couldn't update your progress",
          body: "The adaptive service didn't respond. Please try again.",
          tone: "neutral",
        });
      } finally {
        setPending(false);
      }
    },
    [pending, data, applyAdaptive, notify, reload],
  );

  const completeResource = useCallback(
    async (m: RoadmapMilestone, r: RoadmapResource) => {
      const live =
        canGoLive && r.resourceId
          ? () => progressApi.adaptiveUpdate({ user_id: userId!, completed_resource_id: r.resourceId })
          : null;
      await runAdaptive(live, { kind: "complete", skill: m.skill, resourceTitle: r.title });
    },
    [canGoLive, userId, runAdaptive],
  );

  const skipResource = useCallback(
    async (m: RoadmapMilestone, r: RoadmapResource) => {
      const live =
        canGoLive && r.resourceId
          ? () => progressApi.adaptiveUpdate({ user_id: userId!, skipped_resource_id: r.resourceId })
          : null;
      await runAdaptive(live, { kind: "skip", skill: m.skill, resourceTitle: r.title });
    },
    [canGoLive, userId, runAdaptive],
  );

  const submitAssessment = useCallback(
    async (m: RoadmapMilestone, score: number) => {
      const live =
        canGoLive && m.skillSlug
          ? () =>
              progressApi.adaptiveUpdate({
                user_id: userId!,
                skill_scores: [{ skill_slug: m.skillSlug, score }],
              })
          : null;
      await runAdaptive(live, { kind: "assessment", skill: m.skill, score });
    },
    [canGoLive, userId, runAdaptive],
  );

  const sendFeedback = useCallback(
    async (r: RoadmapResource, signal: FeedbackSignal) => {
      const positive = signal === "up";
      // Feedback doesn't run the adaptive pipeline; record it, then refresh
      // (it can nudge future recommendations) and acknowledge.
      if (canGoLive && r.resourceId) {
        try {
          await progressApi.submitFeedback({
            target_type: "resource",
            target_id: r.resourceId,
            signal,
          });
          reload();
        } catch {
          /* non-blocking */
        }
      }
      notify({
        title: positive ? "Thanks — noted what's working" : "Thanks — we'll tune your recommendations",
        body: positive
          ? `We'll favor resources like "${r.title}".`
          : `We'll show fewer resources like "${r.title}".`,
        tone: "neutral",
      });
    },
    [canGoLive, userId, reload, notify],
  );

  return (
    <Ctx.Provider value={{ pending, completeResource, skipResource, submitAssessment, sendFeedback }}>
      {children}
    </Ctx.Provider>
  );
}

export function useProgress(): ProgressActions {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useProgress must be used within a ProgressProvider");
  return ctx;
}
