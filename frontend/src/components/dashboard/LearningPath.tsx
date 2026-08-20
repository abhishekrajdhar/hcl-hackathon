import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { IconPath, IconCheck, IconLayers } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import type { DashboardData, PhaseDatum } from "@/lib/dashboard-data";
import { hoursFromMinutes } from "@/lib/format";

function phaseTone(status: PhaseDatum["status"]) {
  return status === "done"
    ? { ring: "border-success bg-success text-white", tone: "success" as const }
    : status === "active"
      ? { ring: "border-brand bg-brand text-white", tone: "brand" as const }
      : { ring: "border-border bg-surface text-muted", tone: "neutral" as const };
}

export function LearningPath({ data }: { data: DashboardData }) {
  return (
    <Card>
      <CardHeader
        title="Current Learning Path"
        subtitle={`${data.phases.length} phases · ~${data.stats.totalPlannedHours}h`}
        icon={<IconPath />}
        action={<Badge tone="brand"><IconLayers className="h-3.5 w-3.5" /> Roadmap</Badge>}
      />
      <CardBody>
        <ol className="relative space-y-5 pl-2">
          {data.phases.map((phase, i) => {
            const t = phaseTone(phase.status);
            const last = i === data.phases.length - 1;
            return (
              <li key={phase.index} className="relative pl-8">
                {!last && (
                  <span className="absolute left-[11px] top-7 h-[calc(100%+4px)] w-px bg-border" />
                )}
                <span
                  className={clsx(
                    "absolute left-0 top-0 grid h-6 w-6 place-items-center rounded-full border-2 text-[11px] font-bold",
                    t.ring,
                  )}
                >
                  {phase.status === "done" ? <IconCheck className="h-3.5 w-3.5" /> : i + 1}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="text-sm font-semibold">{phase.title}</h4>
                  {phase.isCapstone && <Badge tone="accent">Capstone</Badge>}
                  {phase.status === "active" && <Badge tone="brand">In progress</Badge>}
                  <span className="text-xs text-muted">· {hoursFromMinutes(phase.estimatedMinutes)}</span>
                </div>
                <p className="mt-0.5 text-xs text-muted">{phase.objective}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {phase.milestones.map((m) => (
                    <span
                      key={m.title}
                      className={clsx(
                        "rounded-lg border px-2 py-0.5 text-[11px]",
                        m.status === "completed"
                          ? "border-success/40 bg-success/10 text-success"
                          : m.status === "in_progress"
                            ? "border-accent/40 bg-accent/10 text-accent"
                            : m.status === "available"
                              ? "border-brand/40 bg-brand-soft text-brand"
                              : "border-border bg-surface-2 text-muted",
                      )}
                    >
                      {m.title}
                    </span>
                  ))}
                </div>
              </li>
            );
          })}
        </ol>
      </CardBody>
    </Card>
  );
}
