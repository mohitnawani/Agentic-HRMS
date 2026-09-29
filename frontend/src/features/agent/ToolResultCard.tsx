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
import { useEmployees } from "@/features/employees/useEmployees";
import { uploadEmployeePhoto } from "@/features/employees/employeeApi";
import { usePolicies, useUploadPolicy } from "@/features/policies/usePolicies";
import {
  useMyRequests,
  usePendingRequests,
} from "@/features/leave/useLeave";
import type { LeaveRequest } from "@/features/leave/leaveApi";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api-client";
import type { AgentToolResult } from "./agentTypes";

const TOOL_LABELS: Record<string, string> = {
  get_leave_balance: "Leave balance",
  get_attendance_summary: "Attendance summary",
  list_attendance_records: "Employee attendance",
  list_employees: "Employee search",
  get_employee_details: "Employee details",
  get_policy_catalog: "Policy catalog",
  get_audit_logs: "Agent audit logs",
  get_leave_history: "Leave history",
  list_leave_requests: "Employee leave requests",
  list_pending_leave_requests: "Pending leave requests",
  get_holidays: "Holidays",
  get_announcements: "Announcements",
  list_departments: "Departments",
  list_designations: "Designations",
  list_users: "User accounts",
  policy_rag: "Policy search",
  policy_summary: "Policy summary",
  create_employee: "Create employee",
  update_employee: "Update employee",
  upload_employee_photo: "Upload employee photo",
  delete_employee: "Delete employee",
  approve_leave: "Approve leave",
  reject_leave: "Reject leave",
  create_leave_type: "Create leave type",
  create_department: "Create department",
  delete_department: "Delete department",
  create_designation: "Create designation",
  delete_designation: "Delete designation",
  create_announcement: "Create announcement",
  update_announcement: "Update announcement",
  delete_announcement: "Delete announcement",
  create_holiday: "Create holiday",
  delete_holiday: "Delete holiday",
  upload_policy: "Upload policy",
  update_policy: "Update policy",
  delete_policy: "Delete policy",
  apply_leave: "Apply for leave",
  correct_attendance: "Correct attendance",
  cancel_leave: "Cancel leave",
  check_in: "Check in",
  check_out: "Check out",
};

const FIELD_LABELS: Record<string, string> = {
  first_name: "First name",
  last_name: "Last name",
  email: "Email address",
  date_of_joining: "Joining date",
  date_of_birth: "Date of birth",
  start_date: "Start date",
  end_date: "End date",
  date: "Date",
  password: "Temporary password",
  employee_id: "Employee ID",
  update_field: "Employee field",
  update_value: "New value",
  photo_file: "Employee photo",
  request_id: "Leave request ID",
  name: "Department name",
  title: "Title",
  body: "Announcement message",
  announcement_title: "Announcement title",
  announcement_body: "Announcement message",
  announcement_is_active: "Announcement visibility",
  category: "Policy category",
  policy_file: "Policy PDF",
  policy_title: "Policy title",
  policy_category: "Policy category",
  status: "Attendance status",
  correction_reason: "Correction reason",
  leave_type_name: "Leave type name",
  annual_days: "Annual days",
};

const DATE_FIELDS = new Set([
  "date",
  "date_of_birth",
  "date_of_joining",
  "end_date",
  "start_date",
]);

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
      employee.phone,
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
        placeholder="Search by name, email, phone, code, or department"
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
              {Boolean(employee.phone) && (
                <p className="truncate text-muted-foreground">{String(employee.phone)}</p>
              )}
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

