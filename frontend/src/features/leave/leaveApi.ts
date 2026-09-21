import { apiClient } from "@/lib/api-client";

export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface LeaveType {
  id: string;
  name: string;
  default_annual_days: number;
}

export interface LeaveBalance {
  leave_type_id: string;
  leave_type_name: string;
  year: number;
  total_days: number;
  used_days: number;
  remaining_days: number;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: LeaveStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export const listLeaveTypes = () => apiClient.get<LeaveType[]>("/leave/types").then((r) => r.data);

export const getMyBalances = (year?: number) =>
  apiClient.get<LeaveBalance[]>("/leave/balance", { params: year ? { year } : {} }).then((r) => r.data);

export const applyLeave = (data: { leave_type_id: string; start_date: string; end_date: string; reason: string }) =>
  apiClient.post<LeaveRequest>("/leave/requests", data).then((r) => r.data);

export const getMyRequests = () => apiClient.get<LeaveRequest[]>("/leave/requests/me").then((r) => r.data);

export const getPendingRequests = () => apiClient.get<LeaveRequest[]>("/leave/requests/pending").then((r) => r.data);

export const approveRequest = (id: string) =>
  apiClient.post<LeaveRequest>(`/leave/requests/${id}/approve`).then((r) => r.data);

export const rejectRequest = (id: string) =>
  apiClient.post<LeaveRequest>(`/leave/requests/${id}/reject`).then((r) => r.data);

export const cancelRequest = (id: string) =>
  apiClient.post<LeaveRequest>(`/leave/requests/${id}/cancel`).then((r) => r.data);
