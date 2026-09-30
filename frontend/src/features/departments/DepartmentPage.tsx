import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import ConfirmActionDialog from "@/components/ConfirmActionDialog";
import { useAppSelector } from "@/store/hooks";
import { useDepartments, useCreateDepartment, useDeleteDepartment } from "./useDepartments";
import type { Department } from "./departmentApi";

export default function DepartmentPage() {
  const role = useAppSelector((s) => s.auth.role);
  const canWrite = role === "admin";
  const { data: departments, isLoading } = useDepartments();
  const createDepartment = useCreateDepartment();
  const deleteDepartment = useDeleteDepartment();
  const [open, setOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Department | null>(null);
  const { register, handleSubmit, reset } = useForm<{ name: string; description?: string }>();

  const onSubmit = async (values: { name: string; description?: string }) => {
    await createDepartment.mutateAsync(values);
    reset();
    setOpen(false);
  };

  if (isLoading) return <LoadingSkeleton rows={4} />;

  return (
    <div>
      <PageHeader
        title="Departments"
        actions={canWrite && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Add Department</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New Department</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <Input placeholder="Name" {...register("name", { required: true })} />
                <Input placeholder="Description (optional)" {...register("description")} />
                <Button type="submit">Create</Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      />
      <DataTable
        rowKey={(d: Department) => d.id}
        data={departments ?? []}
        searchableText={(d) => `${d.name} ${d.description ?? ""}`}
        searchPlaceholder="Search departments..."
        columns={[
          { header: "Name", render: (d) => d.name },
          { header: "Description", render: (d) => d.description ?? "—" },
          ...(canWrite
            ? [{
                header: "Actions",
                render: (d: Department) => (
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
        title="Delete department?"
        description={<>This will permanently delete <strong>{toDelete?.name}</strong>. Departments currently in use cannot be deleted.</>}
        confirmLabel="Delete department"
        pending={deleteDepartment.isPending}
        error={deleteDepartment.isError}
        onOpenChange={(nextOpen) => {
          if (!nextOpen && !deleteDepartment.isPending) setToDelete(null);
        }}
        onConfirm={() => {
          if (!toDelete) return;
          deleteDepartment.mutate(toDelete.id, { onSuccess: () => setToDelete(null) });
        }}
      />
    </div>
  );
}
