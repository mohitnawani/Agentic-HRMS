import { apiClient } from "@/lib/api-client";

export interface Designation {
  id: string;
  title: string;
}

export const listDesignations = () => apiClient.get<Designation[]>("/designations").then((r) => r.data);
export const createDesignation = (data: { title: string }) =>
  apiClient.post<Designation>("/designations", data).then((r) => r.data);
export const updateDesignation = (id: string, data: { title?: string }) =>
  apiClient.patch<Designation>(`/designations/${id}`, data).then((r) => r.data);
export const deleteDesignation = (id: string) => apiClient.delete(`/designations/${id}`);
