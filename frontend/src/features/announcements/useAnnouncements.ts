import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "./announcementApi";

export const useAnnouncements = () =>
  useQuery({ queryKey: ["announcements"], queryFn: api.listAnnouncements });

export const useCreateAnnouncement = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createAnnouncement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements"] }),
  });
};

export const useUpdateAnnouncement = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title?: string; body?: string; is_active?: boolean } }) =>
      api.updateAnnouncement(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements"] }),
  });
};

export const useDeleteAnnouncement = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deleteAnnouncement,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements"] }),
  });
};
