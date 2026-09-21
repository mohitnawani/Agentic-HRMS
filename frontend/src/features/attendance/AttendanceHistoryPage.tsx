import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { Badge } from "@/components/ui/badge";
import CheckInOut from "./CheckInOut";
import { useMyAttendanceHistory } from "./useAttendance";
import type { AttendanceRecord } from "./attendanceApi";

const STATUS_VARIANT: Record<AttendanceRecord["status"], "default" | "destructive" | "secondary"> = {
  present: "default",
  late: "secondary",
  absent: "destructive",
  half_day: "secondary",
};

export default function AttendanceHistoryPage() {
  const { data: history, isLoading, isError } = useMyAttendanceHistory();

  return (
    <div>
      <PageHeader title="Attendance" description="Check in/out and view your history" />
      <div className="mb-6"><CheckInOut /></div>

      {isLoading && <LoadingSkeleton rows={5} />}
      {isError && <p className="text-destructive">Failed to load history.</p>}
      {history && (
        <DataTable
          rowKey={(r: AttendanceRecord) => r.id}
          data={history}
          columns={[
            { header: "Date", render: (r) => r.date },
            { header: "Check In", render: (r) => (r.check_in ? new Date(r.check_in).toLocaleTimeString() : "—") },
            { header: "Check Out", render: (r) => (r.check_out ? new Date(r.check_out).toLocaleTimeString() : "—") },
            { header: "Status", render: (r) => <Badge variant={STATUS_VARIANT[r.status]}>{r.status}</Badge> },
          ]}
        />
      )}
    </div>
  );
}
