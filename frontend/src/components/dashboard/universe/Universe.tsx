"use client";

// The Learning Universe tab: the learner's skill graph as an explorable
// galaxy. Same GraphModel, same mastery states, same detail panel as the 2D
// knowledge graph — this is a projection of the real data, not a decoration.
//
// The AI mentor drives it: when a coach reply names a skill that exists in
// the galaxy, that node is selected and pulsed, so "can I ask how comfortable
// you are with Linear Algebra?" physically points at Linear Algebra.

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { IconSpark } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";
import { STATE_COLOR, STATE_LABEL, STATE_ORDER, type MasteryState } from "@/lib/graph-view";
import { useKnowledgeGraph } from "@/lib/hooks/useKnowledgeGraph";
import { SkillDetailPanel } from "@/components/dashboard/graph/SkillDetailPanel";

/** Fired by the Assistant when a coach reply lands; detail is the reply text. */
export const COACH_REPLY_EVENT = "coach:reply";

// WebGL cannot render on the server; load the scene only in the browser.
const GalaxyScene = dynamic(
  () => import("./GalaxyScene").then((m) => m.GalaxyScene),
  { ssr: false, loading: () => <Skeleton className="h-[520px] w-full" /> },
);

export function Universe({ data }: { data: DashboardData }) {
  const { graph, proficiencies, loading, isDemo } = useKnowledgeGraph(data, data.isDemo);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pulseIds, setPulseIds] = useState<Set<string>>(new Set());

  const selected = useMemo(
    () => graph.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.nodes, selectedId],
  );

  const counts = useMemo(() => {
    const c: Record<MasteryState, number> = { mastered: 0, learning: 0, weak: 0, not_started: 0 };
    for (const n of graph.nodes) c[n.state] += 1;
    return c;
  }, [graph.nodes]);

  // Mentor → universe. Longest names matched first so "Deep Learning" wins
  // over "Learning"; only skills actually in this galaxy can light up.
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

  // A pulse is a moment, not a state — let it fade.
  useEffect(() => {
    if (!pulseIds.size) return;
    const t = setTimeout(() => setPulseIds(new Set()), 6000);
    return () => clearTimeout(t);
  }, [pulseIds]);

  return (
    <Card>
      <CardHeader
        title="Learning Universe"
        subtitle={`Your route to “${graph.goal}” as a galaxy — foundations below, your goal overhead`}
        icon={<IconSpark />}
        action={isDemo ? <Badge tone="accent">demo universe</Badge> : undefined}
      />
      <CardBody className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {STATE_ORDER.map((s) => (
            <span
              key={s}
              className="flex items-center gap-1.5 rounded-lg border border-border px-2 py-1 text-[11px] text-muted"
            >
              <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLOR[s] }} />
              <span className="font-semibold text-fg">{counts[s]}</span>
              {s === "not_started" ? "In the fog" : STATE_LABEL[s]}
            </span>
          ))}
          <span className="text-[11px] text-muted">
            Drag to orbit · scroll to zoom · click a star · ask the coach and watch it point
          </span>
        </div>

        {loading ? (
          <Skeleton className="h-[520px] w-full" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="h-[520px] min-w-0 overflow-hidden rounded-xl border border-border">
              <GalaxyScene
                model={graph}
                selectedId={selectedId}
                onSelect={setSelectedId}
                pulseIds={pulseIds}
              />
            </div>
            <SkillDetailPanel
              skill={selected}
              model={graph}
              proficiencies={proficiencies}
              isDemo={isDemo}
              onSelect={setSelectedId}
            />
          </div>
        )}
      </CardBody>
    </Card>
  );
}
