import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./attendanceApi";

export const useCheckIn = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.checkIn,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance"] }),
  });
};

export const useCheckOut = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.checkOut,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance"] }),
  });
};

export const useMyAttendanceHistory = () =>
  useQuery({ queryKey: ["attendance", "me", "history"], queryFn: () => api.getMyHistory() });

export const useMySummary = (year: number, month: number) =>
  useQuery({ queryKey: ["attendance", "me", "summary", year, month], queryFn: () => api.getMySummary(year, month) });

export const useMonthCalendar = (year: number, month: number) =>
  useQuery({
    queryKey: ["attendance", "me", "calendar", year, month],
    queryFn: () => api.getMonthCalendar(year, month),
  });

export const useEmployeeHistory = (employeeId: string) =>
  useQuery({
    queryKey: ["attendance", employeeId, "history"],
    queryFn: () => api.getEmployeeHistory(employeeId),
    enabled: !!employeeId,
  });

export const useCorrectAttendance = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof api.correctAttendance>[1] }) =>
      api.correctAttendance(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["attendance"] }),
  });
};
