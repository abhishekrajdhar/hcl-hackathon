import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { SkillRadar } from "@/components/charts/SkillRadar";
import { SkillBars } from "@/components/charts/SkillBars";
import { IconChart } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";

export function SkillProgress({ data }: { data: DashboardData }) {
  return (
    <Card>
      <CardHeader
        title="Skill Progress"
        subtitle="Current proficiency vs. what your goal requires"
        icon={<IconChart />}
      />
      <CardBody className="grid gap-6 lg:grid-cols-2">
        <div className="order-2 lg:order-1">
          <SkillBars skills={data.skills} />
        </div>
        <div className="order-1 lg:order-2">
          <SkillRadar skills={data.skills} />
          <div className="mt-1 flex items-center justify-center gap-4 text-[11px] text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-brand" /> Current
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-accent" /> Target
            </span>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
