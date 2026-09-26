import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./userApi";

export const useUsers = () =>
  useQuery({ queryKey: ["users"], queryFn: api.listUsers });

const invalidateUsers = (qc: ReturnType<typeof useQueryClient>) =>
  qc.invalidateQueries({ queryKey: ["users"] });

export const useCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createUser,
    onSuccess: () => invalidateUsers(qc),
  });
};

export const useActivateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.activateUser,
    onSuccess: () => invalidateUsers(qc),
  });
};

export const useDeactivateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deactivateUser,
    onSuccess: () => invalidateUsers(qc),
  });
};

export const useUpdateUserEmail = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, email }: { id: string; email: string }) =>
      api.updateUserEmail(id, email),
    onSuccess: () => invalidateUsers(qc),
  });
};
