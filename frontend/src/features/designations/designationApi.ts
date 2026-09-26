import { apiClient } from "@/lib/api-client";

export interface Designation {
  id: string;
  title: string;
  department_id: string;
  department_name: string | null;
}

export const listDesignations = (departmentId?: string) =>
  apiClient
    .get<Designation[]>("/designations", { params: departmentId ? { department_id: departmentId } : {} })
    .then((r) => r.data);
export const createDesignation = (data: { title: string; department_id: string }) =>
  apiClient.post<Designation>("/designations", data).then((r) => r.data);
export const updateDesignation = (id: string, data: { title?: string; department_id?: string }) =>
  apiClient.patch<Designation>(`/designations/${id}`, data).then((r) => r.data);
export const deleteDesignation = (id: string) => apiClient.delete(`/designations/${id}`);
