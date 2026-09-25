import { useState, type FormEvent } from "react";
import axios from "axios";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Database,
  FileSearch,
  ShieldAlert,
} from "lucide-react";
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
import { useEmployee, useEmployees } from "@/features/employees/useEmployees";
import { useUploadPolicy } from "@/features/policies/usePolicies";
import {
  useLeaveTypes,
  useMyBalances,
  useMyRequests,
  usePendingRequests,
} from "@/features/leave/useLeave";
import type { LeaveRequest } from "@/features/leave/leaveApi";
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
  apply_leave: "Apply for leave",
  cancel_leave: "Cancel leave",
  check_in: "Check in",
  check_out: "Check out",
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
  { name: "first_name", label: "First name" },
  { name: "last_name", label: "Last name" },
  { name: "phone", label: "Phone" },
  { name: "employee_code", label: "Employee code" },
  { name: "date_of_joining", label: "Date of joining", type: "date" },
  { name: "date_of_birth", label: "Date of birth", type: "date" },
  { name: "gender", label: "Gender" },
  { name: "city", label: "City" },
  { name: "address", label: "Address" },
  { name: "emergency_contact", label: "Emergency contact" },
] as const;

type Respond = (
  message: string,
  parameters?: Record<string, unknown>,
  displayMessage?: string,
) => void;

function requestErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    return error.response?.data?.detail ?? error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function EmployeeSelector({
  disabled,
  onRespond,
}: {
  disabled: boolean;
  onRespond: Respond;
}) {
  const [employeeId, setEmployeeId] = useState("");
  const [search, setSearch] = useState("");
  const { data: employees, isLoading, isError } = useEmployees();
  const selected = employees?.find((employee) => employee.id === employeeId);
  const normalizedSearch = search.trim().toLowerCase();
  const filteredEmployees = employees?.filter((employee) =>
    [
      employee.first_name,
      employee.last_name,
      `${employee.first_name} ${employee.last_name}`,
      employee.email,
      employee.employee_code ?? "",
    ].some((value) => value.toLowerCase().includes(normalizedSearch)),
  );

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
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search by name, email, or employee code"
        disabled={disabled || isLoading}
      />
      <div className="flex gap-2">
        <Select value={employeeId} onValueChange={setEmployeeId} disabled={disabled || isLoading}>
          <SelectTrigger>
            <SelectValue placeholder={isLoading ? "Loading employees..." : "Choose an employee"} />
          </SelectTrigger>
          <SelectContent>
            {filteredEmployees?.map((employee) => (
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
      {!isLoading && !isError && employees?.length !== 0 && filteredEmployees?.length === 0 && (
        <p className="text-xs text-muted-foreground">No employees match your search.</p>
      )}
    </form>
  );
}

function EmployeeResults({ employees }: { employees: Record<string, unknown>[] }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const normalizedSearch = search.trim().toLowerCase();
  const filtered = employees.filter((employee) =>
    [
      employee.full_name,
      employee.email,
      employee.employee_code,
      employee.department,
      employee.designation,
    ].some((value) => String(value ?? "").toLowerCase().includes(normalizedSearch)),
  );
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const activePage = Math.min(page, totalPages);
  const startIndex = (activePage - 1) * pageSize;
  const visible = filtered.slice(startIndex, startIndex + pageSize);

  return (
    <div className="mt-3 space-y-2">
      <Input
        value={search}
        onChange={(event) => {
          setSearch(event.target.value);
          setPage(1);
        }}
        placeholder="Search employees by name, email, code, or department"
        aria-label="Search employee results"
      />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{filtered.length} employee{filtered.length === 1 ? "" : "s"}</span>
        {filtered.length > 0 && (
          <span>
            Showing {startIndex + 1}–{Math.min(startIndex + pageSize, filtered.length)}
          </span>
        )}
      </div>
      <div className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
        {visible.map((employee, index) => (
          <div
            key={String(employee.employee_id ?? index)}
            className="rounded-lg bg-secondary/70 px-3 py-2 text-xs sm:flex sm:items-center sm:justify-between sm:gap-4"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">{String(employee.full_name ?? "Employee")}</p>
              <p className="truncate text-muted-foreground">{String(employee.email ?? "")}</p>
            </div>
            <div className="mt-1 shrink-0 text-muted-foreground sm:mt-0 sm:text-right">
              {Boolean(employee.employee_code) && <p>{String(employee.employee_code)}</p>}
              <p>{String(employee.department ?? "No department")}</p>
            </div>
          </div>
        ))}
      </div>
      {filtered.length === 0 && (
        <p className="rounded-lg bg-secondary/70 px-3 py-4 text-center text-xs text-muted-foreground">
          No employees match your search.
        </p>
      )}
      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2 border-t border-border/60 pt-2">
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label="Previous employee page"
            disabled={activePage === 1}
            onClick={() => setPage(activePage - 1)}
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
          </Button>
          <span className="min-w-20 text-center text-xs text-muted-foreground">
            Page {activePage} of {totalPages}
          </span>
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label="Next employee page"
            disabled={activePage === totalPages}
            onClick={() => setPage(activePage + 1)}
          >
            <ChevronRight className="size-4" aria-hidden="true" />
          </Button>
        </div>
      )}
    </div>
  );
}

