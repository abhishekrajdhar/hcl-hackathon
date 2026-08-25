"use client";

import { useCallback, useEffect, useState } from "react";
import { api, auth, getToken, graphApi } from "@/lib/api";
import type { DashboardData } from "@/lib/dashboard-data";
import {
  buildGraphModel,
  goalSlugs,
  pickExpandSlugs,
  toProficiencies,
} from "@/lib/graph-derive";
import { demoGraph } from "@/lib/graph-demo";
import type { GraphModel } from "@/lib/graph-view";
import type { SkillGraphResponse, SkillListItem } from "@/lib/types";

/** How many target skills we expand closures for. Each one is a request. */
const MAX_TARGETS = 6;

interface State {
  graph: GraphModel;
  loading: boolean;
  isDemo: boolean;
  error: string | null;
}

/**
 * Loads the learner's knowledge graph: the prerequisite closure of the skills
 * their goal targets, coloured by the proficiencies the dashboard already
 * holds. Falls back to the bundled demo graph when signed out or when the
 * account has no path yet — the same rule the rest of the dashboard follows.
 */
export function useKnowledgeGraph(data: DashboardData, dashboardIsDemo: boolean) {
  const [state, setState] = useState<State>({
    graph: demoGraph,
    loading: true,
    isDemo: true,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));

    if (!getToken() || dashboardIsDemo) {
      setState({ graph: demoGraph, loading: false, isDemo: true, error: null });
      return;
    }

    try {
      const roadmapSlugs = data.roadmap.phases
        .flatMap((p) => p.milestones)
        .map((m) => m.skillSlug)
        .filter((s): s is string => Boolean(s));

      // The learner's FULL proficiency list — `data.skills` is capped at eight
      // for the charts, which would leave the weakest skills uncoloured.
      const user = await auth.me();
      const [page, profileSkills] = await Promise.all([
        graphApi.listSkills(),
        api.getSkills(user.id),
      ]);
      const proficiencies = toProficiencies(profileSkills);

      // Every goal skill is flagged as a target; only the deepest few are
      // expanded, since each expansion costs a request.
      const targetSlugs = goalSlugs(roadmapSlugs, proficiencies);
      const expandSlugs = pickExpandSlugs(roadmapSlugs, proficiencies, MAX_TARGETS);
      if (!expandSlugs.length) {
        setState({ graph: demoGraph, loading: false, isDemo: true, error: null });
        return;
      }

      const catalogue: SkillListItem[] = page.items;
      const bySlug = new Map(catalogue.map((s) => [s.slug, s]));
      const targetIds = expandSlugs
        .map((slug) => bySlug.get(slug)?.id)
        .filter((id): id is string => Boolean(id));

      if (!targetIds.length) {
        setState({ graph: demoGraph, loading: false, isDemo: true, error: null });
        return;
      }

      // One closure per target; a target that fails is skipped rather than
      // failing the whole graph.
      const closures = (
        await Promise.all(
          targetIds.map((id) =>
            graphApi.getSkillGraph(id).catch(() => null as SkillGraphResponse | null),
          ),
        )
      ).filter((c): c is SkillGraphResponse => Boolean(c));

      if (!closures.length) {
        setState({ graph: demoGraph, loading: false, isDemo: true, error: null });
        return;
      }

      const graph = buildGraphModel({
        closures,
        catalogue,
        targetSlugs,
        proficiencies,
        goal: data.goal,
      });

      setState({ graph, loading: false, isDemo: false, error: null });
    } catch (e) {
      setState({
        graph: demoGraph,
        loading: false,
        isDemo: true,
        error: e instanceof Error ? e.message : "Failed to load the skill graph",
      });
    }
  }, [data.goal, data.roadmap, dashboardIsDemo]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, reload: () => void load() };
}
