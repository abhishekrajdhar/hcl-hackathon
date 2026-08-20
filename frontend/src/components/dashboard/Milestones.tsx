import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusDot } from "@/components/ui/StatusDot";
import { Badge } from "@/components/ui/Badge";
import { IconFlag, IconLock, IconCheck, IconClock } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import type { DashboardData } from "@/lib/dashboard-data";
import { hoursFromMinutes } from "@/lib/format";

export function Milestones({ data }: { data: DashboardData }) {
  const ms = data.milestones.filter((m) => !m.isCapstone).slice(0, 6);
  return (
    <Card>
      <CardHeader title="Milestones" subtitle="Skills to master, in order" icon={<IconFlag />} />
      <CardBody className="space-y-3">
        {ms.map((m) => {
          const done = m.status === "completed";
          const locked = m.status === "locked";
          const active = m.status === "in_progress";
          return (
            <div
              key={`${m.phaseIndex}-${m.title}`}
              className={clsx(
                "rounded-xl border p-3.5",
                active ? "border-brand/40 bg-brand-soft/40" : "border-border",
                locked && "opacity-70",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={clsx(
                      "grid h-6 w-6 place-items-center rounded-lg",
                      done ? "bg-success/15 text-success" : locked ? "bg-surface-2 text-muted" : "bg-brand-soft text-brand",
                    )}
                  >
                    {done ? <IconCheck className="h-3.5 w-3.5" /> : locked ? <IconLock className="h-3.5 w-3.5" /> : <IconFlag className="h-3.5 w-3.5" />}
                  </span>
                  <span className="text-sm font-medium">{m.title}</span>
                  <span className="text-[11px] text-muted">· {m.phaseTitle}</span>
                </div>
                <StatusDot status={m.status} />
              </div>
              <div className="mt-2.5">
                <ProgressBar
                  value={m.current}
                  target={m.required}
                  tone={done ? "success" : active ? "accent" : "brand"}
                />
                <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                  <span>
                    {Math.round(m.current * 100)}% → target {Math.round(m.required * 100)}%
                  </span>
                  <span className="inline-flex items-center gap-1">
                    {m.hasAssessment && <Badge tone="neutral">checkpoint</Badge>}
                    <IconClock className="h-3 w-3" /> {hoursFromMinutes(m.estimatedMinutes)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </CardBody>
    </Card>
  );
}
