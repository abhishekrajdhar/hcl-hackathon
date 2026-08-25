// Pure 3D layout for the Learning Universe.
//
// The galaxy is the SAME GraphModel the 2D knowledge graph renders — one
// source of truth, two projections. Prerequisite rank becomes altitude
// (foundations at the bottom, the goal overhead), and each rank's skills sit
// on a ring around the axis, ordered by the same barycentre pass the 2D view
// uses so related skills stay near each other. Pure and deterministic: same
// graph in, same universe out — no randomness, no clock.

import { layoutGraph, type GraphEdge, type GraphModel, type GraphNode } from "@/lib/graph-view";

export type Vec3 = [number, number, number];

export interface GalaxyNode extends GraphNode {
  position: Vec3;
  /** Sphere radius. Goal skills are landmarks; the rest are moons. */
  radius: number;
}

export interface GalaxyEdge extends GraphEdge {
  from: Vec3;
  to: Vec3;
}

export interface GalaxyLayout {
  nodes: GalaxyNode[];
  edges: GalaxyEdge[];
  byId: Map<string, GalaxyNode>;
  /** Vertical extent, for framing the camera. */
  height: number;
  /** Widest ring radius, for framing the camera. */
  spread: number;
}

const LEVEL_GAP = 2.6; // vertical distance between prerequisite ranks
const RING_BASE = 1.6; // ring radius for a two-node rank
const RING_PER_NODE = 0.72; // extra radius per node sharing a rank
const PHASE_STEP = 0.9; // radians each rank's ring is rotated vs the one below

export function layoutGalaxy(model: GraphModel): GalaxyLayout {
  // Reuse the 2D solver for rank + within-rank order; discard its pixels.
  const flat = layoutGraph(model);
  if (!flat.nodes.length) {
    return { nodes: [], edges: [], byId: new Map(), height: 0, spread: 0 };
  }

  const rows = new Map<number, typeof flat.nodes>();
  for (const n of flat.nodes) {
    const row = rows.get(n.row) ?? [];
    row.push(n);
    rows.set(n.row, row);
  }

  const nodes: GalaxyNode[] = [];
  let spread = 0;
  for (const [row, members] of rows) {
    // Foundations (rank 0) at the bottom; the deepest skills — the goal —
    // overhead, so learning literally reads as ascending.
    const y = row * LEVEL_GAP;
    const count = members.length;
    // A lone skill on a rank still orbits slightly off-axis; with the phase
    // step below, successive lone ranks trace a helix instead of a flat pole.
    const ring = count === 1 ? 0.9 : RING_BASE + RING_PER_NODE * (count - 2);
    spread = Math.max(spread, ring);
    for (const n of members) {
      const angle = (n.col / count) * Math.PI * 2 + row * PHASE_STEP;
      const { row: _r, col: _c, x: _x, y: _y, cx: _cx, cy: _cy, ...core } = n;
      nodes.push({
        ...core,
        position: [Math.cos(angle) * ring, y, Math.sin(angle) * ring],
        radius: n.isTarget ? 0.52 : 0.34,
      });
    }
  }

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges: GalaxyEdge[] = [];
  for (const e of model.edges) {
    const from = byId.get(e.prerequisiteId);
    const to = byId.get(e.dependentId);
    if (!from || !to) continue;
    edges.push({ ...e, from: from.position, to: to.position });
  }

  const maxRow = Math.max(...flat.nodes.map((n) => n.row));
  return { nodes, edges, byId, height: maxRow * LEVEL_GAP, spread };
}
