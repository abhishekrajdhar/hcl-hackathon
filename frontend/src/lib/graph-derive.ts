// Builds the knowledge-graph view model from live API responses.
//
// Two sources are merged: the prerequisite closures of the learner's target
// skills (structure) and the proficiencies already loaded for the dashboard
// (colour). Nothing is inferred that the backend did not say — a skill with no
// recorded proficiency is painted "not started" rather than guessed at.

import type { GraphEdge, GraphModel, GraphNode } from "@/lib/graph-view";
import { masteryState } from "@/lib/graph-view";
import type { EdgeKind } from "@/lib/graph-view";
import type {
  PrerequisiteRead,
  SkillGraphResponse,
  SkillListItem,
  SkillProficiency,
} from "@/lib/types";

/**
 * One learner proficiency on the canonical [0, 1] scale.
 *
 * Deliberately NOT `DashboardData["skills"]`: that list is capped at the top
 * eight by proficiency so the radar stays readable, which silently drops the
 * lowest skills — exactly the ones the graph most needs to paint red.
 */
export interface GraphProficiency {
  slug: string;
  current: number;
  target: number | null;
}

/** Normalise the full profile skill list into what the graph colours from. */
export function toProficiencies(skills: SkillProficiency[]): GraphProficiency[] {
  return skills
    .filter((s) => s.skill?.slug)
    .map((s) => ({
      slug: s.skill!.slug,
      current: s.proficiency,
      target: s.target_proficiency,
    }));
}

export interface BuildGraphInput {
  /** Closure responses, one per expanded target skill. */
  closures: SkillGraphResponse[];
  /** The catalogue, for difficulty and category (the closure omits them). */
  catalogue: SkillListItem[];
  /**
   * Every slug the learner's goal asks for — not just the ones expanded. A
   * target that appears as somebody else's prerequisite still gets flagged.
   */
  targetSlugs: string[];
  /** The learner's full proficiency list, keyed by slug — the colour source. */
  proficiencies: GraphProficiency[];
  goal: string;
}

/**
 * Merge the closures into one graph. Nodes are deduplicated by id; edges by the
 * (prerequisite, dependent) pair, since two targets sharing a foundation will
 * each report the same edge.
 */
export function buildGraphModel(input: BuildGraphInput): GraphModel {
  const { closures, catalogue, targetSlugs, proficiencies, goal } = input;

  const meta = new Map(catalogue.map((s) => [s.id, s]));
  const bySlug = new Map(proficiencies.map((s) => [s.slug, s]));
  const targets = new Set(targetSlugs);

  const nodes = new Map<string, GraphNode>();
  for (const closure of closures) {
    for (const n of closure.nodes) {
      if (nodes.has(n.skill_id)) continue;
      const info = meta.get(n.skill_id);
      const tracked = bySlug.get(n.slug);
      const proficiency = tracked ? tracked.current : null;
      const required = tracked ? tracked.target : null;
      nodes.set(n.skill_id, {
        id: n.skill_id,
        slug: n.slug,
        name: n.name,
        difficulty: info?.difficulty ?? 0,
        category: info?.category?.name ?? null,
        isTarget: targets.has(n.slug),
        proficiency,
        required,
        state: masteryState(proficiency, required),
      });
    }
  }

  const edges = new Map<string, GraphEdge>();
  for (const closure of closures) {
    for (const e of closure.edges) {
      const key = `${e.prerequisite_skill_id}->${e.source_skill_id}`;
      if (edges.has(key)) continue;
      edges.set(key, toEdge(e));
    }
  }

  return {
    goal,
    nodes: [...nodes.values()],
    // Drop edges whose far end is not in view, so layout never routes to nothing.
    edges: [...edges.values()].filter(
      (e) => nodes.has(e.prerequisiteId) && nodes.has(e.dependentId),
    ),
  };
}

function toEdge(e: PrerequisiteRead): GraphEdge {
  return {
    prerequisiteId: e.prerequisite_skill_id,
    dependentId: e.source_skill_id,
    kind: e.relationship_type as EdgeKind,
    strength: e.strength,
    rationale: e.rationale,
  };
}

/**
 * Every skill the goal asks for, in roadmap order. Used to flag targets — the
 * whole set, regardless of how many we can afford to expand.
 */
export function goalSlugs(
  roadmapSlugs: string[],
  proficiencies: GraphProficiency[],
): string[] {
  const fromRoadmap = [...new Set(roadmapSlugs.filter(Boolean))];
  return fromRoadmap.length ? fromRoadmap : proficiencies.map((s) => s.slug);
}

/**
 * Which skills to actually expand a closure for — one request each, so this is
 * capped.
 *
 * Take them from the END of the roadmap. Phases run foundation-first, so the
 * last milestones are the deepest, and a deep skill's prerequisite closure
 * already contains the shallow ones: expanding "CNN" pulls in deep learning,
 * neural networks, ML, Python and the maths underneath it. Taking the first N
 * instead drops the learner's actual destination off their own graph.
 *
 * Falls back to the widest gaps so the tab is never empty for someone without a
 * generated path yet.
 */
export function pickExpandSlugs(
  roadmapSlugs: string[],
  proficiencies: GraphProficiency[],
  limit = 6,
): string[] {
  const fromRoadmap = [...new Set(roadmapSlugs.filter(Boolean))];
  if (fromRoadmap.length) return fromRoadmap.slice(-limit).reverse();
  // Widest gap first: those are the skills worth showing the route to.
  const gap = (s: GraphProficiency) => (s.target ?? s.current) - s.current;
  return [...proficiencies]
    .sort((a, b) => gap(b) - gap(a))
    .slice(0, limit)
    .map((s) => s.slug);
}
