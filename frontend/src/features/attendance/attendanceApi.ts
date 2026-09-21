import { apiClient } from "@/lib/api-client";

export interface AttendanceRecord {
  id: string;
  employee_id: string;
  date: string;
  check_in: string | null;
  check_out: string | null;
  status: "present" | "absent" | "late" | "half_day";
}

export interface AttendanceSummary {
  total_days: number;
  present: number;
  absent: number;
  late: number;
  half_day: number;
}

// check in
export const checkIn = () => apiClient.post<AttendanceRecord>("/attendance/check-in").then((r) => r.data)

//check out
export const checkOut = () => apiClient.post<AttendanceRecord>("/attendance/check-out").then((r) => r.data);


// get_history
export const getMyHistory = (start?: string, end?: string) =>
  apiClient
    .get<AttendanceRecord[]>("/attendance/me", { params: { start, end } })
    .then((r) => r.data);

// get summary
export const getMySummary = (year: number, month: number) =>
  apiClient.get<AttendanceSummary>("/attendance/me/summary", { params: { year, month } }).then((r) => r.data);


//get_employee_history
export const getEmployeeHistory = (employeeId: string, start?: string, end?: string) =>
  apiClient
    .get<AttendanceRecord[]>(`/attendance/${employeeId}`, { params: { start, end } })
    .then((r) => r.data);

//correct_attendance    
export const correctAttendance = (
  attendanceId: string,
  data: { check_in?: string; check_out?: string; status?: string; correction_reason: string }
) => apiClient.patch<AttendanceRecord>(`/attendance/${attendanceId}/correct`, data).then((r) => r.data);
