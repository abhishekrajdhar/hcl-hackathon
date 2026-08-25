// Presentation model for the skill knowledge graph, plus the pure layered-DAG
// layout that positions it. Decoupled from the API schemas: built in
// `graph-derive.ts` from the live graph, or supplied by `graph-demo.ts`.
//
// Nothing here touches the network, the clock or React — given the same nodes
// and edges it always produces the same picture, which is what makes the graph
// stable across re-renders and safe to snapshot.

/** The four states a node is painted in. */
export type MasteryState = "mastered" | "learning" | "weak" | "not_started";

// Thresholds are the backend's canonical skill-level bands
// (`app/engines/adaptive/decisions.py`) so a node's colour never disagrees with
// the adaptive engine's own view of the same number.
export const MASTERED_ABOVE = 0.8; // SKILL_SKIP_INTRO
export const WEAK_BELOW = 0.5; // SKILL_REMEDIAL

export const STATE_LABEL: Record<MasteryState, string> = {
  mastered: "Mastered",
  learning: "Learning",
  weak: "Weak",
  not_started: "Not started",
};

/**
 * The world's colour semantics, as CSS custom properties so the 2D graph, the
 * HUD and the 3D scene cannot drift apart. Amber marks achievement, cyan marks
 * what is live, coral asks for attention, steel is the fog of the undiscovered.
 */
export const STATE_COLOR: Record<MasteryState, string> = {
  mastered: "var(--state-mastered)",
  learning: "var(--state-active)",
  weak: "var(--state-weak)",
  not_started: "var(--state-locked)",
};

export const STATE_ORDER: MasteryState[] = ["mastered", "learning", "weak", "not_started"];

/**
 * Classify a proficiency into one of the four painted states.
 *
 * A skill counts as mastered when it clears the band OR already meets whatever
 * the goal requires of it — a goal asking for 0.6 is satisfied at 0.6, and
 * showing that as "still learning" would be wrong.
 */
export function masteryState(
  proficiency: number | null | undefined,
  required?: number | null,
): MasteryState {
  if (proficiency == null || proficiency <= 0) return "not_started";
  if (required != null && required > 0 && proficiency >= required) return "mastered";
  if (proficiency > MASTERED_ABOVE) return "mastered";
  if (proficiency < WEAK_BELOW) return "weak";
  return "learning";
}

/** hard prerequisites are drawn solid; everything softer is dashed. */
export type EdgeKind = "hard_prerequisite" | "soft_prerequisite" | "recommended" | "related";

export interface GraphNode {
  id: string;
  slug: string;
  name: string;
  /** 1..5, intrinsic to the skill. */
  difficulty: number;
  category: string | null;
  /** True when the learner's goal asks for this skill directly. */
  isTarget: boolean;
  proficiency: number | null;
  required: number | null;
  state: MasteryState;
}

/**
 * One prerequisite relation. Direction is explicit on purpose: the backend
 * stores "source requires prerequisite", and in a learning graph the
 * prerequisite is what you reach first — so it is drawn ABOVE its dependent.
 */
export interface GraphEdge {
  prerequisiteId: string;
  dependentId: string;
  kind: EdgeKind;
  strength: number;
  rationale: string | null;
}

export interface GraphModel {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** What the graph was built around, for the empty/summary copy. */
  goal: string;
}

// --- layout ----------------------------------------------------------------

export const NODE_W = 150;
export const NODE_H = 46;
const COL_GAP = 22;
const ROW_GAP = 74;
const PAD_X = 28;
const PAD_Y = 28;

export interface PositionedNode extends GraphNode {
  row: number;
  col: number;
  x: number; // top-left
  y: number;
  cx: number; // centre
  cy: number;
}

export interface PositionedEdge extends GraphEdge {
  /** Cubic bezier from the bottom of the prerequisite to the top of its dependent. */
  path: string;
}

export interface GraphLayout {
  nodes: PositionedNode[];
  edges: PositionedEdge[];
  byId: Map<string, PositionedNode>;
  width: number;
  height: number;
  rowCount: number;
}

/**
 * Longest-path ranking: a node sits one row below its deepest prerequisite, so
 * an edge never points upwards and a skill is never drawn above something it
 * depends on. Cycles cannot occur (the backend refuses them at write time), but
 * the visit cap keeps this total even if a malformed graph ever arrived.
 */
export function rankNodes(nodes: GraphNode[], edges: GraphEdge[]): Map<string, number> {
  const ids = new Set(nodes.map((n) => n.id));
  const parents = new Map<string, string[]>();
  for (const id of ids) parents.set(id, []);
  for (const e of edges) {
    if (!ids.has(e.prerequisiteId) || !ids.has(e.dependentId)) continue;
    parents.get(e.dependentId)!.push(e.prerequisiteId);
  }

  const rank = new Map<string, number>();
  const visiting = new Set<string>();

  const resolve = (id: string, depth: number): number => {
    const cached = rank.get(id);
    if (cached != null) return cached;
    if (visiting.has(id) || depth > ids.size) return 0;
    visiting.add(id);
    let r = 0;
    for (const p of parents.get(id) ?? []) r = Math.max(r, resolve(p, depth + 1) + 1);
    visiting.delete(id);
    rank.set(id, r);
    return r;
  };

  for (const id of ids) resolve(id, 0);
  return rank;
}

