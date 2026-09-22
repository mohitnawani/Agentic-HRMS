import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useMyBalances, useMyRequests, useApplyLeave, useCancelRequest } from "./useLeave";
import { useLeaveTypes } from "./useLeave";
import type { LeaveRequest, LeaveStatus } from "./leaveApi";

const STATUS_VARIANT: Record<LeaveStatus, "success" | "destructive" | "warning" | "outline"> = {
  pending: "warning",
  approved: "success",
  rejected: "destructive",
  cancelled: "outline",
};

const applySchema = z.object({
  leave_type_id: z.string().min(1, "Pick a leave type"),
  start_date: z.string().min(1, "Required"),
  end_date: z.string().min(1, "Required"),
  reason: z.string().min(1, "Required"),
}).refine((v) => v.end_date >= v.start_date, {
  message: "End date can't be before start date",
  path: ["end_date"],
});

type ApplyValues = z.infer<typeof applySchema>;

export default function LeavePage() {
  const { data: balances, isLoading: balancesLoading } = useMyBalances();
  const { data: requests, isLoading: requestsLoading } = useMyRequests();
  const { data: leaveTypes } = useLeaveTypes();
  const applyLeave = useApplyLeave();
  const cancelRequest = useCancelRequest();
  const [open, setOpen] = useState(false);

  const { register, handleSubmit, control, reset, formState: { errors, isSubmitting } } = useForm<ApplyValues>({
    resolver: zodResolver(applySchema),
  });

  const onSubmit = async (values: ApplyValues) => {
    await applyLeave.mutateAsync(values);
    reset();
    setOpen(false);
  };

  return (
    <div>
      <PageHeader
        title="Leave"
        description="Your balances and requests"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Apply for Leave</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New Leave Request</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <div className="space-y-1">
                  <Label>Leave Type</Label>
                  <Controller
                    control={control}
                    name="leave_type_id"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger><SelectValue placeholder="Select type" /></SelectTrigger>
                        <SelectContent>
                          {leaveTypes?.map((t) => (
                            <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.leave_type_id && <p className="text-sm text-destructive">{errors.leave_type_id.message}</p>}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Start</Label>
                    <Input type="date" {...register("start_date")} />
                    {errors.start_date && <p className="text-sm text-destructive">{errors.start_date.message}</p>}
                  </div>
                  <div className="space-y-1">
                    <Label>End</Label>
                    <Input type="date" {...register("end_date")} />
                    {errors.end_date && <p className="text-sm text-destructive">{errors.end_date.message}</p>}
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Reason</Label>
                  <Textarea {...register("reason")} placeholder="Why do you need leave?" />
                  {errors.reason && <p className="text-sm text-destructive">{errors.reason.message}</p>}
                </div>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Submitting..." : "Submit Request"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {balancesLoading ? (
        <LoadingSkeleton rows={3} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {balances?.map((b, i) => (
            <Card key={b.leave_type_id} tone={(["amber", "violet", "teal"] as const)[i % 3]}>
              <CardHeader><CardTitle className="text-sm text-muted-foreground">{b.leave_type_name}</CardTitle></CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold">{b.remaining_days}<span className="text-base text-muted-foreground"> / {b.total_days}</span></p>
                <p className="text-xs text-muted-foreground mt-1">Used {b.used_days} this year</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <h2 className="text-lg font-semibold mb-3">My Requests</h2>
      {requestsLoading ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <DataTable
          rowKey={(r: LeaveRequest) => r.id}
          data={requests ?? []}
          emptyTitle="No leave requests yet"
          columns={[
            { header: "From", render: (r) => r.start_date },
            { header: "To", render: (r) => r.end_date },
            { header: "Reason", render: (r) => r.reason },
            { header: "Status", render: (r) => <Badge variant={STATUS_VARIANT[r.status]}>{r.status}</Badge> },
            {
              header: "Actions",
              render: (r) => r.status === "pending" ? (
                <Button size="sm" variant="outline" onClick={() => cancelRequest.mutate(r.id)}>
                  Cancel
                </Button>
              ) : <span className="text-muted-foreground text-sm">—</span>,
            },
          ]}
        />
      )}
    </div>
  );
}
