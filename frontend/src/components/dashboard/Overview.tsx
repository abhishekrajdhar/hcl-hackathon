import { Card, CardBody } from "@/components/ui/Card";
import { ProgressRing } from "@/components/charts/ProgressRing";
import { Stat } from "@/components/ui/Stat";
import { Badge } from "@/components/ui/Badge";
import { IconTarget, IconClock, IconChart, IconClipboard } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";
import { pct, titleCase } from "@/lib/format";

export function Overview({ data }: { data: DashboardData }) {
  return (
    <Card className="overflow-hidden">
      <div className="relative p-5 sm:p-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge tone="brand">
                <IconTarget className="h-3.5 w-3.5" /> Goal
              </Badge>
              <Badge tone="accent">Current: {data.currentMilestone}</Badge>
            </div>
            <h1 className="display text-2xl font-semibold sm:text-[28px]">{titleCase(data.goal)}</h1>
            <p className="max-w-xl text-sm text-muted">
              Your route to {titleCase(data.role)}, rebuilt every time your skills change.
            </p>
          </div>
          <div className="shrink-0">
            <ProgressRing value={data.progressPct} label="overall" />
          </div>
        </div>

        <div className="mt-7 grid grid-cols-2 divide-x divide-y divide-line border-t border-line lg:grid-cols-4 lg:divide-y-0">
          <Stat
            label="Milestones"
            tone="active"
            value={`${data.stats.itemsCompleted}/${data.stats.itemsTotal}`}
            hint="items completed"
            icon={<IconClipboard className="h-4 w-4" />}
          />
          <Stat
            label="Skills tracked"
            value={data.stats.skillsTracked}
            hint={`avg ${pct(
              data.skills.reduce((a, s) => a + s.current, 0) / Math.max(1, data.skills.length),
            )}`}
            icon={<IconChart className="h-4 w-4" />}
          />
          <Stat
            label="Time invested"
            value={`${data.stats.hoursSpent}h`}
            hint={paceHint(data)}
            icon={<IconClock className="h-4 w-4" />}
          />
          <Stat
            label="Avg. assessment"
            tone="achievement"
            value={pct(data.stats.avgAssessment)}
            hint={`${data.weeklyHours}h / week`}
            icon={<IconClipboard className="h-4 w-4" />}
          />
        </div>
      </div>
    </Card>
  );
}

/** How the learner's real tempo compares with the plan, and what it forecasts.
 *
 *  Falls back to the plain planned total until enough items are finished for
 *  the ratio to mean anything — a forecast from one data point is a guess. */
function paceHint(data: DashboardData): string {
  const { label, ratio, weeksRemaining } = data.pace;
  if (label === "unknown") return `of ~${data.stats.totalPlannedHours}h planned`;
  const tempo =
    label === "on_track"
      ? "on plan"
      : `${ratio.toFixed(1)}× ${label === "slower" ? "slower" : "faster"} than planned`;
  return weeksRemaining != null ? `${tempo} · ~${weeksRemaining}w left` : tempo;
}