function PolicyDownloadButton({ documentId, title }: { documentId: string; title: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const download = async () => {
    setPending(true);
    setError("");
    try {
      const response = await apiClient.get(`/policies/${documentId}/download`, {
        responseType: "blob",
      });
      const disposition: string = response.headers["content-disposition"] ?? "";
      const match = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/.exec(disposition);
      const filename = decodeURIComponent(match?.[1] ?? match?.[2] ?? `${title}.pdf`);
      const url = URL.createObjectURL(new Blob([response.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError("Download failed.");
    } finally {
      setPending(false);
    }
  };

  return (
    <span className="mt-2 block">
      <Button size="sm" variant="outline" onClick={download} disabled={pending}>
        {pending ? "Downloading…" : "Download PDF"}
      </Button>
      {error && <span className="ml-2 text-destructive">{error}</span>}
    </span>
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

function EmployeePhotoUploader({
  employeeId,
  disabled,
  onRespond,
}: {
  employeeId: string;
  disabled: boolean;
  onRespond: Respond;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const submitPhoto = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !employeeId) return;
    setUploading(true);
    setUploadError("");
    try {
      const employee = await uploadEmployeePhoto(employeeId, file);
      onRespond(
        "Employee photo upload completed",
        { photo_file: "uploaded" },
        `Uploaded photo for ${employee.first_name} ${employee.last_name}`,
      );
    } catch (error) {
      setUploadError(requestErrorMessage(error, "Could not upload the employee photo."));
    } finally {
      setUploading(false);
    }
  };

  return (
    <form onSubmit={submitPhoto} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
      <label className="block text-xs font-medium text-primary">Choose employee photo</label>
      <Input
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        disabled={disabled || uploading}
        required
      />
      <p className="text-xs text-muted-foreground">PNG, JPG, WEBP, or GIF; maximum 5 MB.</p>
      {uploadError && <p className="text-xs text-destructive">{uploadError}</p>}
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={disabled || uploading || !file}>
          {uploading ? "Uploading..." : "Upload photo"}
        </Button>
        <Button
          size="sm"
          type="button"
          variant="outline"
          onClick={() => onRespond("cancel")}
          disabled={disabled || uploading}
        >
          Cancel
        </Button>
      </div>
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

function PolicySelector({
  disabled,
  onRespond,
  action = "delete",
}: {
  disabled: boolean;
  onRespond: Respond;
  action?: "delete" | "edit";
}) {
  const { data: policies, isLoading, isError } = usePolicies();
  const [documentId, setDocumentId] = useState("");
  const [search, setSearch] = useState("");
  const normalizedSearch = search.trim().toLowerCase();
  const filteredPolicies = policies?.filter((policy) =>
    [policy.title, policy.category].some((value) =>
      value.toLowerCase().includes(normalizedSearch),
    ),
  );
  const selected = policies?.find((policy) => policy.id === documentId);

  const submitPolicy = (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    onRespond(
      selected.id,
      { document_id: selected.id },
      `Selected policy: ${selected.title}`,
    );
  };

  return (
    <form onSubmit={submitPolicy} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
      <label className="block text-xs font-medium text-primary">
        Select policy to {action}
      </label>
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search by title or category"
        disabled={disabled || isLoading}
      />
      <div className="flex gap-2">
        <Select value={documentId} onValueChange={setDocumentId} disabled={disabled || isLoading}>
          <SelectTrigger>
            <SelectValue placeholder={isLoading ? "Loading policies..." : "Choose a policy"} />
          </SelectTrigger>
          <SelectContent>
            {filteredPolicies?.map((policy) => (
              <SelectItem key={policy.id} value={policy.id}>
                {policy.title} · {policy.category}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" type="submit" disabled={disabled || !documentId}>
          Continue
        </Button>
      </div>
      {isError && <p className="text-xs text-destructive">Could not load policies.</p>}
      {!isLoading && !isError && filteredPolicies?.length === 0 && (
        <p className="text-xs text-muted-foreground">No policies match your search.</p>
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function titleFor(result: AgentToolResult) {
  if (result.tool && result.tool !== "unknown") {
    return TOOL_LABELS[result.tool] ?? result.tool.replaceAll("_", " ");
  }
  if (result.agent === "database") return "HRMS data";
  if (result.agent === "rag") return "Policy search";
  return "Assistant request";
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
  const initialCurrentValue = isRecord(result.data) ? result.data.current_value : undefined;
  const [value, setValue] = useState(
    typeof initialCurrentValue === "string" ? initialCurrentValue : "",
  );
  const denied = result.status === "denied";
  const failed = result.status === "error";
  const waiting = ["needs_input", "confirmation_required"].includes(result.status);
  const data = result.data;
  const balances = isRecord(data) && Array.isArray(data.balances) ? data.balances : [];
  const employees = Array.isArray(data) ? data : [];
  const policyCatalog = isRecord(data) && isRecord(data.catalog) ? data.catalog : data;
  const policies = isRecord(policyCatalog) && Array.isArray(policyCatalog.policies)
    ? policyCatalog.policies
    : [];
  const policySummaries = isRecord(data) && Array.isArray(data.summaries)
    ? data.summaries
    : [];
  const auditRecords = isRecord(data) && Array.isArray(data.audits) ? data.audits : [];
  const leaveRequests = isRecord(data) && Array.isArray(data.leave_requests)
    ? data.leave_requests
    : [];
  const holidays = isRecord(data) && Array.isArray(data.holidays) ? data.holidays : [];
  const announcements = isRecord(data) && Array.isArray(data.announcements)
    ? data.announcements
    : [];
  const attendanceRecords = isRecord(data) && Array.isArray(data.attendance_records)
    ? data.attendance_records
    : [];
  const departments = isRecord(data) && Array.isArray(data.departments) ? data.departments : [];
  const designations = isRecord(data) && Array.isArray(data.designations) ? data.designations : [];
  const users = isRecord(data) && Array.isArray(data.users) ? data.users : [];
  const managementRecords = [...departments, ...designations, ...users];
  const details = isRecord(data)
    ? Object.entries(data).filter(
        ([key, item]) =>
          !["stage", "missing_field", "current_value", "allow_keep"].includes(key) &&
          ["string", "number", "boolean"].includes(typeof item),
      )
    : [];
  const missingField =
    isRecord(data) && typeof data.missing_field === "string"
      ? data.missing_field
      : null;
  const pendingParameters =
    isRecord(data) && isRecord(data.parameters) ? data.parameters : {};
  const minimumDate =
    isRecord(data) && typeof data.min_date === "string" ? data.min_date : undefined;
  const currentValue = isRecord(data) ? data.current_value : undefined;
  const requestedInputType =
    isRecord(data) && typeof data.input_type === "string" ? data.input_type : undefined;
  const suggestions =
    isRecord(data) && Array.isArray(data.suggestions)
      ? data.suggestions.filter(isRecord)
      : [];
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
    requestedInputType === "date"
      ? "date"
      : missingField === "email"
      ? "email"
      : missingField && DATE_FIELDS.has(missingField)
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
        missingField === "photo_file" &&
        result.tool === "upload_employee_photo" &&
        onRespond && (
          <EmployeePhotoUploader
            employeeId={String(pendingParameters.employee_id ?? "")}
            disabled={disabled}
            onRespond={onRespond}
          />
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
        missingField === "document_id" &&
        ["delete_policy", "update_policy"].includes(result.tool ?? "") &&
        onRespond && (
          <PolicySelector
            action={result.tool === "update_policy" ? "edit" : "delete"}
            disabled={disabled}
            onRespond={onRespond}
          />
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

      {interactive &&
        result.status === "needs_input" &&
        missingField &&
        !["document_id", "employee_id", "request_id"].includes(missingField) &&
        suggestions.length > 0 &&
        onRespond && (
          <div className="mt-3 space-y-2 border-t border-warning/20 pt-3">
            <p className="text-xs font-medium text-primary">
              {FIELD_LABELS[missingField] ?? "Choose an option"}
            </p>
            <div
              className="flex snap-x gap-2 overflow-x-auto pb-2"
              aria-label={`${FIELD_LABELS[missingField] ?? missingField} options`}
            >
              {suggestions.map((suggestion, index) => {
                const optionValue = String(suggestion.value ?? "");
                const optionLabel = String(suggestion.label ?? optionValue);
                return (
                  <Button
                    key={`${optionValue}-${index}`}
                    type="button"
                    variant="outline"
                    className="h-auto min-w-44 snap-start items-start whitespace-normal px-3 py-2 text-left"
                    disabled={disabled || !optionValue}
                    onClick={() =>
                      onRespond(optionValue, { [missingField]: optionValue }, optionLabel)
                    }
                  >
                    <span>
                      <span className="block text-xs font-medium">{optionLabel}</span>
                      {typeof suggestion.description === "string" && suggestion.description && (
                        <span className="mt-1 block text-[11px] font-normal text-muted-foreground">
                          {suggestion.description}
                        </span>
                      )}
                    </span>
                  </Button>
                );
              })}
            </div>
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
        )}

      {interactive && result.status === "needs_input" && missingField && suggestions.length === 0 && !["employee_id", "photo_file", "policy_file", "document_id", "request_id"].includes(missingField) && onRespond && (
        <form onSubmit={submitSlot} className="mt-3 space-y-2 border-t border-warning/20 pt-3">
          <label className="block text-xs font-medium text-primary">
            {FIELD_LABELS[missingField] ?? "Required information"}
          </label>
          {(missingField === "update_value" || missingField.startsWith("announcement_") || missingField.startsWith("policy_")) && currentValue !== undefined && (
            <div className="rounded-lg border border-border bg-secondary/60 px-3 py-2 text-xs">
              <span className="font-medium text-primary">Current value: </span>
              <span className="whitespace-pre-wrap text-muted-foreground">
                {typeof currentValue === "boolean"
                  ? currentValue ? "Visible" : "Hidden"
                  : String(currentValue)}
              </span>
            </div>
          )}
          <div className="flex gap-2">
            {["body", "announcement_body"].includes(missingField) ? (
              <Textarea
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder="Enter a new message or type keep"
                disabled={disabled}
                required
              />
            ) : (
              <Input
                type={inputType}
                min={missingField === "end_date" ? minimumDate : undefined}
                max={missingField === "date" ? new Date().toLocaleDateString("en-CA") : undefined}
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

      {policies.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {policies.map((item, index) => {
            const policy = isRecord(item) ? item : {};
            return (
              <div key={String(policy.document_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <p className="font-medium text-primary">{String(policy.title ?? "Policy")}</p>
                <p className="mt-0.5 capitalize text-muted-foreground">
                  {String(policy.category ?? "Uncategorized")} · Version {String(policy.version ?? 1)}
                </p>
                {typeof policy.document_id === "string" && policy.document_id && (
                  <PolicyDownloadButton
                    documentId={policy.document_id}
                    title={String(policy.title ?? "Policy")}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {policySummaries.length > 0 && (
        <div className="mt-3 space-y-2">
          {policySummaries.map((item, index) => {
            const policy = isRecord(item) ? item : {};
            return (
              <div key={String(policy.document_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-3 text-xs">
                <p className="font-semibold text-primary">{String(policy.title ?? "Policy")}</p>
                <p className="mt-1 whitespace-pre-wrap leading-relaxed text-muted-foreground">
                  {String(policy.summary ?? "No summary available.")}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {auditRecords.length > 0 && (
        <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
          {auditRecords.map((item, index) => {
            const audit = isRecord(item) ? item : {};
            return (
              <div key={String(audit.audit_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-primary">{String(audit.tool ?? "Agent tool")}</p>
                  <Badge variant={audit.status === "success" ? "success" : audit.status === "denied" ? "destructive" : "warning"}>
                    {String(audit.status ?? "unknown")}
                  </Badge>
                </div>
                <p className="mt-1 text-muted-foreground">
                  {String(audit.agent ?? "agent")} · {String(audit.created_at ?? "")}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {leaveRequests.length > 0 && (
        <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
          {leaveRequests.map((item, index) => {
            const request = isRecord(item) ? item : {};
            return (
              <div key={String(request.request_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-primary">
                    {String(request.employee ?? request.leave_type ?? "Leave request")}
                  </p>
                  {Boolean(request.status) && (
                    <Badge variant={request.status === "approved" ? "success" : request.status === "rejected" ? "destructive" : "warning"}>
                      {String(request.status)}
                    </Badge>
                  )}
                </div>
                {Boolean(request.employee) && (
                  <p className="mt-1 text-muted-foreground">{String(request.leave_type ?? "Leave")}</p>
                )}
                <p className="mt-1 text-muted-foreground">
                  {String(request.start_date ?? "")} to {String(request.end_date ?? "")}
                </p>
                {Boolean(request.reason) && <p className="mt-1">{String(request.reason)}</p>}
              </div>
            );
          })}
        </div>
      )}

      {attendanceRecords.length > 0 && (
        <div className="mt-3 max-h-80 space-y-2 overflow-y-auto pr-1">
          {attendanceRecords.map((item, index) => {
            const record = isRecord(item) ? item : {};
            return (
              <div key={String(record.attendance_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-primary">{String(record.employee ?? "Employee")}</p>
                  <Badge variant={record.status === "present" ? "success" : record.status === "absent" ? "destructive" : "warning"}>
                    {String(record.status ?? "unknown").replaceAll("_", " ")}
                  </Badge>
                </div>
                <p className="mt-1 text-muted-foreground">
                  {String(record.date ?? "")}
                  {record.check_in ? ` · In: ${String(record.check_in).slice(11, 16)}` : ""}
                  {record.check_out ? ` · Out: ${String(record.check_out).slice(11, 16)}` : ""}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {holidays.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {holidays.map((item, index) => {
            const holiday = isRecord(item) ? item : {};
            return (
              <div key={String(holiday.holiday_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <p className="font-medium text-primary">{String(holiday.name ?? "Holiday")}</p>
                <p className="mt-1 text-muted-foreground">{String(holiday.date ?? "")}</p>
              </div>
            );
          })}
        </div>
      )}

      {announcements.length > 0 && (
        <div className="mt-3 space-y-2">
          {announcements.map((item, index) => {
            const announcement = isRecord(item) ? item : {};
            return (
              <div key={String(announcement.announcement_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <p className="font-medium text-primary">{String(announcement.title ?? "Announcement")}</p>
                <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{String(announcement.body ?? "")}</p>
              </div>
            );
          })}
        </div>
      )}

      {managementRecords.length > 0 && (
        <div className="mt-3 grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
          {managementRecords.map((item, index) => {
            const record = isRecord(item) ? item : {};
            const heading = record.name ?? record.title ?? record.email ?? "Record";
            const subtitle = record.department
              ?? record.description
              ?? (record.role ? `${record.role} · ${record.is_active ? "active" : "inactive"}` : "");
            return (
              <div key={String(record.department_id ?? record.designation_id ?? record.user_id ?? index)} className="rounded-lg bg-secondary/70 px-3 py-2 text-xs">
                <p className="font-medium text-primary">{String(heading)}</p>
                {Boolean(subtitle) && <p className="mt-1 text-muted-foreground">{String(subtitle)}</p>}
              </div>
            );
          })}
        </div>
      )}

      {!balances.length && !employees.length && !policies.length && !policySummaries.length && !auditRecords.length && !leaveRequests.length && !attendanceRecords.length && !holidays.length && !announcements.length && !managementRecords.length && details.length > 0 && (
        <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
          {details.map(([key, item]) => (
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
