import { useState, type FormEvent } from "react";
import { CheckCircle2, CircleAlert, Database, FileSearch, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useEmployees } from "@/features/employees/useEmployees";
import { useUploadPolicy } from "@/features/policies/usePolicies";
import { cn } from "@/lib/utils";
import type { AgentToolResult } from "./agentTypes";

const TOOL_LABELS: Record<string, string> = {
  get_leave_balance: "Leave balance",
  get_attendance_summary: "Attendance summary",
  list_employees: "Employee search",
  get_employee_details: "Employee details",
  policy_rag: "Policy search",
  create_employee: "Create employee",
  update_employee: "Update employee",
  delete_employee: "Delete employee",
  approve_leave: "Approve leave",
  reject_leave: "Reject leave",
  create_department: "Create department",
  create_announcement: "Create announcement",
  upload_policy: "Upload policy",
};

const FIELD_LABELS: Record<string, string> = {
  first_name: "First name",
  last_name: "Last name",
  email: "Email address",
  date_of_joining: "Joining date",
  password: "Temporary password",
  employee_id: "Employee ID",
  request_id: "Leave request ID",
  name: "Department name",
  title: "Title",
  body: "Announcement message",
  category: "Policy category",
  policy_file: "Policy PDF",
};

const UPDATE_FIELDS = [
  ["first_name", "First name"],
  ["last_name", "Last name"],
  ["phone", "Phone"],
  ["employee_code", "Employee code"],
  ["city", "City"],
] as const;

type Respond = (
  message: string,
  parameters?: Record<string, unknown>,
  displayMessage?: string,
) => void;

