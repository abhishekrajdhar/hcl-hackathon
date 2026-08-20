"use client";

import { ProgressBar } from "@/components/ui/ProgressBar";
import type { SkillDatum } from "@/lib/dashboard-data";

export function SkillBars({ skills }: { skills: SkillDatum[] }) {
  return (
    <ul className="space-y-3.5">
      {skills.map((s) => {
        const tone =
          s.current >= 0.8 ? "success" : s.current >= 0.5 ? "brand" : "warning";
        return (
          <li key={s.slug || s.name}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="font-medium">{s.name}</span>
              <span className="tabular-nums text-muted">
                {Math.round(s.current * 100)}%
                <span className="ml-1 text-[11px] opacity-70">
                  / {Math.round(s.target * 100)}%
                </span>
              </span>
            </div>
            <ProgressBar value={s.current} target={s.target} tone={tone} />
          </li>
        );
      })}
    </ul>
  );
}
