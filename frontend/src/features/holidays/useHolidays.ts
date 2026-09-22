import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./holidayApi";

export const useHolidays = (year?: number) =>
  useQuery({ queryKey: ["holidays", year ?? "all"], queryFn: () => api.listHolidays(year) });

export const useCreateHoliday = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createHoliday,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holidays"] }),
  });
};

export const useUpdateHoliday = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; date?: string } }) =>
      api.updateHoliday(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holidays"] }),
  });
};

export const useDeleteHoliday = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteHoliday,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holidays"] }),
  });
};
