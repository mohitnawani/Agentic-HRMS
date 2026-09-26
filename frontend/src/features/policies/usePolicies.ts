import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./policyApi";

export const usePolicies = (category?: string) =>
  useQuery({
    queryKey: ["policies", category ?? "all"],
    queryFn: () => api.listPolicies(category),
  });

export const useUploadPolicy = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.uploadPolicy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
};

export const useDeletePolicy = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deletePolicy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
};
