import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import ConfirmActionDialog from "@/components/ConfirmActionDialog";
import { useAppSelector } from "@/store/hooks";
import { useDepartments } from "@/features/departments/useDepartments";
import { useDesignations, useCreateDesignation, useDeleteDesignation } from "./useDesignations";
import type { Designation } from "./designationApi";

export default function DesignationPage() {
  const role = useAppSelector((s) => s.auth.role);
  const canWrite = role === "admin";
  const { data: designations, isLoading } = useDesignations();
  const { data: departments } = useDepartments();
  const createDesignation = useCreateDesignation();
  const deleteDesignation = useDeleteDesignation();
  const [open, setOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Designation | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, control, reset, formState: { errors } } = useForm<{ title: string; department_id: string }>();

  const onSubmit = async (values: { title: string; department_id: string }) => {
    setServerError(null);
    try {
      await createDesignation.mutateAsync({ title: values.title.trim(), department_id: values.department_id });
      reset();
      setOpen(false);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setServerError(typeof detail === "string" ? detail : "Could not create designation.");
    }
  };

  if (isLoading) return <LoadingSkeleton rows={4} />;

  return (
    <div>
      <PageHeader
        title="Designations"
        actions={canWrite && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Add Designation</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New Designation</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <div className="space-y-1">
                  <Label>Department</Label>
                  <Controller
                    control={control}
                    name="department_id"
                    rules={{ required: "Pick a department" }}
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger><SelectValue placeholder="Select department" /></SelectTrigger>
                        <SelectContent>
                          {departments?.map((d) => (
                            <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.department_id && <p className="text-sm text-destructive">{errors.department_id.message}</p>}
                </div>
                <Input placeholder="Title e.g. Backend Developer" {...register("title", { required: "Title is required" })} />
                {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
                {serverError && <p className="text-sm text-destructive">{serverError}</p>}
                <Button type="submit">Create</Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      />
      <DataTable
        rowKey={(d: Designation) => d.id}
        data={designations ?? []}
        searchableText={(d) => `${d.title} ${d.department_name ?? ""}`}
        searchPlaceholder="Search designations..."
        columns={[
          { header: "Title", render: (d) => d.title },
          { header: "Department", render: (d) => d.department_name ?? "—" },
          ...(canWrite
            ? [{
                header: "Actions",
                render: (d: Designation) => (
                  <Button size="sm" variant="destructive" onClick={() => setToDelete(d)}>
                    Delete
                  </Button>
                ),
              }]
            : []),
        ]}
      />
      <ConfirmActionDialog
        open={toDelete !== null}
        title="Delete designation?"
        description={<>This will permanently delete <strong>{toDelete?.title}</strong>. Assigned designations cannot be deleted.</>}
        confirmLabel="Delete designation"
        pending={deleteDesignation.isPending}
        error={deleteDesignation.isError}
        onOpenChange={(nextOpen) => {
          if (!nextOpen && !deleteDesignation.isPending) setToDelete(null);
        }}
        onConfirm={() => {
          if (!toDelete) return;
          deleteDesignation.mutate(toDelete.id, { onSuccess: () => setToDelete(null) });
        }}
      />
    </div>
  );
}
