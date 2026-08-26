"use client";

// Live connectivity between this browser and the backend, per subsystem.
//
// Every row probes a real endpoint and reports what actually came back. A 401
// or 403 still counts as reachable — the service answered, the caller just is
// not allowed — because the question this panel answers is "is the backend
// connected", not "am I an admin".

import { useCallback, useEffect, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { IconActivity } from "@/components/ui/icons";
import { getToken, systemApi } from "@/lib/api";
import type { HealthReport } from "@/lib/types";

/** One probe per subsystem, chosen to be read-only and cheap. */
const PROBES = [
  { name: "Auth", path: "/api/v1/auth/me" },
  { name: "Profile", path: "/api/v1/profile" },
  { name: "Skill graph", path: "/api/v1/skills?limit=1" },
  { name: "Catalogue", path: "/api/v1/resources?limit=1" },
  { name: "Paths", path: "/api/v1/learning-paths?limit=1" },
  { name: "Assessments", path: "/api/v1/assessments?limit=1" },
  { name: "Progress", path: "/api/v1/progress/summary" },
  { name: "Recommendations", path: "/api/v1/recommendations?limit=1" },
  { name: "Coach", path: "/api/v1/chat/conversations?limit=1" },
] as const;

interface Row {
  name: string;
  status: number;
  latencyMs: number;
  ok: boolean;
}

export function SystemStatus() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [checking, setChecking] = useState(false);

  const run = useCallback(async () => {
    setChecking(true);
    const token = getToken();
    const [probes, report] = await Promise.all([
      Promise.all(
        PROBES.map(async (p) => {
          const r = await systemApi.probe(p.path, token);
          return { name: p.name, status: r.status, latencyMs: r.latencyMs, ok: r.ok };
        }),
      ),
      systemApi.health().catch(() => null),
    ]);
    setRows(probes);
    setHealth(report);
    setChecking(false);
  }, []);

  useEffect(() => {
    void run();
  }, [run]);

  const reachable = rows?.filter((r) => r.ok).length ?? 0;
  const total = rows?.length ?? PROBES.length;
  const allUp = rows != null && reachable === total;

  return (
    <Card>
      <CardHeader
        title="System"
        subtitle={
          rows == null
            ? "Checking connectivity…"
            : allUp
              ? `Backend reachable — ${reachable}/${total} subsystems answering`
              : `${total - reachable} of ${total} subsystems not answering`
        }
        icon={<IconActivity className="h-4 w-4" />}
        action={
          <button
            onClick={run}
            disabled={checking}
            className="label-meta transition-colors hover:text-cyan disabled:opacity-40"
          >
            {checking ? "Checking…" : "Re-check"}
          </button>
        }
      />
      <CardBody className="space-y-4">
        {health?.providers && (health.providers.llm === "mock" || health.providers.embeddings === "mock") && (
          <div className="flex items-start gap-2.5 border-l-2 border-amber py-1.5 pl-3">
            <p className="text-[12px] leading-relaxed text-text-2">
              <span className="font-medium text-amber">AI is running on the deterministic
              fallback</span>{" "}
              (LLM: {health.providers.llm}, embeddings: {health.providers.embeddings}).
              Interviews, career advice and coach replies come from curated rules, not a
              model. To go live:{" "}
              <code className="text-[11px] text-text">
                export OPENAI_API_KEY=sk-… && ./scripts/use-openai.sh
              </code>
            </p>
          </div>
        )}

        {health && (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <Meta label="API" value={`${health.app} ${health.version}`} />
            <Meta label="Environment" value={health.environment} />
            {health.providers && (
              <>
                <Meta
                  label="LLM"
                  value={health.providers.llm}
                  tone={health.providers.llm === "mock" ? "bad" : "ok"}
                />
                <Meta
                  label="Embeddings"
                  value={health.providers.embeddings}
                  tone={health.providers.embeddings === "mock" ? "bad" : "ok"}
                />
              </>
            )}
            {Object.entries(health.components).map(([name, c]) => (
              <Meta
                key={name}
                label={name}
                value={c.latency_ms != null ? `${c.status} · ${c.latency_ms}ms` : c.status}
                tone={c.status === "ok" ? "ok" : "bad"}
              />
            ))}
          </div>
        )}

        <div className="grid gap-px border-t border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
          {rows == null
            ? PROBES.map((p) => (
                <div key={p.name} className="flex items-center justify-between bg-panel px-3.5 py-2.5">
                  <span className="text-[12px] text-text-3">{p.name}</span>
                  <span className="label-meta animate-pulse">probing…</span>
                </div>
              ))
            : rows.map((r) => (
              <div key={r.name} className="flex items-center justify-between bg-panel px-3.5 py-2.5">
                <span className="flex items-center gap-2.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${r.ok ? "bg-teal" : "bg-coral"}`}
                    style={r.ok ? { boxShadow: "0 0 6px var(--teal)" } : undefined}
                  />
                  <span className="text-[12px] text-text">{r.name}</span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="readout text-[11px] text-text-3">{r.latencyMs}ms</span>
                  <Badge tone={r.ok ? "accent" : "danger"}>{r.status || "ERR"}</Badge>
                </span>
              </div>
            ))}
        </div>

        <p className="label-meta">
          401 / 403 count as reachable — the service answered.
        </p>
      </CardBody>
    </Card>
  );
}

function Meta({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "bad";
}) {
  return (
    <span className="flex items-baseline gap-2">
      <span className="label-meta">{label}</span>
      <span
        className={`readout text-[12px] ${
          tone === "ok" ? "text-teal" : tone === "bad" ? "text-coral" : "text-text"
        }`}
      >
        {value}
      </span>
    </span>
  );
}
