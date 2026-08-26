"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api, auth, getToken } from "@/lib/api";
import type { DashboardData } from "@/lib/dashboard-data";
import { buildDashboardData } from "@/lib/derive";
import { demoData } from "@/lib/demo";
import { patchDashboardFromAdaptive } from "@/lib/adaptive";
import type {
  AdaptiveUpdateResponse,
  ProgressEvent,
  ProgressSummary,
  RecommendationResponse,
} from "@/lib/types";

type State = {
  data: DashboardData;
  loading: boolean;
  error: string | null;
  isDemo: boolean;
  /** Signed in, but no profile yet — this learner has not been onboarded. */
  needsOnboarding: boolean;
};

// Loads the signed-in learner's dashboard through the API layer, falling back to
// the bundled demo dataset when signed out or when core data is unavailable.
export function useDashboardData(): State & {
  reload: () => void;
  applyAdaptive: (res: AdaptiveUpdateResponse) => void;
} {
  const [state, setState] = useState<State>({
    data: demoData,
    loading: true,
    error: null,
    isDemo: true,
    needsOnboarding: false,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    if (!getToken()) {
      setState({
        data: demoData,
        loading: false,
        error: null,
        isDemo: true,
        needsOnboarding: false,
      });
      return;
    }
    try {
      const user = await auth.me();
      const [profile, roadmap] = await Promise.all([
        api.getFullProfile(user.id),
        api.getLearningPath(user.id).catch(() => null),
      ]);

      // best-effort secondary calls (never block the dashboard)
      const targetSkills = (roadmap?.phases ?? [])
        .flatMap((p) => p.milestones)
        .filter((m) => m.skill_slug && m.gap > 0)
        .map((m) => ({ skill_slug: m.skill_slug as string, required_level: m.required_level }))
        .slice(0, 8);

      const [progress, recommendations, eventsPage] = await Promise.all([
        api.getProgressSummary().catch(() => null as ProgressSummary | null),
        targetSkills.length
          ? api
              .getRecommendations(user.id, profile.profile.target_role || "your goal", targetSkills)
              .catch(() => null as RecommendationResponse | null)
          : Promise.resolve(null),
        api.getProgressEvents().then((p) => p.items).catch(() => [] as ProgressEvent[]),
      ]);

      const data = buildDashboardData({ profile, roadmap, progress, recommendations, events: eventsPage });
      setState({ data, loading: false, error: null, isDemo: false, needsOnboarding: false });
    } catch (e) {
      // Signed in but with no profile yet: this is a NEW learner, not an error.
      // Showing them a stranger's demo journey as though it were theirs was the
      // wrong call — they get onboarding instead, and the demo stays something
      // you opt into.
      const notFound = e instanceof ApiError && e.status === 404;
      setState({
        data: demoData,
        loading: false,
        error: notFound ? null : e instanceof Error ? e.message : "Failed to load",
        isDemo: true,
        needsOnboarding: notFound,
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Apply an adaptive result to the in-memory data so skill/roadmap bars animate
  // immediately. In live mode `reload()` then reconciles with backend truth.
  const applyAdaptive = useCallback((res: AdaptiveUpdateResponse) => {
    setState((s) => ({ ...s, data: patchDashboardFromAdaptive(s.data, res) }));
  }, []);

  return { ...state, reload: () => void load(), applyAdaptive };
}
