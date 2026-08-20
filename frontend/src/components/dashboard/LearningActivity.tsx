import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { ActivityChart } from "@/components/charts/ActivityChart";
import { IconActivity } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";

export function LearningActivity({ data }: { data: DashboardData }) {
  const totalMin = data.activity.reduce((a, d) => a + d.minutes, 0);
  const activeDays = data.activity.filter((d) => d.minutes > 0).length;
  return (
    <Card>
      <CardHeader
        title="Learning Activity"
        subtitle={`${Math.round(totalMin / 60)}h over the last 14 days · ${activeDays} active days`}
        icon={<IconActivity />}
      />
      <CardBody>
        <ActivityChart data={data.activity} />
      </CardBody>
    </Card>
  );
}
