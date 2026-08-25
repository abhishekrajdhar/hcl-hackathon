"use client";

import { useMemo } from "react";
import { clsx } from "@/lib/cn";
import {
  NODE_H,
  NODE_W,
  STATE_COLOR,
  layoutGraph,
  transitive,
  type GraphModel,
  type PositionedNode,
} from "@/lib/graph-view";

/**
 * The graph itself: a layered DAG in plain SVG. Prerequisites sit above the
 * skills that need them, so reading top-to-bottom is a valid learning order.
 *
 * Layout is computed by the pure helper in `graph-view.ts` and memoised on the
 * model, so hovering and selecting never re-solve it.
 */
export function GraphCanvas({
  model,
  selectedId,
  onSelect,
  zoom,
}: {
  model: GraphModel;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  zoom: number;
}) {
  const layout = useMemo(() => layoutGraph(model), [model]);

  // When something is selected, everything that is not on its route is dimmed:
  // ancestors are what it needs, descendants are what it unlocks.
  const { ancestors, descendants } = useMemo(() => {
    if (!selectedId) return { ancestors: new Set<string>(), descendants: new Set<string>() };
    return {
      ancestors: transitive(selectedId, model, "up"),
      descendants: transitive(selectedId, model, "down"),
    };
  }, [selectedId, model]);

  const inFocus = (id: string) =>
    !selectedId || id === selectedId || ancestors.has(id) || descendants.has(id);

  if (!layout.nodes.length) {
    return (
      <p className="px-5 py-10 text-center text-sm text-muted">
        No skills to plot yet — generate a learning path first.
      </p>
    );
  }

  return (
    // A deep DAG can be far taller than the card; scroll it rather than
    // letting it push the rest of the dashboard down.
    <div className="max-h-[560px] overflow-auto rounded-xl border border-border bg-surface-2/40">
      <svg
        role="img"
        aria-label={`Skill knowledge graph: ${layout.nodes.length} skills, ${layout.edges.length} prerequisite links`}
        width={layout.width * zoom}
        height={layout.height * zoom}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="block"
        onClick={() => onSelect(null)}
      >
        <defs>
          <marker
            id="kg-arrow"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 7 4 L 0 7 z" fill="currentColor" />
          </marker>
        </defs>

        {/* Edges first so nodes paint over them. */}
        <g>
          {layout.edges.map((e) => {
            const lit =
              selectedId != null &&
              (e.prerequisiteId === selectedId ||
                e.dependentId === selectedId ||
                (ancestors.has(e.prerequisiteId) && ancestors.has(e.dependentId)) ||
                (descendants.has(e.prerequisiteId) && descendants.has(e.dependentId)) ||
                (ancestors.has(e.prerequisiteId) && e.dependentId === selectedId) ||
                (e.prerequisiteId === selectedId && descendants.has(e.dependentId)));
            const dimmed = selectedId != null && !lit;
            return (
              <path
                key={`${e.prerequisiteId}->${e.dependentId}`}
                d={e.path}
                fill="none"
                stroke={lit ? "var(--brand)" : "var(--border)"}
                strokeWidth={lit ? 2 : 1.25}
                strokeDasharray={e.kind === "hard_prerequisite" ? undefined : "4 4"}
                opacity={dimmed ? 0.25 : 1}
                markerEnd="url(#kg-arrow)"
                color={lit ? "var(--brand)" : "var(--border)"}
              />
            );
          })}
        </g>

        <g>
          {layout.nodes.map((n) => (
            <Node
              key={n.id}
              node={n}
              selected={n.id === selectedId}
              dimmed={!inFocus(n.id)}
              onSelect={onSelect}
            />
          ))}
        </g>
      </svg>
    </div>
  );
}

function Node({
  node,
  selected,
  dimmed,
  onSelect,
}: {
  node: PositionedNode;
  selected: boolean;
  dimmed: boolean;
  onSelect: (id: string) => void;
}) {
  const color = STATE_COLOR[node.state];
  return (
    <g
      transform={`translate(${node.x}, ${node.y})`}
      opacity={dimmed ? 0.3 : 1}
      className="cursor-pointer"
      role="button"
      tabIndex={0}
      aria-label={`${node.name}, ${node.state.replace("_", " ")}`}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(node.id);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(node.id);
        }
      }}
    >
      <rect
        width={NODE_W}
        height={NODE_H}
        rx={12}
        fill="var(--surface)"
        stroke={selected ? "var(--brand)" : color}
        strokeWidth={selected ? 2.5 : 1.5}
      />
      {/* Status stripe — the colour key, readable without relying on hue alone. */}
      <rect width={5} height={NODE_H} rx={2.5} fill={color} />
      {node.isTarget && (
        <circle cx={NODE_W - 11} cy={11} r={4} fill="var(--brand)">
          <title>Your goal targets this skill</title>
        </circle>
      )}
      <text
        x={14}
        y={node.name.length > 22 ? 20 : 27}
        className="pointer-events-none select-none"
        fill="var(--fg)"
        fontSize="12"
        fontWeight="600"
      >
        {truncate(node.name, 20)}
      </text>
      <text
        x={14}
        y={node.name.length > 22 ? 34 : 39}
        className="pointer-events-none select-none"
        fill="var(--muted)"
        fontSize="10"
      >
        {node.proficiency == null ? "not started" : `${Math.round(node.proficiency * 100)}%`}
      </text>
    </g>
  );
}

const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export function Legend({ className }: { className?: string }) {
  const items = [
    { state: "mastered", label: "Mastered", hint: "at or above what your goal needs" },
    { state: "learning", label: "Learning", hint: "in progress" },
    { state: "weak", label: "Weak", hint: "below 50%" },
    { state: "not_started", label: "Not started", hint: "no record yet" },
  ] as const;
  return (
    <div className={clsx("flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px]", className)}>
      {items.map((i) => (
        <span key={i.state} className="flex items-center gap-1.5 text-muted" title={i.hint}>
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ background: STATE_COLOR[i.state] }}
          />
          {i.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5 text-muted" title="Hard prerequisite">
        <svg width="18" height="6" aria-hidden>
          <line x1="0" y1="3" x2="18" y2="3" stroke="var(--border)" strokeWidth="1.5" />
        </svg>
        Required
      </span>
      <span className="flex items-center gap-1.5 text-muted" title="Soft or recommended prerequisite">
        <svg width="18" height="6" aria-hidden>
          <line
            x1="0"
            y1="3"
            x2="18"
            y2="3"
            stroke="var(--border)"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
        </svg>
        Helpful
      </span>
    </div>
  );
}
