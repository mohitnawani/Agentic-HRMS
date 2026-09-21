import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./leaveApi";

export const useLeaveTypes = () =>
  useQuery({ queryKey: ["leave", "types"], queryFn: api.listLeaveTypes });

export const useMyBalances = () =>
  useQuery({ queryKey: ["leave", "me", "balances"], queryFn: () => api.getMyBalances() });

export const useMyRequests = () =>
  useQuery({ queryKey: ["leave", "me", "requests"], queryFn: api.getMyRequests });

export const usePendingRequests = () =>
  useQuery({ queryKey: ["leave", "pending"], queryFn: api.getPendingRequests });

const invalidateLeave = (qc: ReturnType<typeof useQueryClient>) => {
  qc.invalidateQueries({ queryKey: ["leave"] });
  qc.invalidateQueries({ queryKey: ["dashboard"] });
};

export const useApplyLeave = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.applyLeave,
    onSuccess: () => invalidateLeave(qc),
  });
};

export const useApproveRequest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.approveRequest,
    onSuccess: () => invalidateLeave(qc),
  });
};

export const useRejectRequest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.rejectRequest,
    onSuccess: () => invalidateLeave(qc),
  });
};

export const useCancelRequest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.cancelRequest,
    onSuccess: () => invalidateLeave(qc),
  });
};
