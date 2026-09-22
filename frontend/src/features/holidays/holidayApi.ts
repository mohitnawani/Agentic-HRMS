import { apiClient } from "@/lib/api-client";

export interface Holiday {
  id: string;
  name: string;
  date: string;
}

export const listHolidays = (year?: number) =>
  apiClient.get<Holiday[]>("/holidays", { params: year ? { year } : {} }).then((r) => r.data);
export const createHoliday = (data: { name: string; date: string }) =>
  apiClient.post<Holiday>("/holidays", data).then((r) => r.data);
export const updateHoliday = (id: string, data: { name?: string; date?: string }) =>
  apiClient.patch<Holiday>(`/holidays/${id}`, data).then((r) => r.data);
export const deleteHoliday = (id: string) => apiClient.delete(`/holidays/${id}`);
