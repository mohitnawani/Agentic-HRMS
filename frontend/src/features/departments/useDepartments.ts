import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./departmentApi";

export const useDepartments = () =>
  useQuery({ queryKey: ["departments"], queryFn: api.listDepartments });

export const useCreateDepartment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createDepartment,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
};

export const useUpdateDepartment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string } }) =>
      api.updateDepartment(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
};

export const useDeleteDepartment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDepartment,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
};
