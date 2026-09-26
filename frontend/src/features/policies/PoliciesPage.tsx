import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useAppSelector } from "@/store/hooks";
import { useDeletePolicy, usePolicies, useUploadPolicy } from "./usePolicies";
import { downloadPolicyFile, type PolicyDocument } from "./policyApi";

export default function PoliciesPage() {
  const role = useAppSelector((s) => s.auth.role);
  const [category, setCategory] = useState<string>("all");
  const { data: allPolicies, isLoading, isError } = usePolicies();
  const uploadPolicy = useUploadPolicy();
  const deletePolicy = useDeletePolicy();
  const [open, setOpen] = useState(false);
  const [toDelete, setToDelete] = useState<PolicyDocument | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<{
    title: string; category: string; file: FileList;
  }>();

  const canUpload = role === "admin" || role === "hr";
  const categories = ["all", ...new Set((allPolicies ?? []).map((p) => p.category))];
  const policies = category === "all"
    ? allPolicies
    : allPolicies?.filter((policy) => policy.category === category);

  const onSubmit = async (values: { title: string; category: string; file: FileList }) => {
    const file = values.file?.[0];
    if (!file) return;
    await uploadPolicy.mutateAsync({ title: values.title, category: values.category, file });
    reset();
    setOpen(false);
  };

  const handleDownload = async (doc: PolicyDocument) => {
    setDownloadingId(doc.id);
    try {
      const blob = await downloadPolicyFile(doc.id);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const safeTitle = doc.title.replace(/[\\/:*?"<>|]+/g, "_").trim() || "policy";
      link.href = objectUrl;
      link.download = safeTitle.toLowerCase().endsWith(".pdf")
        ? safeTitle
        : `${safeTitle}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Policies"
        description="Company policy documents"
        actions={canUpload && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Upload Policy</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New Policy Document</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <div className="space-y-1">
                  <Label>Title</Label>
                  <Input {...register("title", { required: true })} placeholder="Leave Policy 2026" />
                </div>
                <div className="space-y-1">
                  <Label>Category</Label>
                  <Input {...register("category", { required: true })} placeholder="leave" />
                </div>
                <div className="space-y-1">
                  <Label>File (PDF only)</Label>
                  <Input type="file" accept="application/pdf" {...register("file", { required: true })} />
                  <p className="text-xs text-muted-foreground">Only PDF files are accepted.</p>
                </div>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Uploading..." : "Upload"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      />

      <div className="max-w-xs mb-4">
        <Label>Category</Label>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {categories.map((c) => (
              <SelectItem key={c} value={c}>{c === "all" ? "All categories" : c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && <LoadingSkeleton rows={4} />}
      {isError && <p className="text-destructive">Failed to load policies.</p>}
      {!isLoading && !isError && (
        <DataTable
          rowKey={(d: PolicyDocument) => d.id}
          data={policies ?? []}
          emptyTitle="No policy documents yet"
          searchableText={(d) => `${d.title} ${d.category}`}
          searchPlaceholder="Search policies by title or category..."
          columns={[
            { header: "Title", render: (d) => d.title },
            { header: "Category", render: (d) => d.category },
            { header: "Uploaded", render: (d) => new Date(d.created_at).toLocaleDateString() },
            {
              header: "Actions",
              render: (d) => (
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={downloadingId === d.id}
                    onClick={() => handleDownload(d)}
                  >
                    {downloadingId === d.id ? "Downloading..." : "Download"}
                  </Button>
                  {canUpload && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setToDelete(d)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
        />
      )}

      <AlertDialog open={!!toDelete} onOpenChange={(nextOpen) => !nextOpen && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete policy?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes “{toDelete?.title}”, its PDF, and all indexed RAG chunks.
              The assistant will no longer use it for answers.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep policy</AlertDialogCancel>
            <Button
              variant="destructive"
              size="sm"
              disabled={deletePolicy.isPending}
              onClick={() => {
                if (!toDelete) return;
                deletePolicy.mutate(toDelete.id, {
                  onSuccess: () => setToDelete(null),
                });
              }}
            >
              {deletePolicy.isPending ? "Deleting..." : "Delete policy"}
            </Button>
          </AlertDialogFooter>
          {deletePolicy.isError && (
            <p className="text-sm text-destructive">
              The policy could not be deleted. Nothing was removed; please try again.
            </p>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
