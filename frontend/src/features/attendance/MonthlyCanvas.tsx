import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useMonthCalendar } from "./useAttendance";
import type { CalendarDay } from "./attendanceApi";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const CELL_BG: Record<string, string> = {
  present: "bg-green-50 border-green-200",
  late: "bg-amber-50 border-amber-200",
  half_day: "bg-amber-50 border-amber-200",
  on_leave: "bg-teal-50 border-teal-200",
  leave_pending: "bg-orange-50 border-orange-200",
  weekend: "bg-gray-50 border-gray-200",
  absent: "bg-red-50 border-red-200",
  missing: "bg-blue-50 border-blue-200",
  plain: "bg-white border-gray-200",
};

const STATUS_TEXT: Record<string, string> = {
  present: "text-green-700",
  late: "text-amber-700",
  half_day: "text-amber-700",
  on_leave: "text-teal-700",
  leave_pending: "text-orange-700",
  absent: "text-red-700",
  missing: "text-blue-700",
};

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtOvertime(mins: number) {
  const sign = mins >= 0 ? "+" : "-";
  const abs = Math.abs(mins);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  return h > 0 ? `${sign}${h}h${m ? ` ${m}m` : ""}` : `${sign}${m}m`;
}

function cellKind(day: CalendarDay): string {
  if (day.before_joining) return "plain";
  if (day.missing_punch) return "missing";
  if (day.state === "weekend" || day.state === "upcoming") return day.state === "weekend" ? "weekend" : "plain";
  return day.state;
}

function DayCell({ day }: { day: CalendarDay }) {
  const kind = cellKind(day);
  const num = Number(day.date.slice(8, 10));

  return (
    <div className={cn("min-h-24 rounded-md border p-1.5 text-xs", CELL_BG[kind])}>
      <p className="font-medium text-gray-900">{num}</p>
      {day.before_joining || day.state === "upcoming" ? null
      : day.state === "weekend" && !day.missing_punch ? (
        <p className="mt-1 text-gray-500">Weekend Off</p>
      ) : day.missing_punch ? (
        <>
          <p className="mt-1 font-medium text-blue-700">Missing punch</p>
          {day.check_in && <p className="text-gray-600">In {fmtTime(day.check_in)}</p>}
        </>
      ) : day.state === "on_leave" || day.state === "leave_pending" ? (
        <>
          <p className={cn("mt-1 font-medium", STATUS_TEXT[day.state])}>{day.leave_name}</p>
          <p className="text-gray-600">{day.leave_status === "approved" ? "Approved" : "Pending"}</p>
        </>
      ) : day.state === "absent" ? (
        <p className="mt-1 font-medium text-red-700">Absent</p>
      ) : (
        <>
          <p className={cn("mt-1 font-medium capitalize", STATUS_TEXT[day.state] ?? "text-gray-700")}>
            {day.state.replace("_", " ")}
          </p>
          {day.check_in && (
            <p className="font-medium text-gray-900">
              {fmtTime(day.check_in)}{day.check_out ? ` - ${fmtTime(day.check_out)}` : ""}
            </p>
          )}
          {day.overtime_minutes !== null && day.overtime_minutes !== undefined && (
            <span className={cn(
              "mt-1 inline-block rounded-full px-1.5 py-0.5 text-[11px] font-medium",
              day.overtime_minutes >= 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
            )}>
              {fmtOvertime(day.overtime_minutes)}
            </span>
          )}
        </>
      )}
    </div>
  );
}

export default function MonthlyCanvas() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const { data, isLoading, isError } = useMonthCalendar(year, month);

  const shift = (delta: number) => {
    const d = new Date(year, month - 1 + delta, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth() + 1);
  };

  const monthLabel = new Date(year, month - 1, 1).toLocaleDateString([], { month: "long", year: "numeric" });
  const leadBlanks = data && data.days.length > 0 ? new Date(data.days[0].date + "T00:00:00").getDay() : 0;

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-gray-500">Monthly Canvas</p>
          <h2 className="text-2xl font-semibold">{monthLabel}</h2>
        </div>
        <div className="flex gap-2">
          <button type="button" aria-label="Previous month" onClick={() => shift(-1)}
            className="rounded-md border px-2 py-1 hover:bg-gray-50">
            <ChevronLeft size={18} />
          </button>
          <button type="button" aria-label="Next month" onClick={() => shift(1)}
            className="rounded-md border px-2 py-1 hover:bg-gray-50">
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {isLoading && <div className="mt-4"><LoadingSkeleton rows={5} /></div>}
      {isError && <p className="mt-4 text-sm text-red-700">Failed to load calendar.</p>}
      {data && (
        <div className="mt-4 grid grid-cols-7 gap-2">
          {WEEKDAYS.map((d) => (
            <p key={d} className="pb-1 text-center text-xs text-gray-500">{d}</p>
          ))}
          {Array.from({ length: leadBlanks }).map((_, i) => (
            <div key={`blank-${i}`} />
          ))}
          {data.days.map((day) => (
            <DayCell key={day.date} day={day} />
          ))}
        </div>
      )}
    </div>
  );
}
