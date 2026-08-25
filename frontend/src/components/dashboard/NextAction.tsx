import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { IconArrow, IconClock, IconSpark } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";
import { hoursFromMinutes } from "@/lib/format";

export function NextAction({ data }: { data: DashboardData }) {
  const next = data.nextAction;
  return (
    <Card className="overflow-hidden">
      <div className="relative flex items-center justify-between gap-4 border-l-2 border-cyan p-5">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-brand">
            <IconSpark className="h-4 w-4" /> Next action
          </div>
          {next ? (
            <>
              <h3 className="truncate text-lg font-semibold">{next.title}</h3>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                <Badge tone="brand">{next.kind}</Badge>
                <span>in {next.phase} · {next.milestone}</span>
                <span className="inline-flex items-center gap-1">
                  <IconClock className="h-3.5 w-3.5" /> {hoursFromMinutes(next.estimatedMinutes)}
                </span>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted">
              No pending step — everything available is done. Generate or continue your path.
            </p>
          )}
        </div>
        {next && (
          <Button className="shrink-0">
            Start <IconArrow className="h-4 w-4" />
          </Button>
        )}
      </div>
    </Card>
  );
}
