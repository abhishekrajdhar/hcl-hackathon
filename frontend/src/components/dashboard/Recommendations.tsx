import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconBook, IconClock, IconArrow, IconExternal, IconLock } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import type { DashboardData, RecommendationDatum } from "@/lib/dashboard-data";
import { difficultyLabel } from "@/lib/format";

function RecCard({ r }: { r: RecommendationDatum }) {
  return (
    <article
      className={clsx(
        "flex flex-col rounded-xl border border-border bg-surface-2/50 p-4",
        !r.isReady && "opacity-80",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold">{r.title}</h4>
          <p className="text-[11px] text-muted">{r.provider}</p>
        </div>
        {r.isReady ? (
          <Badge tone="brand">{r.skill}</Badge>
        ) : (
          <Badge tone="warning"><IconLock className="h-3 w-3" /> locked</Badge>
        )}
      </div>

      <div className="mt-2.5 flex flex-wrap gap-1.5 text-[11px]">
        <Badge tone="accent">{r.type}</Badge>
        <Badge tone="neutral">{difficultyLabel(r.difficulty)}</Badge>
        <Badge tone="neutral">
          <IconClock className="h-3 w-3" /> {r.estimatedHours}h
        </Badge>
      </div>

      <p className="mt-2.5 line-clamp-3 text-xs text-muted">
        <span className="font-medium text-fg/80">Why: </span>
        {r.reason}
      </p>

      <div className="mt-3 flex items-center justify-between pt-1">
        <span className="text-[11px] text-muted">match {Math.round(r.score * 100)}%</span>
        <div className="flex gap-1.5">
          <a href={r.url} target="_blank" rel="noreferrer">
            <Button variant="ghost" size="sm">
              <IconExternal className="h-3.5 w-3.5" />
            </Button>
          </a>
          <Button size="sm" variant={r.isReady ? "primary" : "soft"}>
            {r.cta} <IconArrow className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </article>
  );
}

export function Recommendations({ data }: { data: DashboardData }) {
  return (
    <Card>
      <CardHeader
        title="Recommended Resources"
        subtitle="Chosen for your gaps and current stage"
        icon={<IconBook />}
      />
      <CardBody>
        {data.recommendations.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {data.recommendations.map((r) => (
              <RecCard key={r.id} r={r} />
            ))}
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-muted">
            No recommendations yet. Set a goal to generate your personalized list.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
