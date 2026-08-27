"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api, auth, getToken } from "@/lib/api";
import type { DashboardData } from "@/lib/dashboard-data";
import { emptyDashboardData } from "@/lib/dashboard-data";
import { buildDashboardData } from "@/lib/derive";
import { isDemoEmail } from "@/lib/demo-session";
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
  /** Signed in as the shared demo account — real data, shared journey. */
  isDemo: boolean;
  /** Signed in, but no profile yet — this learner has not been onboarded. */
  needsOnboarding: boolean;
  /**
   * Profile and goal exist but no active roadmap does — onboarding was
   * interrupted, or the path was deleted. The dashboard offers to generate
   * one from the stored goal rather than showing an empty universe.
   */
  missingPath: { userId: string; goalText: string } | null;
};

// Loads the signed-in learner's dashboard through the API layer. There is no
// bundled dataset: every session — the shared demo account included — renders
// what the backend computed for it, or an honest empty/error state.
export function useDashboardData(): State & {
  reload: () => void;
  applyAdaptive: (res: AdaptiveUpdateResponse) => void;
} {
  const [state, setState] = useState<State>({
    data: emptyDashboardData(),
    loading: true,
    error: null,
    isDemo: false,
    needsOnboarding: false,
    missingPath: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    if (!getToken()) {
      // Signed out. The dashboard route either redirects to /login or is
      // busy signing into the demo account; render nothing in the meantime.
      setState({
        data: emptyDashboardData(),
        loading: false,
        error: null,
        isDemo: false,
        needsOnboarding: false,
        missingPath: null,
      });
      return;
    }
    try {
      const user = await auth.me();
      const isDemo = isDemoEmail(user.email);
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
      const goalText = profile.profile.goal_text_raw || profile.profile.target_role || "";
      setState({
        data: { ...data, isDemo },
        loading: false,
        error: null,
        isDemo,
        needsOnboarding: false,
        missingPath: !roadmap && goalText ? { userId: user.id, goalText } : null,
      });
    } catch (e) {
      // Signed in but with no profile yet: a NEW learner, not an error. They
      // go to onboarding.
      if (e instanceof ApiError && e.status === 404) {
        setState({
          data: emptyDashboardData(),
          loading: false,
          error: null,
          isDemo: false,
          needsOnboarding: true,
          missingPath: null,
        });
        return;
      }
      // A failure renders as a failure. Substituting anything that looks like
      // data would tell a signed-in learner a story that is not theirs.
      setState({
        data: emptyDashboardData(),
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load your data",
        isDemo: false,
        needsOnboarding: false,
        missingPath: null,
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Apply an adaptive result to the in-memory data so skill/roadmap bars animate
  // immediately. `reload()` then reconciles with backend truth.
  const applyAdaptive = useCallback((res: AdaptiveUpdateResponse) => {
    setState((s) => ({ ...s, data: patchDashboardFromAdaptive(s.data, res) }));
  }, []);

  return { ...state, reload: () => void load(), applyAdaptive };
}
