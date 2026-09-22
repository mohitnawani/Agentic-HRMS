import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import PageHeader from "@/components/PageHeader";
import DataTable from "@/components/DataTable";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useUsers, useCreateUser, useActivateUser, useDeactivateUser } from "./useUsers";
import type { ManagedRole, ManagedUser } from "./userApi";

const ROLE_VARIANT: Record<ManagedRole, "default" | "secondary" | "outline"> = {
  admin: "default",
  hr: "secondary",
  employee: "outline",
};

const createSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(6, "At least 6 characters"),
  role: z.enum(["admin", "hr", "employee"]),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
});

type CreateValues = z.infer<typeof createSchema>;

export default function UsersPage() {
  const { data: users, isLoading, isError } = useUsers();
  const createUser = useCreateUser();
  const activateUser = useActivateUser();
  const deactivateUser = useDeactivateUser();
  const [open, setOpen] = useState(false);

  const { register, handleSubmit, control, reset, formState: { errors, isSubmitting } } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: "employee" },
  });

  const onSubmit = async (values: CreateValues) => {
    await createUser.mutateAsync(values);
    reset({ role: "employee" });
    setOpen(false);
  };

  return (
    <div>
      <PageHeader
        title="Users"
        description={`${users?.length ?? 0} accounts`}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>Create User</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>New User Account</DialogTitle></DialogHeader>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
                <div className="space-y-1">
                  <Label>Email</Label>
                  <Input type="email" {...register("email")} />
                  {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
                </div>
                <div className="space-y-1">
                  <Label>Temporary Password</Label>
                  <Input type="password" {...register("password")} />
                  {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
                </div>
                <div className="space-y-1">
                  <Label>Role</Label>
                  <Controller
                    control={control}
                    name="role"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="hr">HR</SelectItem>
                          <SelectItem value="employee">Employee</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>First Name (optional)</Label>
                    <Input {...register("first_name")} />
                  </div>
                  <div className="space-y-1">
                    <Label>Last Name (optional)</Label>
                    <Input {...register("last_name")} />
                  </div>
                </div>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Creating..." : "Create User"}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      {isLoading && <LoadingSkeleton rows={5} />}
      {isError && <p className="text-destructive">Failed to load users.</p>}
      {!isLoading && !isError && (
        <DataTable
          rowKey={(u: ManagedUser) => u.id}
          data={users ?? []}
          emptyTitle="No users found"
          columns={[
            { header: "Email", render: (u) => u.email },
            { header: "Role", render: (u) => <Badge variant={ROLE_VARIANT[u.role]}>{u.role}</Badge> },
            {
              header: "Status",
              render: (u) => (
                <Badge variant={u.is_active ? "success" : "outline"}>
                  {u.is_active ? "Active" : "Inactive"}
                </Badge>
              ),
            },
            {
              header: "Actions",
              render: (u) => u.is_active ? (
                <Button size="sm" variant="outline" onClick={() => deactivateUser.mutate(u.id)}>
                  Deactivate
                </Button>
              ) : (
                <Button size="sm" onClick={() => activateUser.mutate(u.id)}>
                  Activate
                </Button>
              ),
            },
          ]}
        />
      )}
    </div>
  );
}
