import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./designationApi";

export const useDesignations = (departmentId?: string) =>
  useQuery({
    queryKey: ["designations", departmentId ?? "all"],
    queryFn: () => api.listDesignations(departmentId),
  });

export const useCreateDesignation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createDesignation,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["designations"] }),
  });
};

export const useUpdateDesignation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title?: string; department_id?: string } }) =>
      api.updateDesignation(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["designations"] }),
  });
};

export const useDeleteDesignation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteDesignation,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["designations"] }),
  });
};
