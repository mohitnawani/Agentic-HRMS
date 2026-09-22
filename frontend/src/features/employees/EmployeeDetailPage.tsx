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
import { cn } from "@/lib/utils";

const EDIT_STEPS = ["Work Profile", "Personal Info", "Banking", "Documents"] as const;
const EDIT_STEP_FIELDS: Record<number, (keyof EditValues)[]> = {
  0: ["department_id", "date_of_joining", "employee_code"],
  1: ["first_name", "last_name", "phone", "emergency_contact", "date_of_birth", "gender", "address", "city", "photo"],
  2: ["bank_name", "account_number", "ifsc_code"],
  3: ["id_proof_type", "id_proof_number"],
};

interface EditValues {
  first_name: string; last_name: string; phone: string;
  date_of_joining: string; department_id: string; photo?: FileList;
  employee_code: string; date_of_birth: string; gender: string;
  address: string; city: string; emergency_contact: string;
  bank_name: string; account_number: string; ifsc_code: string;
  id_proof_type: string; id_proof_number: string;
}

const toEditValues = (e: {
  first_name: string; last_name: string; phone: string | null;
  date_of_joining: string; department_id: string | null;
  employee_code: string | null; date_of_birth: string | null; gender: string | null;
  address: string | null; city: string | null; emergency_contact: string | null;
  bank_name: string | null; account_number: string | null; ifsc_code: string | null;
  id_proof_type: string | null; id_proof_number: string | null;
}): EditValues => ({
  first_name: e.first_name,
  last_name: e.last_name,
  phone: e.phone ?? "",
  date_of_joining: e.date_of_joining,
  department_id: e.department_id ?? "",
  employee_code: e.employee_code ?? "",
  date_of_birth: e.date_of_birth ?? "",
  gender: e.gender ?? "",
  address: e.address ?? "",
  city: e.city ?? "",
  emergency_contact: e.emergency_contact ?? "",
  bank_name: e.bank_name ?? "",
  account_number: e.account_number ?? "",
  ifsc_code: e.ifsc_code ?? "",
  id_proof_type: e.id_proof_type ?? "",
  id_proof_number: e.id_proof_number ?? "",
});

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const role = useAppSelector((s) => s.auth.role);
  const { data: employee, isLoading, isError } = useEmployee(id ?? "");
  const { data: departments } = useDepartments();
  const updateEmployee = useUpdateEmployee();
  const uploadPhoto = useUploadPhoto();
  const [editing, setEditing] = useState(false);
  const [estep, setEstep] = useState(0);

  const { register, handleSubmit, control, reset, trigger } = useForm<EditValues>();

  // Admin edits anyone; HR edits HR/employee profiles but never admin profiles.
  const canEdit =
    role === "admin" || (role === "hr" && employee?.role !== "admin");

  if (isLoading) return <LoadingSkeleton rows={4} />;
  if (isError || !employee) return <p className="text-destructive">Employee not found.</p>;

  const openEdit = () => {
    reset(toEditValues(employee));
    setEstep(0);
    setEditing(true);
  };

  const onSave = async (values: EditValues) => {
    const { photo, department_id, ...rest } = values;
    const data: { [K in keyof typeof rest]?: (typeof rest)[K] | undefined } = { ...rest };
    for (const k of Object.keys(data) as (keyof typeof data)[]) {
      if (data[k] === "") data[k] = undefined;
    }
    await updateEmployee.mutateAsync({
      id: employee.id,
      data: { ...data, department_id: department_id || undefined },
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
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Edit Employee</DialogTitle></DialogHeader>
          <div className="mb-1 flex gap-1">
            {EDIT_STEPS.map((label, i) => (
              <button
                key={label}
                type="button"
                onClick={() => i <= estep && setEstep(i)}
                className={cn(
                  "flex-1 rounded-md px-2 py-1.5 text-xs font-medium",
                  i === estep ? "bg-primary text-primary-foreground" : i < estep ? "bg-muted" : "bg-muted/40 text-muted-foreground"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <form onSubmit={handleSubmit(onSave)} className="space-y-3">
            {estep === 0 && (
              <>
                <div className="grid grid-cols-2 gap-3">
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
                    <Label>Date of Joining</Label>
                    <Input type="date" {...register("date_of_joining", { required: true })} />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Employee Code</Label>
                  <Input {...register("employee_code")} />
                </div>
              </>
            )}
            {estep === 1 && (
              <>
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
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Phone</Label>
                    <Input {...register("phone")} />
                  </div>
                  <div className="space-y-1">
                    <Label>Emergency Contact</Label>
                    <Input {...register("emergency_contact")} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Date of Birth</Label>
                    <Input type="date" {...register("date_of_birth")} />
                  </div>
                <div className="space-y-1">
                  <Label>Gender</Label>
                  <Controller
                    control={control}
                    name="gender"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="male">Male</SelectItem>
                          <SelectItem value="female">Female</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Address</Label>
                    <Input {...register("address")} />
                  </div>
                  <div className="space-y-1">
                    <Label>City</Label>
                    <Input {...register("city")} />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Change Photo</Label>
                  <Input type="file" accept="image/*" {...register("photo")} />
                </div>
              </>
            )}
            {estep === 2 && (
              <>
                <div className="space-y-1">
                  <Label>Bank Name</Label>
                  <Input {...register("bank_name")} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Account Number</Label>
                    <Input {...register("account_number")} />
                  </div>
                  <div className="space-y-1">
                    <Label>IFSC Code</Label>
                    <Input {...register("ifsc_code")} />
                  </div>
                </div>
              </>
            )}
            {estep === 3 && (
              <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>ID Proof Type</Label>
                <Controller
                  control={control}
                  name="id_proof_type"
                  render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="aadhaar">Aadhaar</SelectItem>
                        <SelectItem value="pan">PAN</SelectItem>
                        <SelectItem value="passport">Passport</SelectItem>
                        <SelectItem value="driving_licence">Driving Licence</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
                <div className="space-y-1">
                  <Label>ID Proof Number</Label>
                  <Input {...register("id_proof_number")} />
                </div>
              </div>
            )}
            <div className="flex gap-2 pt-1">
              {estep > 0 && (
                <Button type="button" variant="outline" onClick={() => setEstep((s) => s - 1)}>Back</Button>
              )}
              <Button type="button" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
              <div className="flex-1" />
              {estep < EDIT_STEPS.length - 1 ? (
                <Button
                  type="button"
                  onClick={async () => {
                    if (await trigger(EDIT_STEP_FIELDS[estep])) setEstep((s) => s + 1);
                  }}
                >
                  Next
                </Button>
              ) : (
                <Button type="submit">Save Changes</Button>
              )}
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
