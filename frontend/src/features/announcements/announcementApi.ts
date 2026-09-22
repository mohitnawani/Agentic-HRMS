import { apiClient } from "@/lib/api-client";

export interface Announcement {
  id: string;
  title: string;
  body: string;
  created_by: string;
  is_active: boolean;
}

export const listAnnouncements = () =>
  apiClient.get<Announcement[]>("/announcements").then((r) => r.data);
export const createAnnouncement = (data: { title: string; body: string }) =>
  apiClient.post<Announcement>("/announcements", data).then((r) => r.data);
export const updateAnnouncement = (id: string, data: { title?: string; body?: string; is_active?: boolean }) =>
  apiClient.patch<Announcement>(`/announcements/${id}`, data).then((r) => r.data);
export const deleteAnnouncement = (id: string) => apiClient.delete(`/announcements/${id}`);
