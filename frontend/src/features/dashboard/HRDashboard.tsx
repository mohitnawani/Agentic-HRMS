import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PageHeader from "@/components/PageHeader";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useHRDashboard } from "./useDashboard";

export default function HRDashboard() {
  const { data, isLoading, isError } = useHRDashboard();

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (isError || !data) return <p className="text-destructive">Failed to load dashboard.</p>;

  const deptChartData = Object.entries(data.department_breakdown).map(([name, count]) => ({ name, count }));

  return (
    <div>
      <PageHeader title="HR Dashboard" description="Org-wide headcount, attendance, and pending approvals" />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <Card tone="sage">
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Total Employees</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.total_employees}</p></CardContent>
        </Card>
        <Card tone="moss">
          <CardHeader><CardTitle className="text-sm text-muted-foreground">On Leave Today</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.on_leave_today}</p></CardContent>
        </Card>
        <Card tone="mint">
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Pending Approvals</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.pending_approvals}</p></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Employees by Department</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={deptChartData}>
              <XAxis dataKey="name" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--color-primary)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
