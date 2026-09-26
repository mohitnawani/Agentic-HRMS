import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PageHeader from "@/components/PageHeader";
import { useDepartments } from "@/features/departments/useDepartments";
import { useDesignations } from "@/features/designations/useDesignations";
import { useCreateEmployee, useUploadPhoto } from "./useEmployees";
import type { EmployeeCreatePayload } from "./employeeApi";
import { useAppSelector } from "@/store/hooks";
import { cn } from "@/lib/utils";
import { emailSchema, passwordSchema } from "@/lib/validation";

const schema = z.object({
  email: emailSchema,
  password: passwordSchema,
  first_name: z.string().min(1, "Required"),
  last_name: z.string().min(1, "Required"),
  phone: z.string().optional(),
  date_of_joining: z.string().min(1, "Required"),
  department_id: z.string().optional(),
  designation_id: z.string().optional(),
  employee_code: z.string().optional(),
  date_of_birth: z.string().optional(),
  gender: z.string().optional(),
  address: z.string().optional(),
  city: z.string().optional(),
  emergency_contact: z.string().optional(),
  bank_name: z.string().optional(),
  account_number: z.string().optional(),
  ifsc_code: z.string().optional(),
  id_proof_type: z.string().optional(),
  id_proof_number: z.string().optional(),
  role: z.enum(["admin", "hr", "employee"]).optional(),
  photo: z.any().optional(),
});

type FormValues = z.infer<typeof schema>;

const STEPS = ["Work Profile", "Personal Info", "Banking", "Documents"] as const;
const STEP_FIELDS: Record<number, (keyof FormValues)[]> = {
  0: ["date_of_joining", "department_id", "designation_id", "employee_code"],
  1: ["first_name", "last_name", "email", "password", "phone", "date_of_birth", "gender", "address", "city", "emergency_contact", "photo"],
  2: ["bank_name", "account_number", "ifsc_code"],
  3: ["id_proof_type", "id_proof_number"],
};

export default function EmployeeForm() {
  const navigate = useNavigate();
  const role = useAppSelector((s) => s.auth.role);
  const { data: departments } = useDepartments();
  const { data: designations } = useDesignations();
  const createEmployee = useCreateEmployee();
  const uploadPhoto = useUploadPhoto();
  const [step, setStep] = useState(0);
  const [serverError, setServerError] = useState<string | null>(null);

  const { register, handleSubmit, control, trigger, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const next = async () => {
    if (await trigger(STEP_FIELDS[step])) setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const onSubmit = async (values: FormValues) => {
    setServerError(null);
    const { photo, ...rest } = values;
    const payload = Object.fromEntries(
      Object.entries(rest).map(([k, v]) => [k, v === "" ? undefined : v])
    ) as unknown as EmployeeCreatePayload;
    try {
      const created = await createEmployee.mutateAsync({
        ...payload,
        department_id: payload.department_id || undefined,
        designation_id: payload.designation_id || undefined,
      });
      const file = (photo as FileList | undefined)?.[0];
      if (file) {
        await uploadPhoto.mutateAsync({ id: created.id, file });
      }
      navigate(`/${role}/employees`);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setServerError(typeof detail === "string" ? detail : "Could not create employee. Check the highlighted fields.");
    }
  };

  const fieldError = (name: keyof FormValues) => {
    const msg = errors[name]?.message;
    return typeof msg === "string" ? <p className="text-sm text-destructive">{msg}</p> : null;
  };

  return (
    <div className="max-w-2xl">
      <PageHeader title="Add Employee" description={`Step ${step + 1} of ${STEPS.length}: ${STEPS[step]}`} />
      <div className="mb-4 flex gap-1">
        {STEPS.map((label, i) => (
          <button
            key={label}
            type="button"
            onClick={() => i < step && setStep(i)}
            className={cn(
              "flex-1 rounded-md px-2 py-2 text-xs font-medium",
              i === step ? "bg-primary text-primary-foreground" : i < step ? "bg-muted" : "bg-muted/40 text-muted-foreground"
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <Card>
        <CardHeader><CardTitle>{STEPS[step]}</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {step === 0 && (
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
                    <Label>Designation</Label>
                    <Controller
                      control={control}
                      name="designation_id"
                      render={({ field }) => (
                        <Select onValueChange={field.onChange} value={field.value}>
                          <SelectTrigger><SelectValue placeholder="Select designation" /></SelectTrigger>
                          <SelectContent>
                            {designations?.map((d) => (
                              <SelectItem key={d.id} value={d.id}>{d.title}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Date of Joining</Label>
                    <Input type="date" {...register("date_of_joining")} />
                    {fieldError("date_of_joining")}
                  </div>
                  <div className="space-y-1">
                    <Label>Employee Code (optional — auto if blank)</Label>
                    <Input {...register("employee_code")} placeholder="EMP-0007" />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>Role</Label>
                  <Controller
                    control={control}
                    name="role"
                    render={({ field }) => (
                      <Select onValueChange={field.onChange} value={field.value}>
                        <SelectTrigger><SelectValue placeholder="Employee" /></SelectTrigger>
                        <SelectContent>
                          {(role === "admin" ? ["admin", "hr", "employee"] : ["hr", "employee"]).map((r) => (
                            <SelectItem key={r} value={r}>{r === "hr" ? "HR" : r.charAt(0).toUpperCase() + r.slice(1)}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              </>
            )}

            {step === 1 && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>First Name</Label>
                    <Input {...register("first_name")} />
                    {fieldError("first_name")}
                  </div>
                  <div className="space-y-1">
                    <Label>Last Name</Label>
                    <Input {...register("last_name")} />
                    {fieldError("last_name")}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Email</Label>
                    <Input
                      type="email"
                      autoComplete="email"
                      placeholder="name@gmail.com"
                      {...register("email")}
                    />
                    {fieldError("email")}
                  </div>
                  <div className="space-y-1">
                    <Label>Temporary Password</Label>
                    <Input type="password" autoComplete="new-password" placeholder="Min 8 chars, letter + number" {...register("password")} />
                    {fieldError("password")}
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
                <div className="space-y-1">
                  <Label>Address</Label>
                  <Textarea {...register("address")} placeholder="Street, area..." />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>City</Label>
                    <Input {...register("city")} />
                  </div>
                  <div className="space-y-1">
                    <Label>Photo (optional)</Label>
                    <Input type="file" accept="image/*" {...register("photo")} />
                  </div>
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <div className="space-y-1">
                  <Label>Bank Name</Label>
                  <Input {...register("bank_name")} placeholder="HDFC Bank" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Account Number</Label>
                    <Input {...register("account_number")} />
                  </div>
                  <div className="space-y-1">
                    <Label>IFSC Code</Label>
                    <Input {...register("ifsc_code")} placeholder="HDFC0001234" />
                  </div>
                </div>
              </>
            )}

            {step === 3 && (
              <>
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
                <p className="text-xs text-muted-foreground">
                  Review the steps above — anything can stay blank and be completed later from the profile page.
                </p>
              </>
            )}

            <div className="flex gap-2 pt-2">
              {serverError && <p className="text-sm text-destructive w-full">{serverError}</p>}
            </div>
            <div className="flex gap-2 pt-2">
              {step > 0 && (
                <Button type="button" variant="outline" onClick={() => setStep((s) => s - 1)}>Back</Button>
              )}
              <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
              <div className="flex-1" />
              {step < STEPS.length - 1 ? (
                <Button type="button" onClick={next}>Next</Button>
              ) : (
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Creating..." : "Create Employee"}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
