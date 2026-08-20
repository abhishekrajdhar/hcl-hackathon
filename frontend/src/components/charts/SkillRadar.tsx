"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { SkillDatum } from "@/lib/dashboard-data";

export function SkillRadar({ skills }: { skills: SkillDatum[] }) {
  const data = skills.map((s) => ({
    skill: s.name.length > 14 ? s.name.slice(0, 12) + "…" : s.name,
    current: Math.round(s.current * 100),
    target: Math.round(s.target * 100),
  }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis
            dataKey="skill"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
          />
          <Radar
            name="Target"
            dataKey="target"
            stroke="var(--accent)"
            fill="var(--accent)"
            fillOpacity={0.08}
          />
          <Radar
            name="Current"
            dataKey="current"
            stroke="var(--brand)"
            fill="var(--brand)"
            fillOpacity={0.35}
          />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              color: "var(--fg)",
              fontSize: 12,
            }}
            formatter={(v: number, n: string) => [`${v}%`, n]}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
