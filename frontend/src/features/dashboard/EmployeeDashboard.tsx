import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PageHeader from "@/components/PageHeader";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useEmployeeDashboard } from "./useDashboard";

const COLORS = ["#22c55e", "#ef4444", "#eab308", "#a855f7"];

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
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">This Month — Present</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.attendance_this_month.present}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Pending Leave Requests</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.pending_leave_requests}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Leave Types</CardTitle></CardHeader>
          <CardContent><p className="text-3xl font-semibold">{data.leave_balances.length}</p></CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Attendance This Month</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={attendanceChartData} dataKey="value" nameKey="name" outerRadius={80} label>
                  {attendanceChartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Leave Balances</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {data.leave_balances.map((bal) => (
              <div key={bal.leave_type_name} className="flex justify-between text-sm">
                <span>{bal.leave_type_name}</span>
                <span className="font-medium">{bal.remaining_days} / {bal.total_days} left</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
