import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip,} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PageHeader from "@/components/PageHeader";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useEmployeeDashboard } from "./useDashboard";

const COLORS = ["#35704c", "#b93838", "#bd861d", "#8aa67b"];

export default function EmployeeDashboard() {
  const { data, isLoading, isError } = useEmployeeDashboard();

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (isError || !data) return <p className="text-destructive">Failed to load dashboard.</p>;

  const attendanceChartData = [
    { name: "Present", value: data.attendance_this_month.present },
    { name: "Absent", value: data.attendance_this_month.absent },
    { name: "Late", value: data.attendance_this_month.late },
    { name: "Half Day", value: data.attendance_this_month.half_day },
  ];

  return (
    <div>
      <PageHeader title="My Dashboard" description="Your attendance, leave balance, and requests" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card tone="sage">
          <CardHeader><CardTitle className="text-sm text-muted-foreground">This Month — Present</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.attendance_this_month.present}</p></CardContent>
        </Card>
        <Card tone="moss">
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Pending Leave Requests</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.pending_leave_requests}</p></CardContent>
        </Card>
        <Card tone="mint">
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Leave Types</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.leave_balances.length}</p></CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
<Card>
  <CardHeader>
    <CardTitle>Attendance This Month</CardTitle>
  </CardHeader>
  <CardContent>
    <div className="relative">
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={attendanceChartData}
            dataKey="value"
            nameKey="name"
            innerRadius={65}
            outerRadius={95}
            paddingAngle={2}
            stroke="none"
          >
            {attendanceChartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: any, name: any) => [`${Number(value ?? 0)} days`, name]}
            contentStyle={{ borderRadius: 8, fontSize: 12 }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Center total */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-semibold">
          {attendanceChartData.reduce((sum, d) => sum + d.value, 0)}
        </span>
        <span className="text-xs text-muted-foreground">Total Days</span>
      </div>
    </div>

    {/* Legend with values + percentages */}
    <div className="mt-4 space-y-2">
      {attendanceChartData.map((d, i) => {
        const total = attendanceChartData.reduce((s, x) => s + x.value, 0);
        const pct = total ? Math.round((d.value / total) * 100) : 0;
        return (
          <div key={d.name} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="text-muted-foreground">{d.name}</span>
            </div>
            <span className="font-medium">
              {d.value} <span className="text-muted-foreground">({pct}%)</span>
            </span>
          </div>
        );
      })}
    </div>
  </CardContent>
</Card>

        <Card>
          <CardHeader><CardTitle>Leave Balances</CardTitle></CardHeader>
          <CardContent className="space-y-6">
            <p className="text-sm text-muted-foreground">Your available days at a glance.</p>
            {data.leave_balances.length === 0 && (
              <p className="rounded-xl bg-muted p-4 text-sm text-muted-foreground">No leave balances available yet.</p>
            )}
            {data.leave_balances.map((bal) => {
              const remainingPercent = bal.total_days > 0
                ? Math.min(100, Math.max(0, (bal.remaining_days / bal.total_days) * 100))
                : 0;

              return (
                <div key={bal.leave_type_name} className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="font-medium">{bal.leave_type_name}</span>
                    <span className="shrink-0 font-semibold tabular-nums text-primary">
                      {bal.remaining_days} <span className="font-normal text-muted-foreground">/ {bal.total_days} left</span>
                    </span>
                  </div>
                  <div
                    role="progressbar"
                    aria-label={`${bal.leave_type_name} remaining`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={remainingPercent}
                    aria-valuetext={`${bal.remaining_days} of ${bal.total_days} days remaining`}
                    className="h-5 overflow-hidden rounded-full bg-muted"
                  >
                    <div
                      className="h-full rounded-full bg-[#9cbe83] motion-safe:transition-[width] motion-safe:duration-500"
                      style={{ width: `${remainingPercent}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
