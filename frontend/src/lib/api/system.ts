// Service health. Deliberately unauthenticated and outside the /api/v1 prefix,
// which is why it bypasses the shared `request` helper.

import type { HealthReport } from "@/lib/types";

export interface ProbeResult {
  ok: boolean;
  status: number;
  latencyMs: number;
  detail?: string;
}

/** Full health report, including the database component and its latency. */
export async function health(): Promise<HealthReport> {
  const res = await fetch("/health", { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Health check failed (${res.status})`);
  return (await res.json()) as HealthReport;
}

/**
 * Time a single endpoint. Used by the System panel to show, per subsystem,
 * whether the frontend can actually reach the backend right now — a 401 or
 * 403 still counts as reachable, because the service answered.
 */
export async function probe(path: string, token: string | null): Promise<ProbeResult> {
  const started = performance.now();
  try {
    const res = await fetch(path, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return {
      ok: res.status < 500,
      status: res.status,
      latencyMs: Math.round(performance.now() - started),
    };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      latencyMs: Math.round(performance.now() - started),
      detail: e instanceof Error ? e.message : "unreachable",
    };
  }
}
