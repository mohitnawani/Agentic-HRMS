import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useEmployees } from "@/features/employees/useEmployees";
import { useEmployeeHistory, useCorrectAttendance } from "./useAttendance";
import type { AttendanceRecord } from "./attendanceApi";

export default function AttendanceCorrectionPage() {
  const { data: employees } = useEmployees();
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>("");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const { data: history, isLoading } = useEmployeeHistory(selectedEmployeeId);
  const [editing, setEditing] = useState<AttendanceRecord | null>(null);
  const [reason, setReason] = useState("");
  const correctAttendance = useCorrectAttendance();
  const normalizedEmployeeSearch = employeeSearch.trim().toLowerCase();
  const filteredEmployees = employees?.filter((employee) =>
    [
      employee.first_name,
      employee.last_name,
      `${employee.first_name} ${employee.last_name}`,
      employee.email,
      employee.employee_code ?? "",
    ].some((value) => value.toLowerCase().includes(normalizedEmployeeSearch)),
  );

  const handleSave = () => {
    if (!editing) return;
    correctAttendance.mutate(
      { id: editing.id, data: { status: editing.status, correction_reason: reason } },
      { onSuccess: () => { setEditing(null); setReason(""); } }
    );
  };

  return (
    <div>
      <PageHeader title="Attendance Correction" description="Select an employee to view and correct their records" />

      <div className="mb-6 max-w-md space-y-2 rounded-xl border border-border bg-card p-4 shadow-sm">
        <Label htmlFor="attendance-employee-search">Employee</Label>
        <Input
          id="attendance-employee-search"
          value={employeeSearch}
          onChange={(event) => setEmployeeSearch(event.target.value)}
          placeholder="Search by name, email, or employee code"
        />
        <Select value={selectedEmployeeId} onValueChange={setSelectedEmployeeId}>
          <SelectTrigger><SelectValue placeholder="Select employee" /></SelectTrigger>
          <SelectContent>
            {filteredEmployees?.map((e) => (
              <SelectItem key={e.id} value={e.id}>
                {e.first_name} {e.last_name} · {e.email}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {filteredEmployees?.length === 0 && (
          <p className="text-xs text-muted-foreground">No employees match your search.</p>
        )}
      </div>

      {selectedEmployeeId && isLoading && <LoadingSkeleton rows={4} />}

      {selectedEmployeeId && history && (
        <DataTable
          rowKey={(r: AttendanceRecord) => r.id}
          data={history}
          searchableText={(r) => `${r.date} ${r.status}`}
          searchPlaceholder="Search attendance by date or status..."
          columns={[
            { header: "Date", render: (r) => r.date },
            { header: "Status", render: (r) => r.status },
            {
              header: "Actions",
              render: (r) => (
                <Button size="sm" variant="outline" onClick={() => setEditing(r)}>Correct</Button>
              ),
            },
          ]}
        />
      )}

      {editing && (
        <Card className="mt-6 max-w-md">
          <CardHeader><CardTitle>Correct entry — {editing.date}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div>
              <Label>Status</Label>
              <Select
                value={editing.status}
                onValueChange={(v) => setEditing({ ...editing, status: v as AttendanceRecord["status"] })}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="present">Present</SelectItem>
                  <SelectItem value="absent">Absent</SelectItem>
                  <SelectItem value="late">Late</SelectItem>
                  <SelectItem value="half_day">Half Day</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Correction Reason</Label>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is this being corrected?" />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSave} disabled={!reason || correctAttendance.isPending}>Save</Button>
              <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
