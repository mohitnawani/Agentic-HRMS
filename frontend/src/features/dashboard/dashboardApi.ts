import { apiClient } from "@/lib/api-client";

export interface EmployeeDashboardData {
  attendance_this_month: { total_days: number; present: number; absent: number; late: number; half_day: number };
  leave_balances: { leave_type_name: string; total_days: number; used_days: number; remaining_days: number }[];
  pending_leave_requests: number;
}

export interface HRDashboardData {
  total_employees: number;
  on_leave_today: number;
  pending_approvals: number;
  department_breakdown: Record<string, number>;
}

export interface AdminDashboardData {
  total_employees: number;
  total_departments: number;
  active_users: number;
  department_breakdown: Record<string, number>;
}

export const getEmployeeDashboard = () =>
  apiClient.get<EmployeeDashboardData>("/dashboard/employee").then((res) => res.data);

export const getHRDashboard = () =>
  apiClient.get<HRDashboardData>("/dashboard/hr").then((res) => res.data);

export const getAdminDashboard = () =>
  apiClient.get<AdminDashboardData>("/dashboard/admin").then((res) => res.data);
