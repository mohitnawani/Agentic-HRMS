import { apiClient } from "@/lib/api-client";

export interface Department {
  id: string;
  name: string;
  description: string | null;
}

export const listDepartments = () =>
  apiClient.get<Department[]>("/departments").then((r) => r.data);

export const createDepartment = (data: {
  name: string;
  description?: string;
}) => apiClient.post<Department>("/departments", data).then((r) => r.data);

export const updateDepartment = (
  id: string,
  data: { name?: string; description?: string },
) =>
  apiClient.patch<Department>(`/departments/${id}`, data).then((r) => r.data);
  
export const deleteDepartment = (id: string) =>
  apiClient.delete(`/departments/${id}`);
