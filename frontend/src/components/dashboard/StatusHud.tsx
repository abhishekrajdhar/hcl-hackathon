"use client";

// The top strip's live readouts. Instrument values, not dashboard cards: a
// label above a number, hairline separators, no borders or fills.
//
// Every figure is derived from real learner data — XP and level are a
// deterministic function of completed items and assessment performance, not a
// separate score the app invents and stores.

import type { DashboardData } from "@/lib/dashboard-data";
import { titleCase } from "@/lib/format";
import { levelFromData, xpFromData } from "@/lib/xp";

export function StatusHud({ data }: { data: DashboardData }) {
  const xp = xpFromData(data);
  const level = levelFromData(xp);

  return (
    <div className="flex items-center gap-5 overflow-x-auto">
      <Readout label="Goal" value={data.role ? titleCase(data.role) : "—"} accent />
      <Divider />
      <Readout label="Level" value={String(level.level)} />
      <Divider />
      <Readout label="XP" value={xp.toLocaleString()} sub={`/ ${level.nextAt.toLocaleString()}`} />
      <Divider />
      <Readout label="Skills" value={String(data.stats.skillsTracked)} />
      <Divider />
      <Readout
        label="Progress"
        value={`${Math.round(data.progressPct)}%`}
        sub={data.pace.label === "unknown" ? undefined : data.pace.label.replace("_", " ")}
      />
    </div>
  );
}

function Divider() {
  return <span aria-hidden className="h-4 w-px shrink-0 bg-line" />;
}

function Readout({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className="flex min-w-0 shrink-0 items-baseline gap-2">
      <span className="label-meta">{label}</span>
      <span
        className={`readout truncate text-[12px] font-semibold ${accent ? "text-cyan" : "text-text"}`}
      >
        {value}
      </span>
      {sub && <span className="readout text-[10px] text-text-3">{sub}</span>}
    </div>
  );
}
