import { apiClient } from "@/lib/api-client";

export interface Employee {
  id: string;
  user_id: string;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  date_of_joining: string;
  department_id: string | null;
  designation_id: string | null;
}

export interface EmployeeCreatePayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  date_of_joining: string;
  department_id?: string;
  designation_id?: string;
}

export type EmployeeUpdatePayload = Partial<
  Omit<EmployeeCreatePayload, "email" | "password">
>;

export const listEmployees = (departmentId?: string) =>
  apiClient
    .get<Employee[]>("/employees", { params: departmentId ? { department_id: departmentId } : {} })
    .then((res) => res.data);

export const getEmployee = (id: string) =>
  apiClient.get<Employee>(`/employees/${id}`).then((res) => res.data);

export const createEmployee = (data: EmployeeCreatePayload) =>
  apiClient.post<Employee>("/employees", data).then((res) => res.data);

export const updateEmployee = (id: string, data: EmployeeUpdatePayload) =>
  apiClient.patch<Employee>(`/employees/${id}`, data).then((res) => res.data);

export const deleteEmployee = (id: string) => apiClient.delete(`/employees/${id}`);
