import { useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import { Badge } from "@/components/ui/badge";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import EmptyState from "@/components/EmptyState";
import { useAppSelector } from "@/store/hooks";
import { useDepartments } from "@/features/departments/useDepartments";
import { useEmployees, useDeleteEmployee } from "./useEmployees";
import type { Employee } from "./employeeApi";

export default function EmployeeListPage() {
  const navigate = useNavigate();
  const role = useAppSelector((s) => s.auth.role);
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const { data: employees, isLoading, isError } = useEmployees(
    departmentFilter === "all" ? undefined : departmentFilter,
  );
  const { data: departments } = useDepartments();
  const deleteEmployee = useDeleteEmployee();
  const [toDelete, setToDelete] = useState<Employee | null>(null);

  const canManage = role === "admin" || role === "hr";
  // Admin deletes anyone; HR deletes employees only (never admins/HRs); employee deletes no one.
  const canDelete = (targetRole: string) =>
    role === "admin" || (role === "hr" && targetRole === "employee");

  if (isLoading) return <LoadingSkeleton rows={6} />;
  if (isError) return <p className="text-destructive">Failed to load employees.</p>;
  if (!employees || employees.length === 0) {
    return (
      <div>
        <PageHeader title="Employees" actions={canManage && <Button onClick={() => navigate(`/${role}/employees/new`)}>Add Employee</Button>} />
        <EmptyState title="No employees yet" description="Add your first employee to get started." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Employees"
        description={`${employees.length} total`}
        actions={canManage && <Button onClick={() => navigate(`/${role}/employees/new`)}>Add Employee</Button>}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Department:</span>
        <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
          <SelectTrigger className="w-56" aria-label="Filter by department">
            <SelectValue placeholder="All departments" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All departments</SelectItem>
            {departments?.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <DataTable
        rowKey={(e: Employee) => e.id}
        data={employees}
        searchableText={(e) => [e.first_name, e.last_name, e.email, e.employee_code, e.role, e.department_name, e.designation_name].filter(Boolean).join(" ")}
        searchPlaceholder="Search employees by name, email, code, role..."
        columns={[
          { header: "Name", render: (e) => `${e.first_name} ${e.last_name}` },
          { header: "Email", render: (e) => e.email },
          { header: "Department", render: (e) => e.department_name ?? "—" },
          { header: "Designation", render: (e) => e.designation_name ?? "—" },
          {
            header: "Role",
            render: (e) => (
              <Badge variant={e.role === "admin" ? "default" : e.role === "hr" ? "secondary" : "outline"}>
                {e.role === "hr" ? "HR" : e.role.charAt(0).toUpperCase() + e.role.slice(1)}
              </Badge>
            ),
          },
          { header: "Joined", render: (e) => e.date_of_joining },
          {
            header: "Actions",
            render: (e) => (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => navigate(`/${role}/employees/${e.id}`)}>
                  View
                </Button>
                {canDelete(e.role) && (
                  <Button size="sm" variant="destructive" onClick={() => setToDelete(e)}>
                    Delete
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />

      <AlertDialog open={!!toDelete} onOpenChange={(open) => !open && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete employee?</AlertDialogTitle>
            <AlertDialogDescription>
              This will deactivate {toDelete?.first_name} {toDelete?.last_name}'s account. This cannot be undone from the UI.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (toDelete) deleteEmployee.mutate(toDelete.id);
                setToDelete(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