/**
 * Order each row so edges cross as little as possible: repeatedly place a node
 * near the average position of its neighbours in the adjacent row (the
 * barycentre heuristic), alternating sweeps down and up. Four passes is well
 * past the point of visible improvement on graphs this size.
 *
 * Ties break on name, so the result is stable rather than dependent on input
 * order.
 */
function orderRows(rows: GraphNode[][], edges: GraphEdge[]): GraphNode[][] {
  const ordered = rows.map((r) => [...r].sort((a, b) => a.name.localeCompare(b.name)));

  const barycentre = (row: GraphNode[], neighbours: GraphNode[], pick: (e: GraphEdge) => [string, string]) => {
    const pos = new Map<string, number>();
    row.forEach((n, i) => pos.set(n.id, i));
    const scored = neighbours.map((n, i) => {
      const linked: number[] = [];
      for (const e of edges) {
        const [from, to] = pick(e);
        if (to === n.id && pos.has(from)) linked.push(pos.get(from)!);
      }
      const mean = linked.length ? linked.reduce((a, b) => a + b, 0) / linked.length : i;
      return { n, mean, i };
    });
    scored.sort((a, b) => a.mean - b.mean || a.n.name.localeCompare(b.n.name));
    return scored.map((s) => s.n);
  };

  for (let pass = 0; pass < 4; pass++) {
    for (let r = 1; r < ordered.length; r++) {
      ordered[r] = barycentre(ordered[r - 1], ordered[r], (e) => [e.prerequisiteId, e.dependentId]);
    }
    for (let r = ordered.length - 2; r >= 0; r--) {
      ordered[r] = barycentre(ordered[r + 1], ordered[r], (e) => [e.dependentId, e.prerequisiteId]);
    }
  }
  return ordered;
}

/** Position every node and route every edge. Pure and deterministic. */
export function layoutGraph(model: GraphModel): GraphLayout {
  const { nodes, edges } = model;
  if (!nodes.length) {
    return { nodes: [], edges: [], byId: new Map(), width: 0, height: 0, rowCount: 0 };
  }

  const rank = rankNodes(nodes, edges);
  const rowCount = Math.max(...nodes.map((n) => rank.get(n.id) ?? 0)) + 1;
  const rows: GraphNode[][] = Array.from({ length: rowCount }, () => []);
  for (const n of nodes) rows[rank.get(n.id) ?? 0].push(n);

  const ordered = orderRows(rows, edges);
  const widest = Math.max(...ordered.map((r) => r.length));
  const contentW = widest * NODE_W + (widest - 1) * COL_GAP;

  const positioned: PositionedNode[] = [];
  ordered.forEach((row, r) => {
    const rowW = row.length * NODE_W + (row.length - 1) * COL_GAP;
    const startX = PAD_X + (contentW - rowW) / 2;
    row.forEach((n, c) => {
      const x = startX + c * (NODE_W + COL_GAP);
      const y = PAD_Y + r * (NODE_H + ROW_GAP);
      positioned.push({ ...n, row: r, col: c, x, y, cx: x + NODE_W / 2, cy: y + NODE_H / 2 });
    });
  });

  const byId = new Map(positioned.map((n) => [n.id, n]));

  const routed: PositionedEdge[] = [];
  for (const e of edges) {
    const from = byId.get(e.prerequisiteId);
    const to = byId.get(e.dependentId);
    if (!from || !to) continue; // edge into a skill outside this view
    const x1 = from.cx;
    const y1 = from.y + NODE_H;
    const x2 = to.cx;
    const y2 = to.y;
    const bend = Math.max(18, (y2 - y1) * 0.45);
    routed.push({ ...e, path: `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}` });
  }

  return {
    nodes: positioned,
    edges: routed,
    byId,
    width: contentW + PAD_X * 2,
    height: PAD_Y * 2 + rowCount * NODE_H + (rowCount - 1) * ROW_GAP,
    rowCount,
  };
}

// --- relations used by the detail panel -------------------------------------

/** Direct prerequisites of a skill: what must come before it. */
export function directPrerequisites(id: string, model: GraphModel): GraphNode[] {
  const byId = new Map(model.nodes.map((n) => [n.id, n]));
  return model.edges
    .filter((e) => e.dependentId === id)
    .map((e) => byId.get(e.prerequisiteId))
    .filter((n): n is GraphNode => Boolean(n));
}

/** Skills that directly require this one: what it opens up. */
export function directDependents(id: string, model: GraphModel): GraphNode[] {
  const byId = new Map(model.nodes.map((n) => [n.id, n]));
  return model.edges
    .filter((e) => e.prerequisiteId === id)
    .map((e) => byId.get(e.dependentId))
    .filter((n): n is GraphNode => Boolean(n));
}

/** Every skill reachable in one direction — used to highlight a selection. */
export function transitive(
  id: string,
  model: GraphModel,
  direction: "up" | "down",
): Set<string> {
  const out = new Set<string>();
  const step = direction === "up" ? directPrerequisites : directDependents;
  const walk = (current: string, depth: number) => {
    if (depth > model.nodes.length) return;
    for (const n of step(current, model)) {
      if (out.has(n.id)) continue;
      out.add(n.id);
      walk(n.id, depth + 1);
    }
  };
  walk(id, 0);
  return out;
}

/** The edge that connects two skills, if any (carries the backend rationale). */
export function edgeBetween(
  prerequisiteId: string,
  dependentId: string,
  model: GraphModel,
): GraphEdge | null {
  return (
    model.edges.find(
      (e) => e.prerequisiteId === prerequisiteId && e.dependentId === dependentId,
    ) ?? null
  );
}