function EmployeeUpdateForm({
  employeeId,
  disabled,
  onRespond,
}: {
  employeeId: string;
  disabled: boolean;
  onRespond: Respond;
}) {
  const [changes, setChanges] = useState<Record<string, string>>({});
  const { data: employee, isLoading, isError } = useEmployee(employeeId);
  const initialValues = employee
    ? Object.fromEntries(
        UPDATE_FIELDS.map(({ name }) => [name, String(employee[name] ?? "")]),
      )
    : {};
  const values = { ...initialValues, ...changes };

  const updates: Record<string, string | null> = {};
  for (const { name } of UPDATE_FIELDS) {
    const current = (values[name] ?? "").trim();
    const initial = (initialValues[name] ?? "").trim();
    if (current !== initial) updates[name] = current || null;
  }

  const submitUpdates = (event: FormEvent) => {
    event.preventDefault();
    const fields = Object.keys(updates);
    if (!fields.length) return;
    onRespond(
      "Update selected employee",
      { updates },
      `Update employee fields: ${fields.map((field) => field.replaceAll("_", " ")).join(", ")}`,
    );
  };

  return (
    <form onSubmit={submitUpdates} className="mt-3 space-y-3 border-t border-warning/20 pt-3">
      <div>
        <p className="text-xs font-medium text-primary">Employee changes</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Existing values are prefilled. Change any fields, then save them together.
        </p>
      </div>
      {isLoading && <p className="text-xs text-muted-foreground">Loading employee details...</p>}
      {isError && <p className="text-xs text-destructive">Could not load employee details.</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        {UPDATE_FIELDS.map((field) => (
          <label key={field.name} className={field.name === "address" ? "sm:col-span-2" : ""}>
            <span className="mb-1 block text-xs text-muted-foreground">{field.label}</span>
            <Input
              type={"type" in field ? field.type : "text"}
              value={values[field.name] ?? ""}
              onChange={(event) =>
                setChanges((current) => ({ ...current, [field.name]: event.target.value }))
              }
              disabled={disabled || isLoading || isError}
              required={["first_name", "last_name"].includes(field.name)}
            />
          </label>
        ))}
      </div>
      <Button
        size="sm"
        type="submit"
        disabled={disabled || isLoading || isError || !Object.keys(updates).length}
      >
        Save changes
      </Button>
    </form>
  );
}

function LeaveApplicationForm({
  disabled,
  onRespond,
}: {
  disabled: boolean;
  onRespond: Respond;
}) {
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [dateError, setDateError] = useState("");
  const { data: leaveTypes, isLoading: typesLoading } = useLeaveTypes();
  const { data: balances, isLoading: balancesLoading } = useMyBalances();
  const selectedType = leaveTypes?.find((type) => type.id === leaveTypeId);
  const selectedBalance = balances?.find((balance) => balance.leave_type_id === leaveTypeId);

  const submitLeave = (event: FormEvent) => {
    event.preventDefault();
    if (!leaveTypeId || !startDate || !endDate || !reason.trim()) return;
    if (endDate < startDate) {
      setDateError("End date cannot be before the start date.");
      return;
    }
    const balanceYear = selectedBalance?.year;
    if (
      balanceYear &&
      (Number(startDate.slice(0, 4)) !== balanceYear || Number(endDate.slice(0, 4)) !== balanceYear)
    ) {
      setDateError(`Your displayed leave balance is for ${balanceYear}. Choose dates in ${balanceYear}.`);
      return;
    }
    setDateError("");
    onRespond(
      "Submit leave application",
      {
        leave_type_id: leaveTypeId,
        start_date: startDate,
        end_date: endDate,
        reason: reason.trim(),
      },
      `Apply for ${selectedType?.name ?? "leave"}: ${startDate} to ${endDate}`,
    );
  };

  const loading = typesLoading || balancesLoading;
  return (
    <form onSubmit={submitLeave} className="mt-3 space-y-3 border-t border-warning/20 pt-3">
      <div>
        <p className="text-xs font-medium text-primary">New leave request</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Complete the request below. You can review it before confirmation.
        </p>
      </div>
      <label className="block">
        <span className="mb-1 block text-xs text-muted-foreground">Leave type</span>
        <Select value={leaveTypeId} onValueChange={setLeaveTypeId} disabled={disabled || loading}>
          <SelectTrigger>
            <SelectValue placeholder={loading ? "Loading leave balances..." : "Select leave type"} />
          </SelectTrigger>
          <SelectContent>
            {leaveTypes?.map((type) => {
              const balance = balances?.find((item) => item.leave_type_id === type.id);
              return (
                <SelectItem key={type.id} value={type.id}>
                  {type.name} · {balance?.remaining_days ?? 0} days available
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      </label>
      {selectedBalance && (
        <p className="rounded-md bg-secondary/70 px-3 py-2 text-xs text-muted-foreground">
          {selectedBalance.remaining_days} of {selectedBalance.total_days} days remaining
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <label>
          <span className="mb-1 block text-xs text-muted-foreground">Start date</span>
          <Input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
        <label>
          <span className="mb-1 block text-xs text-muted-foreground">End date</span>
          <Input
            type="date"
            value={endDate}
            min={startDate || undefined}
            onChange={(event) => setEndDate(event.target.value)}
            disabled={disabled}
            required
          />
        </label>
      </div>
      <label className="block">
        <span className="mb-1 block text-xs text-muted-foreground">Reason</span>
        <Textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Why do you need leave?"
          disabled={disabled}
          required
        />
      </label>
      {dateError && <p className="text-xs text-destructive">{dateError}</p>}
      <div className="flex gap-2">
        <Button
          size="sm"
          type="submit"
          disabled={disabled || loading || !leaveTypeId || !startDate || !endDate || !reason.trim()}
        >
          Review request
        </Button>
        <Button
          size="sm"
          type="button"
          variant="outline"
          onClick={() => onRespond("cancel")}
          disabled={disabled}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

function LeaveRequestPicker({
  requests,
  employeeNames,
  loading,
  disabled,
  onRespond,
}: {
  requests: LeaveRequest[];
  employeeNames?: Map<string, string>;
  loading: boolean;
  disabled: boolean;
  onRespond: Respond;
}) {
  const [requestId, setRequestId] = useState("");
  const [search, setSearch] = useState("");
  const normalizedSearch = search.trim().toLowerCase();
  const filtered = requests.filter((request) =>
    [
      employeeNames?.get(request.employee_id),
      request.start_date,
      request.end_date,
      request.reason,
    ].some((value) => String(value ?? "").toLowerCase().includes(normalizedSearch)),
  );
  const selected = requests.find((request) => request.id === requestId);

  const submitRequest = (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    onRespond(
      selected.id,
      { request_id: selected.id },
      `Selected leave request: ${selected.start_date} to ${selected.end_date}`,
    );
  };

  return (
    <form onSubmit={submitRequest} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
      <label className="block text-xs font-medium text-primary">Select leave request</label>
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search by employee, date, or reason"
        disabled={disabled || loading}
      />
      <div className="flex gap-2">
        <Select value={requestId} onValueChange={setRequestId} disabled={disabled || loading}>
          <SelectTrigger>
            <SelectValue placeholder={loading ? "Loading requests..." : "Choose a pending request"} />
          </SelectTrigger>
          <SelectContent>
            {filtered.map((request) => (
              <SelectItem key={request.id} value={request.id}>
                {employeeNames?.get(request.employee_id)
                  ? `${employeeNames.get(request.employee_id)} · `
                  : ""}
                {request.start_date} to {request.end_date} · {request.reason}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" type="submit" disabled={disabled || !requestId}>
          Continue
        </Button>
      </div>
      {!loading && filtered.length === 0 && (
        <p className="text-xs text-muted-foreground">No pending leave requests found.</p>
      )}
      <Button
        size="sm"
        type="button"
        variant="outline"
        onClick={() => onRespond("cancel")}
        disabled={disabled}
      >
        Cancel
      </Button>
    </form>
  );
}

function OwnLeaveRequestSelector(props: { disabled: boolean; onRespond: Respond }) {
  const { data, isLoading } = useMyRequests();
  return (
    <LeaveRequestPicker
      requests={(data ?? []).filter((request) => request.status === "pending")}
      loading={isLoading}
      {...props}
    />
  );
}

function PendingLeaveRequestSelector(props: { disabled: boolean; onRespond: Respond }) {
  const { data: requests, isLoading: requestsLoading } = usePendingRequests();
  const { data: employees, isLoading: employeesLoading } = useEmployees();
  const employeeNames = new Map(
    (employees ?? []).map((employee) => [
      employee.id,
      `${employee.first_name} ${employee.last_name}`,
    ]),
  );
  return (
    <LeaveRequestPicker
      requests={requests ?? []}
      employeeNames={employeeNames}
      loading={requestsLoading || employeesLoading}
      {...props}
    />
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
  const [uploadError, setUploadError] = useState("");
  const uploadPolicy = useUploadPolicy();
  const title = String(parameters.title ?? "");
  const category = String(parameters.category ?? "");

  const submitPolicy = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title || !category) return;
    setUploadError("");
    try {
      const document = await uploadPolicy.mutateAsync({ title, category, file });
      onRespond(
        "Policy upload completed",
        { policy_file: "uploaded", document_id: document.id },
        `Uploaded policy: ${document.title}`,
      );
    } catch (error) {
      setUploadError(requestErrorMessage(error, "Could not upload the policy."));
    }
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
      {uploadError && (
        <p className="text-xs text-destructive">
          {uploadError}
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
    onRespond(
      normalized,
      { [missingField]: normalized },
      missingField === "password" ? "[Sensitive value provided]" : normalized,
    );
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

      {interactive &&
        result.status === "needs_input" &&
        missingField === "updates" &&
        onRespond && (
          <EmployeeUpdateForm
            employeeId={String(pendingParameters.employee_id ?? "")}
            disabled={disabled}
            onRespond={onRespond}
          />
        )}

      {interactive &&
        result.status === "needs_input" &&
        missingField === "leave_type_id" &&
        onRespond && (
          <LeaveApplicationForm disabled={disabled} onRespond={onRespond} />
        )}

      {interactive &&
        result.status === "needs_input" &&
        missingField === "request_id" &&
        onRespond &&
        (result.tool === "cancel_leave" ? (
          <OwnLeaveRequestSelector disabled={disabled} onRespond={onRespond} />
        ) : (
          <PendingLeaveRequestSelector disabled={disabled} onRespond={onRespond} />
        ))}

      {interactive && result.status === "needs_input" && missingField && !["employee_id", "policy_file", "updates", "leave_type_id", "request_id"].includes(missingField) && onRespond && (
        <form onSubmit={submitSlot} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
          <label className="block text-xs font-medium text-primary">
            {FIELD_LABELS[missingField] ?? "Required information"}
          </label>
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
        <EmployeeResults employees={employees.map((item) => (isRecord(item) ? item : {}))} />
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
