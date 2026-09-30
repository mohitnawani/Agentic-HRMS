import { useMemo, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useEmployees } from "@/features/employees/useEmployees";
import { useCorrectAttendanceForDate, useEmployeeHistory } from "./useAttendance";
import type { AttendanceRecord } from "./attendanceApi";

const today = new Date().toLocaleDateString("en-CA");

function timeFromIso(value: string | null) {
  return value ? value.slice(11, 16) : "";
}

function errorMessage(error: unknown) {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? error.message;
  }
  return "Attendance could not be corrected. Please try again.";
}

export default function AttendanceCorrectionPage() {
  const { data: employees } = useEmployees();
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [attendanceDate, setAttendanceDate] = useState("");
  const [attendanceStatus, setAttendanceStatus] = useState<AttendanceRecord["status"]>("present");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [reason, setReason] = useState("");
  const [success, setSuccess] = useState("");
  const { data: history, isLoading } = useEmployeeHistory(selectedEmployeeId);
  const correction = useCorrectAttendanceForDate();
  const selectedEmployee = employees?.find((employee) => employee.id === selectedEmployeeId);
  const normalizedSearch = employeeSearch.trim().toLowerCase();
  const filteredEmployees = employees?.filter((employee) =>
    [employee.first_name, employee.last_name, `${employee.first_name} ${employee.last_name}`, employee.email, employee.employee_code ?? ""]
      .some((value) => value.toLowerCase().includes(normalizedSearch)),
  );

  const selectedRecord = useMemo(
    () => history?.find((record) => record.date === attendanceDate),
    [attendanceDate, history],
  );

  const chooseDate = (date: string) => {
    setAttendanceDate(date);
    const record = history?.find((item) => item.date === date);
    setAttendanceStatus(record?.status ?? "present");
    setCheckIn(timeFromIso(record?.check_in ?? null));
    setCheckOut(timeFromIso(record?.check_out ?? null));
    setReason("");
    setSuccess("");
    correction.reset();
  };

  const handleEmployeeChange = (employeeId: string) => {
    setSelectedEmployeeId(employeeId);
    setAttendanceDate("");
    setReason("");
    setSuccess("");
    correction.reset();
  };

  const handleSave = () => {
    if (!selectedEmployeeId || !attendanceDate || !reason.trim()) return;
    correction.mutate(
      {
        employeeId: selectedEmployeeId,
        date: attendanceDate,
        data: {
          status: attendanceStatus,
          correction_reason: reason.trim(),
          check_in: checkIn ? `${attendanceDate}T${checkIn}:00` : null,
          check_out: checkOut ? `${attendanceDate}T${checkOut}:00` : null,
        },
      },
      {
        onSuccess: () => {
          setSuccess(`Attendance for ${attendanceDate} was corrected successfully.`);
          setReason("");
        },
      },
    );
  };

  return (
    <div>
      <PageHeader title="Attendance Correction" description="Correct an employee's attendance by selecting a date" />

      <Card className="mb-6 max-w-2xl">
        <CardHeader><CardTitle>Choose employee and date</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="attendance-employee-search">Search employee</Label>
            <Input id="attendance-employee-search" value={employeeSearch} onChange={(event) => setEmployeeSearch(event.target.value)} placeholder="Search by name, email, or employee code" />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label>Employee</Label>
            <Select value={selectedEmployeeId} onValueChange={handleEmployeeChange}>
              <SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger>
              <SelectContent>
                {filteredEmployees?.map((employee) => (
                  <SelectItem key={employee.id} value={employee.id}>
                    {employee.first_name} {employee.last_name} · {employee.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {filteredEmployees?.length === 0 && <p className="text-xs text-muted-foreground">No employees match your search.</p>}
          </div>
          {selectedEmployeeId && (
            <div className="space-y-2">
              <Label htmlFor="attendance-date">Attendance date</Label>
              <Input id="attendance-date" type="date" min={selectedEmployee?.date_of_joining} max={today} value={attendanceDate} onChange={(event) => chooseDate(event.target.value)} />
            </div>
          )}
        </CardContent>
      </Card>

      {selectedEmployeeId && isLoading && <LoadingSkeleton rows={4} />}

      {selectedEmployeeId && attendanceDate && (
        <Card className="mb-6 max-w-2xl">
          <CardHeader><CardTitle>{selectedRecord ? "Correct attendance entry" : "Add attendance correction"}</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {!selectedRecord && <p className="text-sm text-muted-foreground sm:col-span-2">No stored attendance exists for this date. Saving will create the corrected record.</p>}
            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={attendanceStatus} onValueChange={(value) => setAttendanceStatus(value as AttendanceRecord["status"])}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="present">Present</SelectItem>
                  <SelectItem value="absent">Absent</SelectItem>
                  <SelectItem value="late">Late</SelectItem>
                  <SelectItem value="half_day">Half Day</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div />
            <div className="space-y-2">
              <Label htmlFor="attendance-check-in">Check-in (optional)</Label>
              <Input id="attendance-check-in" type="time" value={checkIn} onChange={(event) => setCheckIn(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="attendance-check-out">Check-out (optional)</Label>
              <Input id="attendance-check-out" type="time" value={checkOut} onChange={(event) => setCheckOut(event.target.value)} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="attendance-reason">Correction reason</Label>
              <Input id="attendance-reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} placeholder="Why is this attendance being corrected?" />
            </div>
            {correction.isError && <p className="text-sm text-destructive sm:col-span-2">{errorMessage(correction.error)}</p>}
            {success && <p className="text-sm text-emerald-700 sm:col-span-2">{success}</p>}
            <div className="flex gap-2 sm:col-span-2">
              <Button onClick={handleSave} disabled={!reason.trim() || correction.isPending}>{correction.isPending ? "Saving..." : "Save correction"}</Button>
              <Button variant="outline" onClick={() => chooseDate("")}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {selectedEmployeeId && history && (
        <DataTable
          rowKey={(record: AttendanceRecord) => record.id}
          data={history}
          searchableText={(record) => `${record.date} ${record.status}`}
          searchPlaceholder="Search attendance by date or status..."
          columns={[
            { header: "Date", render: (record) => record.date },
            { header: "Status", render: (record) => record.status.replace("_", " ") },
            { header: "Check-in", render: (record) => timeFromIso(record.check_in) || "—" },
            { header: "Check-out", render: (record) => timeFromIso(record.check_out) || "—" },
            { header: "Actions", render: (record) => <Button size="sm" variant="outline" onClick={() => chooseDate(record.date)}>Correct</Button> },
          ]}
        />
      )}
    </div>
  );
}
