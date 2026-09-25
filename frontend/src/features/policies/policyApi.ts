import { apiClient } from "@/lib/api-client";

export interface PolicyDocument {
  id: string;
  title: string;
  category: string;
  file_path: string;
  uploaded_by: string;
  version: number;
  created_at: string;
}

export const listPolicies = (category?: string) =>
  apiClient
    .get<PolicyDocument[]>("/policies", { params: category && category !== "all" ? { category } : {} })
    .then((r) => r.data);

export const uploadPolicy = (data: { title: string; category: string; file: File }) => {
  const form = new FormData();
  form.append("title", data.title);
  form.append("category", data.category);
  form.append("file", data.file);
  return apiClient.post<PolicyDocument>("/policies", form).then((r) => r.data);
};

export const downloadPolicyFile = (id: string) =>
  apiClient
    .get<Blob>(`/policies/${id}/download`, { responseType: "blob" })
    .then((response) => response.data);
