"use client";

// The Learning Universe: a full-viewport world with instrumentation floating
// over it. Same GraphModel, same mastery states, same detail panel data as the
// 2D knowledge graph — this is the primary projection of it, not a widget.
//
// The AI coach drives it: when a reply names a skill that exists in the
// galaxy, that node is selected and pulsed, so "how comfortable are you with
// Linear Algebra?" physically points at Linear Algebra.

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { clsx } from "@/lib/cn";
import type { DashboardData } from "@/lib/dashboard-data";
import { STATE_COLOR, STATE_ORDER, type MasteryState } from "@/lib/graph-view";
import { titleCase } from "@/lib/format";
import { useKnowledgeGraph } from "@/lib/hooks/useKnowledgeGraph";
import { SkillDetailPanel } from "@/components/dashboard/graph/SkillDetailPanel";
import { CoachDock } from "@/components/dashboard/universe/CoachDock";
import { SceneBoundary } from "@/components/dashboard/universe/SceneBoundary";

/** Fired by the Assistant when a coach reply lands; detail is the reply text. */
export const COACH_REPLY_EVENT = "coach:reply";

// WebGL cannot render on the server; load the scene only in the browser.
const GalaxyScene = dynamic(() => import("./GalaxyScene").then((m) => m.GalaxyScene), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-panel/40" />,
});

const STATE_TERM: Record<MasteryState, string> = {
  mastered: "Mastered",
  learning: "Learning",
  weak: "Needs work",
  not_started: "In the fog",
};

export function Universe({ data }: { data: DashboardData }) {
  const { graph, proficiencies, loading, isDemo } = useKnowledgeGraph(data);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pulseIds, setPulseIds] = useState<Set<string>>(new Set());

  const selected = useMemo(
    () => graph.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.nodes, selectedId],
  );

  // Once the galaxy has nodes, keep it on screen through subsequent refreshes.
  const hasWorld = graph.nodes.length > 0;

  const counts = useMemo(() => {
    const c: Record<MasteryState, number> = { mastered: 0, learning: 0, weak: 0, not_started: 0 };
    for (const n of graph.nodes) c[n.state] += 1;
    return c;
  }, [graph.nodes]);

  // Coach → world. Longest names first so "Deep Learning" beats "Learning";
  // only skills actually in this galaxy can light up.
  useEffect(() => {
    const onReply = (e: Event) => {
      const text = (e as CustomEvent<{ text: string }>).detail?.text?.toLowerCase();
      if (!text) return;
      const mentioned = [...graph.nodes]
        .sort((a, b) => b.name.length - a.name.length)
        .filter((n) => text.includes(n.name.toLowerCase()));
      if (!mentioned.length) return;
      setSelectedId(mentioned[0].id);
      setPulseIds(new Set(mentioned.map((n) => n.id)));
    };
    window.addEventListener(COACH_REPLY_EVENT, onReply);
    return () => window.removeEventListener(COACH_REPLY_EVENT, onReply);
  }, [graph.nodes]);

  // A pulse is a moment, not a state.
  useEffect(() => {
    if (!pulseIds.size) return;
    const t = setTimeout(() => setPulseIds(new Set()), 6000);
    return () => clearTimeout(t);
  }, [pulseIds]);

  return (
    <section className="relative h-[calc(100vh-3rem)] min-h-[620px] w-full overflow-hidden">
      {/* --- the world ---------------------------------------------------- */}
      <div className="absolute inset-0">
        {/* The canvas stays mounted once there is a world to show. Swapping it
            for a placeholder on every refresh tore down the WebGL context and
            rebuilt it — which R3F cannot always survive, because it connects
            its DOM events to the canvas wrapper and that ref is briefly null
            across an unmount/remount (the "null (reading 'addEventListener')"
            crash after marking a resource complete). It also made the whole
            world blink on every reload. */}
        {hasWorld ? (
          <SceneBoundary>
            <GalaxyScene
              model={graph}
              selectedId={selectedId}
              onSelect={setSelectedId}
              pulseIds={pulseIds}
            />
          </SceneBoundary>
        ) : (
          <div className="grid h-full place-items-center">
            <p className="label-meta animate-pulse">
              {loading ? "Charting your universe…" : "No skills charted yet."}
            </p>
          </div>
        )}
      </div>

      {/* Vignette: pulls focus to the centre and gives the floating panels a
          darker ground to sit on without adding a scrim over the whole world. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 65% 60% at 50% 45%, transparent 40%, rgba(7,10,13,0.55) 100%)",
        }}
      />

      {/* --- floating instrumentation ------------------------------------- */}
      {/* Title block, upper left. */}
      <div className="pointer-events-none absolute left-5 top-5 max-w-sm lg:left-8 lg:top-7">
        <p className="label-meta text-cyan">Your journey toward</p>
        <h1 className="display mt-1.5 text-2xl font-semibold text-text lg:text-[32px]">
          {titleCase(data.role || graph.goal)}
        </h1>
        <p className="mt-2 max-w-xs text-[12px] leading-relaxed text-text-2">
          Every star is a skill on your route. Foundations sit below; your goal
          burns overhead.
        </p>
      </div>

      {/* Composition readout, lower left. Counts, not a chart. */}
      <div className="pointer-events-none absolute bottom-5 left-5 lg:bottom-7 lg:left-8">
        <p className="label-meta mb-2">Composition</p>
        <ul className="space-y-1.5">
          {STATE_ORDER.map((s) => (
            <li key={s} className="flex items-center gap-2.5">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: STATE_COLOR[s], boxShadow: `0 0 8px ${STATE_COLOR[s]}` }}
              />
              <span className="readout w-6 text-[13px] font-semibold text-text">{counts[s]}</span>
              <span className="text-[11px] text-text-2">{STATE_TERM[s]}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Controls hint, lower centre. */}
      <p className="label-meta pointer-events-none absolute bottom-6 left-1/2 hidden -translate-x-1/2 xl:block">
        drag to orbit · scroll to zoom · select a star
      </p>

      {/* Skill detail, right. Appears only when something is selected, so the
          world is unobstructed until the learner asks a question of it. */}
      <div
        className={clsx(
          "absolute right-4 top-4 z-20 w-[300px] transition-all duration-300 ease-out lg:right-6 lg:top-6",
          selected
            ? "pointer-events-auto translate-x-0 opacity-100"
            : "pointer-events-none translate-x-4 opacity-0",
        )}
      >
        <div className="hud hud-bracket hud-raised max-h-[calc(100vh-13rem)] overflow-y-auto">
          <SkillDetailPanel
            skill={selected}
            model={graph}
            proficiencies={proficiencies}
            isDemo={isDemo}
            onSelect={setSelectedId}
            bare
          />
        </div>
      </div>

      {/* AI coach, lower right. */}
      <div className="absolute bottom-5 right-4 z-20 lg:bottom-7 lg:right-6">
        <CoachDock data={data} onFocusSkill={(name) => focusByName(graph.nodes, name, setSelectedId)} />
      </div>

      {isDemo && hasWorld && (
        <span className="label-meta pointer-events-none absolute right-6 top-[calc(100%-2.2rem)] hidden text-amber lg:block">
          demo universe
        </span>
      )}
    </section>
  );
}

/** Select a node by (case-insensitive) name — used by the coach dock. */
function focusByName(
  nodes: { id: string; name: string }[],
  name: string,
  select: (id: string | null) => void,
): void {
  const hit = nodes.find((n) => n.name.toLowerCase() === name.toLowerCase());
  if (hit) select(hit.id);
}

export { Skeleton };
