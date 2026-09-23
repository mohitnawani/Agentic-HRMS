import { useState, type ReactNode } from "react";
import { Building2, Mail, Phone, CalendarDays, Hash, ShieldCheck, Briefcase, User } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import EmptyState from "@/components/EmptyState";
import { useDepartments } from "@/features/departments/useDepartments";
import { useDesignations } from "@/features/designations/useDesignations";
import type { Employee } from "./employeeApi";

const TABS = ["Work Profile", "Personal Info", "Banking", "Documents"] as const;

function FieldRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 border-b border-border py-3 last:border-0">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md border text-red-600">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block text-xs text-muted-foreground">{label}</span>
        <span className="block truncate text-sm font-medium">{value}</span>
      </span>
    </div>
  );
}

export default function ProfileView({ employee, actions }: { employee: Employee; actions?: ReactNode }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Work Profile");
  const { data: departments } = useDepartments();
  const { data: designations } = useDesignations();

  const deptName = departments?.find((d) => d.id === employee.department_id)?.name ?? "—";
  const desigTitle = designations?.find((d) => d.id === employee.designation_id)?.title ?? "—";

  return (
    <div className="flex flex-col md:flex-row rounded-lg border overflow-hidden">
      <div className="w-full md:w-80 shrink-0 border-b md:border-b-0 md:border-r p-6">
        {employee.photo_url ? (
          <img
            src={employee.photo_url}
            alt={`${employee.first_name} ${employee.last_name}`}
            className="size-16 rounded-md object-cover border"
          />
        ) : (
            <div
              className="flex size-20 items-center justify-center rounded-full border border-sky-200 bg-sky-100"
              role="img"
              aria-label="No photo uploaded"
            >
              <User size={32} className="text-sky-700" />
            </div>
        )}

        <p className="mt-4 text-xs text-muted-foreground">Employee file</p>
        <h2 className="font-serif text-3xl font-semibold leading-tight">
          {employee.first_name} {employee.last_name}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{desigTitle}</p>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs">
            <Hash size={12} className="text-muted-foreground" />
            Record {employee.employee_code ?? employee.id.slice(0, 3).toUpperCase()}
          </span>
          <Badge variant={employee.is_active ? "success" : "outline"}>
            <ShieldCheck size={12} />
            {employee.is_active ? "ACTIVE" : "INACTIVE"}
          </Badge>
        </div>

        <div className="mt-4 border-t border-border">
          <FieldRow icon={<Building2 size={16} />} label="Department" value={deptName} />
          <FieldRow icon={<Briefcase size={16} />} label="Designation" value={desigTitle} />
          <FieldRow icon={<Mail size={16} />} label="Email" value={employee.email} />
          <FieldRow icon={<Phone size={16} />} label="Phone" value={employee.phone ?? "—"} />
          <FieldRow icon={<CalendarDays size={16} />} label="Joined" value={employee.date_of_joining} />
        </div>

        <div className="mt-4 flex border-t border-border pt-3 text-xs text-muted-foreground">
          <span className="flex-1">Type: Full-time</span>
          <span className="flex-1 border-l border-border pl-3">Role: {employee.role}</span>
        </div>

        {actions && <div className="mt-4">{actions}</div>}
      </div>

      <div className="flex-1 p-6">
        <p className="text-xs text-muted-foreground">Record section</p>
        <h1 className="font-serif text-3xl font-semibold">Work Profile</h1>
        <p className="mt-1 text-sm text-muted-foreground">Employment, contact, and residence details.</p>

        <div className="mt-4 flex gap-1 border-b border-border">
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={
                t === tab
                  ? "rounded-t-md border border-b-0 px-4 py-2 text-sm font-medium bg-background -mb-px"
                  : "px-4 py-2 text-sm text-muted-foreground hover:text-foreground bg-muted"
              }
            >
              {t}
            </button>
          ))}
        </div>

        <div className="py-4 text-sm">
          {tab === "Work Profile" && (
            <div className="max-w-md space-y-2 bg">
              <p><span className="text-muted-foreground">Department:</span> {deptName}</p>
              <p><span className="text-muted-foreground">Designation:</span> {desigTitle}</p>
              <p><span className="text-muted-foreground">Date of joining:</span> {employee.date_of_joining}</p>
              <p><span className="text-muted-foreground">Role:</span> {employee.role}</p>
            </div>
          )}
          {tab === "Personal Info" && (
            <div className="max-w-md space-y-2">
              <p><span className="text-muted-foreground">Email:</span> {employee.email}</p>
              <p><span className="text-muted-foreground">Phone:</span> {employee.phone ?? "—"}</p>
              <p><span className="text-muted-foreground">Date of birth:</span> {employee.date_of_birth ?? "—"}</p>
              <p><span className="text-muted-foreground">Gender:</span> {employee.gender ?? "—"}</p>
              <p><span className="text-muted-foreground">Address:</span> {employee.address ?? "—"}</p>
              <p><span className="text-muted-foreground">City:</span> {employee.city ?? "—"}</p>
              <p><span className="text-muted-foreground">Emergency contact:</span> {employee.emergency_contact ?? "—"}</p>
            </div>
          )}
          {tab === "Banking" && (
            employee.bank_name || employee.account_number || employee.ifsc_code ? (
              <div className="max-w-md space-y-2">
                <p><span className="text-muted-foreground">Bank:</span> {employee.bank_name ?? "—"}</p>
                <p>
                  <span className="text-muted-foreground">Account:</span>{" "}
                  {employee.account_number ? `••••${employee.account_number.slice(-4)}` : "—"}
                </p>
                <p><span className="text-muted-foreground">IFSC:</span> {employee.ifsc_code ?? "—"}</p>
              </div>
            ) : (
              <EmptyState title="No banking details yet" description="Banking information is not maintained for this employee." />
            )
          )}
          {tab === "Documents" && (
            employee.id_proof_type || employee.id_proof_number ? (
              <div className="max-w-md space-y-2">
                <p><span className="text-muted-foreground">ID proof:</span> {employee.id_proof_type ?? "—"}</p>
                <p><span className="text-muted-foreground">ID number:</span> {employee.id_proof_number ?? "—"}</p>
              </div>
            ) : (
              <EmptyState title="No documents yet" description="Uploaded documents will appear here." />
            )
          )}
        </div>
      </div>
    </div>
  );
}
