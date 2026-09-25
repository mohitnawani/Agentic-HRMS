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
import { useDesignations, useCreateDesignation, useDeleteDesignation } from "./useDesignations";
import type { Designation } from "./designationApi";

export default function DesignationPage() {
  const { data: designations, isLoading } = useDesignations();
  const createDesignation = useCreateDesignation();
  const deleteDesignation = useDeleteDesignation();
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset } = useForm<{ title: string }>();

  const onSubmit = async (values: { title: string }) => {
    await createDesignation.mutateAsync(values);
    reset();
    setOpen(false);
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
                <Input placeholder="Title" {...register("title", { required: true })} />
                <Button type="submit">Create</Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />
      <DataTable
        rowKey={(d: Designation) => d.id}
        data={designations ?? []}
        searchableText={(d) => d.title}
        searchPlaceholder="Search designations..."
        columns={[
          { header: "Title", render: (d) => d.title },
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
