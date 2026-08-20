import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { IconClipboard } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";
import { pct, relativeDate, titleCase } from "@/lib/format";

const masteryTone = (m: string) =>
  m === "strong_mastery" ? "success" : m === "good_understanding" ? "brand" : m === "partial_understanding" ? "warning" : "danger";

export function Assessments({ data }: { data: DashboardData }) {
  return (
    <Card>
      <CardHeader title="Assessments" subtitle="How your knowledge checks out" icon={<IconClipboard />} />
      <CardBody className="space-y-3">
        {data.assessments.length ? (
          data.assessments.map((a) => (
            <div key={a.id} className="rounded-xl border border-border p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">{a.title}</span>
                <Badge tone={a.passed ? "success" : "danger"}>{a.passed ? "passed" : "retry"}</Badge>
              </div>
              <div className="mt-2">
                <ProgressBar value={a.percentage} tone={a.passed ? "success" : "warning"} />
                <div className="mt-1 flex items-center justify-between text-[11px] text-muted">
                  <span className="tabular-nums">{pct(a.percentage)}</span>
                  <span className="flex items-center gap-2">
                    <Badge tone={masteryTone(a.mastery)}>{titleCase(a.mastery)}</Badge>
                    {relativeDate(a.submittedAt)}
                  </span>
                </div>
              </div>
            </div>
          ))
        ) : (
          <p className="py-8 text-center text-sm text-muted">
            No assessments taken yet. Checkpoints appear here as you complete milestones.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
