import { Card, CardBody } from "@/components/ui/Card";
import { ProgressRing } from "@/components/charts/ProgressRing";
import { Stat } from "@/components/ui/Stat";
import { Badge } from "@/components/ui/Badge";
import { IconTarget, IconClock, IconChart, IconClipboard } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";
import { pct } from "@/lib/format";

export function Overview({ data }: { data: DashboardData }) {
  return (
    <Card className="overflow-hidden">
      <div className="relative bg-gradient-to-br from-brand/12 via-surface to-accent/10 p-5 sm:p-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge tone="brand">
                <IconTarget className="h-3.5 w-3.5" /> Goal
              </Badge>
              <Badge tone="accent">Current: {data.currentMilestone}</Badge>
            </div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{data.goal}</h1>
            <p className="max-w-xl text-sm text-muted">
              You&apos;re building toward {data.role}. Keep going — you&apos;re making steady progress.
            </p>
          </div>
          <div className="shrink-0">
            <ProgressRing value={data.progressPct} label="overall" />
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat
            label="Milestones"
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
            hint={`of ~${data.stats.totalPlannedHours}h planned`}
            icon={<IconClock className="h-4 w-4" />}
          />
          <Stat
            label="Avg. assessment"
            value={pct(data.stats.avgAssessment)}
            hint={`${data.weeklyHours}h / week`}
            icon={<IconClipboard className="h-4 w-4" />}
          />
        </div>
      </div>
    </Card>
  );
}
