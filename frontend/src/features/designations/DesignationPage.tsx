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
import { useDepartments } from "@/features/departments/useDepartments";
import { useDesignations, useCreateDesignation, useDeleteDesignation } from "./useDesignations";
import type { Designation } from "./designationApi";

export default function DesignationPage() {
  const { data: designations, isLoading } = useDesignations();
  const { data: departments } = useDepartments();
  const createDesignation = useCreateDesignation();
  const deleteDesignation = useDeleteDesignation();
  const [open, setOpen] = useState(false);
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
        actions={
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
        }
      />
      <DataTable
        rowKey={(d: Designation) => d.id}
        data={designations ?? []}
        searchableText={(d) => `${d.title} ${d.department_name ?? ""}`}
        searchPlaceholder="Search designations..."
        columns={[
          { header: "Title", render: (d) => d.title },
          { header: "Department", render: (d) => d.department_name ?? "—" },
          {
            header: "Actions",
            render: (d) => (
              <Button size="sm" variant="destructive" onClick={() => deleteDesignation.mutate(d.id)}>
                Delete
              </Button>
            ),
          },
        ]}
      />
    </div>
  );
}
