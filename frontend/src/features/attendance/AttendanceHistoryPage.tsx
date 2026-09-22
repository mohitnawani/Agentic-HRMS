import PageHeader from "@/components/PageHeader";
import CheckInOut from "./CheckInOut";
import MonthlyCanvas from "./MonthlyCanvas";

export default function AttendanceHistoryPage() {
  return (
    <div>
      <PageHeader title="Attendance" description="Check in/out and view your month" />
      <div className="mb-6"><CheckInOut /></div>
      <MonthlyCanvas />
    </div>
  );
}
