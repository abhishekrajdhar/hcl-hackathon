"use client";

import { useMemo, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { IconChart } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";
import { useKnowledgeGraph } from "@/lib/hooks/useKnowledgeGraph";
import { STATE_ORDER, STATE_COLOR, STATE_LABEL, type MasteryState } from "@/lib/graph-view";
import { GraphCanvas, Legend } from "./GraphCanvas";
import { SkillDetailPanel } from "./SkillDetailPanel";

const ZOOMS = [0.75, 1, 1.25];

/** The knowledge-graph tab: the prerequisite DAG, coloured by mastery. */
export function KnowledgeGraph({ data }: { data: DashboardData }) {
  const { graph, loading, isDemo } = useKnowledgeGraph(data, data.isDemo);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  const selected = useMemo(
    () => graph.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.nodes, selectedId],
  );

  const counts = useMemo(() => {
    const c: Record<MasteryState, number> = {
      mastered: 0,
      learning: 0,
      weak: 0,
      not_started: 0,
    };
    for (const n of graph.nodes) c[n.state] += 1;
    return c;
  }, [graph.nodes]);

  return (
    <Card>
      <CardHeader
        title="Knowledge Graph"
        subtitle={`Every skill between you and “${graph.goal}” — prerequisites above, what they unlock below`}
        icon={<IconChart />}
        action={
          <div className="flex items-center gap-1">
            {ZOOMS.map((z) => (
              <button
                key={z}
                onClick={() => setZoom(z)}
                aria-pressed={zoom === z}
                className={
                  zoom === z
                    ? "rounded-lg border border-brand bg-brand-soft px-2 py-1 text-[11px] text-brand"
                    : "rounded-lg border border-border px-2 py-1 text-[11px] text-muted hover:text-fg"
                }
              >
                {Math.round(z * 100)}%
              </button>
            ))}
          </div>
        }
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
              {STATE_LABEL[s]}
            </span>
          ))}
          {isDemo && <Badge tone="accent">demo graph</Badge>}
        </div>

        {loading ? (
          <Skeleton className="h-[420px] w-full" />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="min-w-0 space-y-2">
              <GraphCanvas
                model={graph}
                selectedId={selectedId}
                onSelect={setSelectedId}
                zoom={zoom}
              />
              <Legend />
            </div>
            <SkillDetailPanel
              skill={selected}
              model={graph}
              isDemo={isDemo}
              onSelect={setSelectedId}
            />
          </div>
        )}
      </CardBody>
    </Card>
  );
}
