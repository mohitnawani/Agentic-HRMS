import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./employeeApi";

export const useEmployees = (departmentId?: string) =>
  useQuery({
    queryKey: ["employees", departmentId ?? "all"],
    queryFn: () => api.listEmployees(departmentId),
  });

export const useEmployee = (id: string) =>
  useQuery({ queryKey: ["employees", id], queryFn: () => api.getEmployee(id), enabled: !!id });

export const useCreateEmployee = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createEmployee,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
};

export const useUpdateEmployee = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: api.EmployeeUpdatePayload }) =>
      api.updateEmployee(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
};

export const useDeleteEmployee = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteEmployee,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
};
