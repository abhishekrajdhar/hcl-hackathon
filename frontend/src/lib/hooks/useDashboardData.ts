"use client";

import { useCallback, useEffect, useState } from "react";
import { api, auth, getToken } from "@/lib/api";
import type { DashboardData } from "@/lib/dashboard-data";
import { buildDashboardData } from "@/lib/derive";
import { demoData } from "@/lib/demo";
import type { ProgressEvent, ProgressSummary, RecommendationResponse } from "@/lib/types";

type State = {
  data: DashboardData;
  loading: boolean;
  error: string | null;
  isDemo: boolean;
};

// Loads the signed-in learner's dashboard through the API layer, falling back to
// the bundled demo dataset when signed out or when core data is unavailable.
export function useDashboardData(): State & { reload: () => void } {
  const [state, setState] = useState<State>({
    data: demoData,
    loading: true,
    error: null,
    isDemo: true,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    if (!getToken()) {
      setState({ data: demoData, loading: false, error: null, isDemo: true });
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
      setState({ data, loading: false, error: null, isDemo: false });
    } catch (e) {
      // Signed in but no profile/path yet — show the demo so the UI is meaningful.
      setState({
        data: demoData,
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load",
        isDemo: true,
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, reload: () => void load() };
}
