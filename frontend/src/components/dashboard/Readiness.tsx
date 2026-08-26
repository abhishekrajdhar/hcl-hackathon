"use client";

// Career readiness: how close the learner is to the target role, as the
// composite of evidenced dimensions the backend derives on demand. Renders
// nothing in demo mode or before a path exists — a readiness figure with no
// evidence behind it would be an invention.

import { useEffect, useState } from "react";
import { getToken, meApi } from "@/lib/api";
import type { ReadinessReport } from "@/lib/api/me";

const WEAKEST_COPY: Record<string, string> = {
  knowledge: "your remaining skill gaps are the biggest drag — keep working the path",
  assessments: "assessment evidence is your weakest dimension — take a checkpoint",
  projects: "project work is your weakest dimension — ship one of the planned projects",
  momentum: "pace is your weakest dimension — smaller, regular sessions move it",
};

export function Readiness({ isDemo }: { isDemo: boolean }) {
  const [report, setReport] = useState<ReadinessReport | null>(null);

  useEffect(() => {
    if (isDemo || !getToken()) return;
    meApi
      .getReadiness()
      .then(setReport)
      .catch(() => setReport(null)); // no active path yet — show nothing
  }, [isDemo]);

  if (!report) return null;
  const pct = Math.round(report.overall * 100);

  return (
    <div className="border-t border-line px-5 py-4">
      <div className="flex items-baseline justify-between gap-4">
        <span className="label-meta">Career readiness</span>
        <span className="readout display text-[22px] font-semibold text-cyan">{pct}%</span>
      </div>

      <div className="mt-2 h-1 overflow-hidden bg-panel-3">
        <div className="h-full bg-cyan" style={{ width: `${pct}%` }} />
      </div>

      <div className="mt-4 grid gap-x-8 gap-y-2 sm:grid-cols-2">
        {report.dimensions.map((d) => (
          <div key={d.key} className="flex items-center gap-3">
            <span className="w-40 shrink-0 text-[11px] text-text-2">{d.label}</span>
            {d.score == null ? (
              <span className="label-meta">{d.detail}</span>
            ) : (
              <>
                <div className="h-1 flex-1 overflow-hidden bg-panel-3">
                  <div
                    className={`h-full ${d.key === report.weakest ? "bg-coral" : "bg-teal"}`}
                    style={{ width: `${Math.round(d.score * 100)}%` }}
                  />
                </div>
                <span className="readout w-9 text-right text-[11px] text-text">
                  {Math.round(d.score * 100)}%
                </span>
              </>
            )}
          </div>
        ))}
      </div>

      {report.weakest && WEAKEST_COPY[report.weakest] && (
        <p className="mt-3 text-[11px] text-text-2">
          Right now, {WEAKEST_COPY[report.weakest]}.
        </p>
      )}
    </div>
  );
}
