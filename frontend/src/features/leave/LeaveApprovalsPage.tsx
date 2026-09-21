import { Button } from "@/components/ui/button";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useEmployees } from "@/features/employees/useEmployees";
import { usePendingRequests, useApproveRequest, useRejectRequest } from "./useLeave";
import type { LeaveRequest } from "./leaveApi";

export default function LeaveApprovalsPage() {
  const { data: pending, isLoading, isError } = usePendingRequests();
  const { data: employees } = useEmployees();
  const approveRequest = useApproveRequest();
  const rejectRequest = useRejectRequest();

  const nameOf = (employeeId: string) => {
    const e = employees?.find((x) => x.id === employeeId);
    return e ? `${e.first_name} ${e.last_name}` : employeeId.slice(0, 8);
  };

  if (isLoading) return <LoadingSkeleton rows={5} />;
  if (isError) return <p className="text-destructive">Failed to load pending requests.</p>;

  return (
    <div>
      <PageHeader title="Leave Approvals" description={`${pending?.length ?? 0} pending`} />
      <DataTable
        rowKey={(r: LeaveRequest) => r.id}
        data={pending ?? []}
        emptyTitle="No pending requests"
        columns={[
          { header: "Employee", render: (r) => nameOf(r.employee_id) },
          { header: "From", render: (r) => r.start_date },
          { header: "To", render: (r) => r.end_date },
          { header: "Reason", render: (r) => r.reason },
          {
            header: "Actions",
            render: (r) => (
              <div className="flex gap-2">
                <Button size="sm" onClick={() => approveRequest.mutate(r.id)}>Approve</Button>
                <Button size="sm" variant="outline" onClick={() => rejectRequest.mutate(r.id)}>Reject</Button>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
