import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCheckIn, useCheckOut, useMyAttendanceHistory } from "./useAttendance";

export default function CheckInOut() {
  const { data: history } = useMyAttendanceHistory();
  const checkIn = useCheckIn();
  const checkOut = useCheckOut();

  const today = new Date().toISOString().slice(0, 10);
  const todayRecord = history?.find((r) => r.date === today);

  const hasCheckedIn = !!todayRecord?.check_in;
  const hasCheckedOut = !!todayRecord?.check_out;

  return (
    <Card>
      <CardHeader><CardTitle>Today's Attendance</CardTitle></CardHeader>
      <CardContent className="flex items-center gap-4">
        <Button onClick={() => checkIn.mutate()} disabled={hasCheckedIn || checkIn.isPending}>
          {hasCheckedIn ? "Checked In" : "Check In"}
        </Button>
        <Button
          variant="outline"
          onClick={() => checkOut.mutate()}
          disabled={!hasCheckedIn || hasCheckedOut || checkOut.isPending}
        >
          {hasCheckedOut ? "Checked Out" : "Check Out"}
        </Button>
        {todayRecord?.check_in && (
          <p className="text-sm text-muted-foreground">
            In: {new Date(todayRecord.check_in).toLocaleTimeString()}
            {todayRecord.check_out && ` · Out: ${new Date(todayRecord.check_out).toLocaleTimeString()}`}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
