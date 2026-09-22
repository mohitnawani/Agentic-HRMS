import { apiClient } from "@/lib/api-client";

export type ManagedRole = "admin" | "hr" | "employee";

export interface ManagedUser {
  id: string;
  email: string;
  role: ManagedRole;
  is_active: boolean;
}

export const listUsers = () => apiClient.get<ManagedUser[]>("/users").then((r) => r.data);

export const createUser = (data: {
  email: string;
  password: string;
  role: ManagedRole;
  first_name?: string;
  last_name?: string;
}) => apiClient.post<ManagedUser>("/users", data).then((r) => r.data);

export const activateUser = (id: string) =>
  apiClient.patch<ManagedUser>(`/users/${id}/activate`).then((r) => r.data);

export const deactivateUser = (id: string) =>
  apiClient.patch<ManagedUser>(`/users/${id}/deactivate`).then((r) => r.data);