function EmployeeSelector({
  disabled,
  onRespond,
}: {
  disabled: boolean;
  onRespond: Respond;
}) {
  const [employeeId, setEmployeeId] = useState("");
  const { data: employees, isLoading, isError } = useEmployees();
  const selected = employees?.find((employee) => employee.id === employeeId);

  const submitEmployee = (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    onRespond(
      selected.id,
      { employee_id: selected.id },
      `Selected employee: ${selected.first_name} ${selected.last_name}`,
    );
  };

  return (
    <form onSubmit={submitEmployee} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
      <label className="block text-xs font-medium text-primary">Select employee</label>
      <div className="flex gap-2">
        <Select value={employeeId} onValueChange={setEmployeeId} disabled={disabled || isLoading}>
          <SelectTrigger>
            <SelectValue placeholder={isLoading ? "Loading employees..." : "Choose an employee"} />
          </SelectTrigger>
          <SelectContent>
            {employees?.map((employee) => (
              <SelectItem key={employee.id} value={employee.id}>
                {employee.first_name} {employee.last_name}
                {employee.employee_code ? ` · ${employee.employee_code}` : ""}
                {` · ${employee.email}`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" type="submit" disabled={disabled || !employeeId}>
          Continue
        </Button>
      </div>
      {isError && (
        <p className="text-xs text-destructive">Could not load employees. Please try again.</p>
      )}
      {!isLoading && !isError && employees?.length === 0 && (
        <p className="text-xs text-muted-foreground">No employees are available.</p>
      )}
    </form>
  );
}

function PolicyUploader({
  parameters,
  disabled,
  onRespond,
}: {
  parameters: Record<string, unknown>;
  disabled: boolean;
  onRespond: Respond;
}) {
  const [file, setFile] = useState<File | null>(null);
  const uploadPolicy = useUploadPolicy();
  const title = String(parameters.title ?? "");
  const category = String(parameters.category ?? "");

  const submitPolicy = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title || !category) return;
    const document = await uploadPolicy.mutateAsync({ title, category, file });
    onRespond(
      "Policy upload completed",
      { policy_file: "uploaded", document_id: document.id },
      `Uploaded policy: ${document.title}`,
    );
  };

  return (
    <form onSubmit={submitPolicy} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
      <label className="block text-xs font-medium text-primary">Choose policy PDF</label>
      <Input
        type="file"
        accept="application/pdf,.pdf"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        disabled={disabled || uploadPolicy.isPending}
        required
      />
      <p className="text-xs text-muted-foreground">
        {title} · {category}
      </p>
      {uploadPolicy.isError && (
        <p className="text-xs text-destructive">
          {uploadPolicy.error instanceof Error
            ? uploadPolicy.error.message
            : "Could not upload the policy."}
        </p>
      )}
      <Button
        size="sm"
        type="submit"
        disabled={disabled || !file || uploadPolicy.isPending}
      >
        {uploadPolicy.isPending ? "Uploading and indexing..." : "Upload policy"}
      </Button>
    </form>
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function titleFor(result: AgentToolResult) {
  if (result.tool) return TOOL_LABELS[result.tool] ?? result.tool.replaceAll("_", " ");
  if (result.agent === "database") return "HRMS data";
  if (result.agent === "rag") return "Policy search";
  return "HR action";
}

interface ToolResultCardProps {
  result: AgentToolResult;
  interactive?: boolean;
  disabled?: boolean;
  onRespond?: Respond;
}

export default function ToolResultCard({
  result,
  interactive = false,
  disabled = false,
  onRespond,
}: ToolResultCardProps) {
  const [value, setValue] = useState("");
  const [updateField, setUpdateField] = useState("first_name");
  const denied = result.status === "denied";
  const failed = result.status === "error";
  const waiting = ["needs_input", "confirmation_required"].includes(result.status);
  const data = result.data;
  const balances = isRecord(data) && Array.isArray(data.balances) ? data.balances : [];
  const employees = Array.isArray(data) ? data : [];
  const details = isRecord(data)
    ? Object.entries(data).filter(
        ([key, item]) =>
          !["stage", "missing_field"].includes(key) &&
          ["string", "number", "boolean"].includes(typeof item),
      )
    : [];
  const missingField =
    isRecord(data) && typeof data.missing_field === "string"
      ? data.missing_field
      : null;
  const pendingParameters =
    isRecord(data) && isRecord(data.parameters) ? data.parameters : {};
  const Icon = denied
    ? ShieldAlert
    : failed
      ? CircleAlert
      : result.agent === "rag"
        ? FileSearch
        : result.agent === "database"
          ? Database
          : CheckCircle2;

  const submitSlot = (event: FormEvent) => {
    event.preventDefault();
    const normalized = value.trim();
    if (!normalized || !missingField || !onRespond) return;
    if (missingField === "updates") {
      onRespond(`Set ${updateField.replaceAll("_", " ")} to ${normalized}`, {
        updates: { [updateField]: normalized },
      });
    } else {
      onRespond(
        normalized,
        { [missingField]: normalized },
        missingField === "password" ? "[Sensitive value provided]" : normalized,
      );
    }
    setValue("");
  };

  const inputType =
    missingField === "email"
      ? "email"
      : missingField === "date_of_joining"
        ? "date"
        : missingField === "password"
          ? "password"
          : "text";

  return (
    <div
      className={cn(
        "mt-3 rounded-xl border p-3 text-left",
        denied || failed
          ? "border-destructive/25 bg-destructive/5"
          : waiting
            ? "border-warning/30 bg-warning/5"
            : "border-border bg-background/80",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-xs font-semibold capitalize text-primary">
          <Icon className="size-4" aria-hidden="true" />
          {titleFor(result)}
        </span>
        <Badge variant={denied || failed ? "destructive" : waiting ? "warning" : "success"}>
          {result.status.replaceAll("_", " ")}
        </Badge>
      </div>

      {interactive && result.status === "confirmation_required" && onRespond && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-warning/20 pt-3">
          <Button size="sm" onClick={() => onRespond("confirm")} disabled={disabled}>
            Confirm action
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onRespond("cancel")}
            disabled={disabled}
          >
            Cancel
          </Button>
        </div>
      )}

      {interactive &&
        result.status === "needs_input" &&
        missingField === "employee_id" &&
        onRespond && (
          <EmployeeSelector disabled={disabled} onRespond={onRespond} />
        )}

      {interactive &&
        result.status === "needs_input" &&
        missingField === "policy_file" &&
        onRespond && (
          <PolicyUploader
            parameters={pendingParameters}
            disabled={disabled}
            onRespond={onRespond}
          />
        )}

      {interactive && result.status === "needs_input" && missingField && !["employee_id", "policy_file"].includes(missingField) && onRespond && (
        <form onSubmit={submitSlot} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
          <label className="block text-xs font-medium text-primary">
            {FIELD_LABELS[missingField] ?? "Required information"}
          </label>
          {missingField === "updates" && (
            <select
              value={updateField}
              onChange={(event) => setUpdateField(event.target.value)}
              disabled={disabled}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {UPDATE_FIELDS.map(([field, label]) => (
                <option key={field} value={field}>{label}</option>
              ))}
            </select>
          )}
          <div className="flex gap-2">
            {missingField === "body" ? (
              <Textarea
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="Enter the announcement message"
                disabled={disabled}
                required
              />
            ) : (
              <Input
                type={inputType}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder={`Enter ${(FIELD_LABELS[missingField] ?? missingField).toLowerCase()}`}
                autoComplete={missingField === "password" ? "new-password" : "off"}
                disabled={disabled}
                required
              />
            )}
            <Button size="sm" type="submit" disabled={disabled || !value.trim()}>
              Continue
            </Button>
          </div>
        </form>
      )}

      {balances.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {balances.map((item, index) => {
            const balance = isRecord(item) ? item : {};
            return (
              <div key={index} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <p className="font-medium">{String(balance.leave_type_name ?? "Leave")}</p>
                <p className="mt-0.5 text-muted-foreground">
                  {String(balance.remaining_days ?? 0)} of {String(balance.total_days ?? 0)} days remaining
                </p>
              </div>
            );
          })}
        </div>
      )}

      {employees.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {employees.slice(0, 5).map((item, index) => {
            const employee = isRecord(item) ? item : {};
            return (
              <div key={index} className="flex justify-between gap-3 rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <span className="font-medium">{String(employee.full_name ?? "Employee")}</span>
                <span className="truncate text-muted-foreground">{String(employee.email ?? "")}</span>
              </div>
            );
          })}
        </div>
      )}

      {!balances.length && !employees.length && details.length > 0 && (
        <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
          {details.slice(0, 8).map(([key, item]) => (
            <div key={key} className="flex justify-between gap-2 border-b border-border/60 py-1">
              <dt className="capitalize text-muted-foreground">{key.replaceAll("_", " ")}</dt>
              <dd className="truncate font-medium">{String(item)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
