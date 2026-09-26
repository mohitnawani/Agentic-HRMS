import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useAppSelector } from "@/store/hooks";
import { useHolidays, useCreateHoliday, useDeleteHoliday } from "./useHolidays";
import type { Holiday } from "./holidayApi";

export default function HolidaysPage() {
  const role = useAppSelector((s) => s.auth.role);
  const canWrite = role === "admin";
  const [year, setYear] = useState<string>("");
  const yearNum = year ? Number(year) : undefined;
  const { data: holidays, isLoading, isError } = useHolidays(yearNum);
  const createHoliday = useCreateHoliday();
  const deleteHoliday = useDeleteHoliday();
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, reset } = useForm<{ name: string; date: string }>();

  const onSubmit = async (values: { name: string; date: string }) => {
    await createHoliday.mutateAsync(values);
    reset();
    setOpen(false);
  };

  return (
    <div>
      <PageHeader
        title="Holidays"
        description="Company holiday calendar"
        actions={canWrite && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Add Holiday</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New Holiday</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <div className="space-y-1">
                  <Label>Name</Label>
                  <Input {...register("name", { required: true })} placeholder="Diwali" />
                </div>
                <div className="space-y-1">
                  <Label>Date</Label>
                  <Input type="date" {...register("date", { required: true })} />
                </div>
                <Button type="submit">Create</Button>
              </form>
            </DialogContent>
          </Dialog>
        )}
      />

      <div className="max-w-xs mb-4">
        <Label>Filter by year</Label>
        <div className="flex gap-2">
          <Input
            type="number"
            placeholder="e.g. 2026"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
          {year && <Button variant="outline" onClick={() => setYear("")}>Clear</Button>}
        </div>
      </div>

      {isLoading && <LoadingSkeleton rows={4} />}
      {isError && <p className="text-destructive">Failed to load holidays.</p>}
      {!isLoading && !isError && (
        <DataTable
          rowKey={(h: Holiday) => h.id}
          data={holidays ?? []}
          emptyTitle="No holidays yet"
          searchableText={(h) => `${h.name} ${h.date}`}
          searchPlaceholder="Search holidays by name or date..."
          columns={[
            { header: "Name", render: (h) => h.name },
            { header: "Date", render: (h) => h.date },
            ...(canWrite
              ? [{
                  header: "Actions",
                  render: (h: Holiday) => (
                    <Button size="sm" variant="destructive" onClick={() => deleteHoliday.mutate(h.id)}>
                      Delete
                    </Button>
                  ),
                }]
              : []),
          ]}
        />
      )}
    </div>
  );
}
