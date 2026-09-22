import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import PageHeader from "@/components/PageHeader";
import { useDepartments } from "@/features/departments/useDepartments";
import { useCreateEmployee, useUploadPhoto } from "./useEmployees";
import { useAppSelector } from "@/store/hooks";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(6, "At least 6 characters"),
  first_name: z.string().min(1, "Required"),
  last_name: z.string().min(1, "Required"),
  phone: z.string().optional(),
  date_of_joining: z.string().min(1, "Required"),
  department_id: z.string().optional(),
  photo: z.any().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function EmployeeForm() {
  const navigate = useNavigate();
  const role = useAppSelector((s) => s.auth.role);
  const { data: departments } = useDepartments();
  const createEmployee = useCreateEmployee();
  const uploadPhoto = useUploadPhoto();

  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (values: FormValues) => {
    const { photo, ...payload } = values;
    const created = await createEmployee.mutateAsync(payload);
    const file = photo?.[0];
    if (file) {
      await uploadPhoto.mutateAsync({ id: created.id, file });
    }
    navigate(`/${role}/employees`);
  };

  return (
    <div className="max-w-lg">
      <PageHeader title="Add Employee" />
      <Card>
        <CardHeader><CardTitle>Details</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>First Name</Label>
                <Input {...register("first_name")} />
                {errors.first_name && <p className="text-sm text-destructive">{errors.first_name.message}</p>}
              </div>
              <div className="space-y-1">
                <Label>Last Name</Label>
                <Input {...register("last_name")} />
                {errors.last_name && <p className="text-sm text-destructive">{errors.last_name.message}</p>}
              </div>
            </div>
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
              <Label>Date of Joining</Label>
              <Input type="date" {...register("date_of_joining")} />
              {errors.date_of_joining && <p className="text-sm text-destructive">{errors.date_of_joining.message}</p>}
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
              <Label>Photo (optional)</Label>
              <Input type="file" accept="image/*" {...register("photo")} />
              <p className="text-xs text-muted-foreground">Portrait photo, uploaded after the profile is created.</p>
            </div>
            <div className="flex gap-2">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating..." : "Create Employee"}
              </Button>
              <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
