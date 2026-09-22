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
  photo_url: string | null;
  is_active: boolean;
  employee_code: string | null;
  date_of_birth: string | null;
  gender: string | null;
  address: string | null;
  city: string | null;
  emergency_contact: string | null;
  bank_name: string | null;
  account_number: string | null;
  ifsc_code: string | null;
  id_proof_type: string | null;
  id_proof_number: string | null;
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
  role?: string;
  employee_code?: string;
  date_of_birth?: string;
  gender?: string;
  address?: string;
  city?: string;
  emergency_contact?: string;
  bank_name?: string;
  account_number?: string;
  ifsc_code?: string;
  id_proof_type?: string;
  id_proof_number?: string;
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

export const getMyProfile = () =>
  apiClient.get<Employee>("/employees/me").then((res) => res.data);

export const createEmployee = (data: EmployeeCreatePayload) =>
  apiClient.post<Employee>("/employees", data).then((res) => res.data);

export const updateEmployee = (id: string, data: EmployeeUpdatePayload) =>
  apiClient.patch<Employee>(`/employees/${id}`, data).then((res) => res.data);

export const deleteEmployee = (id: string) => apiClient.delete(`/employees/${id}`);

export const uploadEmployeePhoto = (id: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient.post<Employee>(`/employees/${id}/photo`, form).then((res) => res.data);
};
