import { useParams } from "react-router";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PageHeader from "@/components/PageHeader";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useEmployee } from "./useEmployees";

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: employee, isLoading, isError } = useEmployee(id ?? "");

  if (isLoading) return <LoadingSkeleton rows={4} />;
  if (isError || !employee) return <p className="text-destructive">Employee not found.</p>;

  return (
    <div className="max-w-lg">
      <PageHeader title={`${employee.first_name} ${employee.last_name}`} />
      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="text-muted-foreground">Email:</span> {employee.email}</p>
          <p><span className="text-muted-foreground">Phone:</span> {employee.phone ?? "—"}</p>
          <p><span className="text-muted-foreground">Joined:</span> {employee.date_of_joining}</p>
          <p><span className="text-muted-foreground">Role:</span> {employee.role}</p>
        </CardContent>
      </Card>
    </div>
  );
}
