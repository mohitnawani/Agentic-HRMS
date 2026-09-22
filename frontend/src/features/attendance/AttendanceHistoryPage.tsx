import PageHeader from "@/components/PageHeader";
import CheckInOut from "./CheckInOut";
import MonthlyCanvas from "./MonthlyCanvas";

export default function AttendanceHistoryPage() {
  return (
    <div className=" max-h-[700px] overflow-y-auto">
      <PageHeader title="Attendance" description="Check in/out and view your month" />
      <div className="mb-6"><CheckInOut /></div>
      <MonthlyCanvas />
    </div>
  );
}
