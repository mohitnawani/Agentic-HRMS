import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { useParams } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import PageHeader from "@/components/PageHeader";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useAppSelector } from "@/store/hooks";
import { useDepartments } from "@/features/departments/useDepartments";
import { useEmployee, useUpdateEmployee, useUploadPhoto } from "./useEmployees";
import ProfileView from "./ProfileView";

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const role = useAppSelector((s) => s.auth.role);
  const { data: employee, isLoading, isError } = useEmployee(id ?? "");
  const { data: departments } = useDepartments();
  const updateEmployee = useUpdateEmployee();
  const uploadPhoto = useUploadPhoto();
  const [editing, setEditing] = useState(false);

  const { register, handleSubmit, control, reset } = useForm<{
    first_name: string; last_name: string; phone: string;
    date_of_joining: string; department_id: string; photo?: FileList;
  }>();

  const canEdit = role === "admin" || role === "hr";

  if (isLoading) return <LoadingSkeleton rows={4} />;
  if (isError || !employee) return <p className="text-destructive">Employee not found.</p>;

  const openEdit = () => {
    reset({
      first_name: employee.first_name,
      last_name: employee.last_name,
      phone: employee.phone ?? "",
      date_of_joining: employee.date_of_joining,
      department_id: employee.department_id ?? "",
    });
    setEditing(true);
  };

  const onSave = async (values: {
    first_name: string; last_name: string; phone: string;
    date_of_joining: string; department_id: string; photo?: FileList;
  }) => {
    const { photo, ...fields } = values;
    await updateEmployee.mutateAsync({
      id: employee.id,
      data: { ...fields, department_id: fields.department_id || undefined },
    });
    const file = photo?.[0];
    if (file) {
      await uploadPhoto.mutateAsync({ id: employee.id, file });
    }
    setEditing(false);
  };

  return (
    <div>
      <PageHeader
        title={`${employee.first_name} ${employee.last_name}`}
        actions={canEdit && <Button onClick={openEdit}>Edit</Button>}
      />
      <ProfileView employee={employee} />

      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Employee</DialogTitle></DialogHeader>
          <form onSubmit={handleSubmit(onSave)} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>First Name</Label>
                <Input {...register("first_name", { required: true })} />
              </div>
              <div className="space-y-1">
                <Label>Last Name</Label>
                <Input {...register("last_name", { required: true })} />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Phone</Label>
              <Input {...register("phone")} />
            </div>
            <div className="space-y-1">
              <Label>Date of Joining</Label>
              <Input type="date" {...register("date_of_joining", { required: true })} />
            </div>
            <div className="space-y-1">
              <Label>Department</Label>
              <Controller
                control={control}
                name="department_id"
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
            </div>
            <div className="space-y-1">
              <Label>Change Photo</Label>
              <Input type="file" accept="image/*" {...register("photo")} />
            </div>
            <div className="flex gap-2">
              <Button type="submit">Save Changes</Button>
              <Button type="button" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
