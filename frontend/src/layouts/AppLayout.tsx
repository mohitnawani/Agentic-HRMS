import { NavLink, Outlet } from "react-router";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { logout } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Layers, LayoutDashboard, Users, CalendarDays, FileText, Bot, Building2, BriefcaseBusiness, Megaphone, UserRound, LogOut } from "lucide-react";

const NAV_ICONS = { Dashboard: LayoutDashboard, "My Profile": UserRound, Employees: Users, Attendance: CalendarDays, Leave: CalendarDays, "Leave Approvals": CalendarDays, Policies: FileText, Assistant: Bot, Departments: Building2, Designations: BriefcaseBusiness, Users, Holidays: CalendarDays, Announcements: Megaphone };

const NAV_ITEMS: Record<string, { label: string; path: string }[]> = {
  employee: [
    { label: "Dashboard", path: "/employee/dashboard" },
    { label: "My Profile", path: "/employee/profile" },
    { label: "Attendance", path: "/employee/attendance" },
    { label: "Leave", path: "/employee/leave" },
    { label: "Policies", path: "/employee/policies" },
    { label: "Announcements", path: "/employee/announcements" },
    { label: "Assistant", path: "/employee/assistant" },
  ],
  hr: [
    { label: "Dashboard", path: "/hr/dashboard" },
    { label: "Employees", path: "/hr/employees" },
    { label: "Attendance", path: "/hr/attendance" },
    { label: "Leave Approvals", path: "/hr/leave" },
    { label: "Policies", path: "/hr/policies" },
    { label: "Announcements", path: "/hr/announcements" },
    { label: "Assistant", path: "/hr/assistant" },
  ],
  admin: [
    { label: "Dashboard", path: "/admin/dashboard" },
    { label: "Employees", path: "/admin/employees" },
    { label: "Departments", path: "/admin/departments" },
    { label: "Designations", path: "/admin/designations" },
    { label: "Users", path: "/admin/users" },
    { label: "Holidays", path: "/admin/holidays" },
    { label: "Announcements", path: "/admin/announcements" },
    { label: "Assistant", path: "/admin/assistant" },
  ],
};

export default function AppLayout() {
  const { role, email } = useAppSelector((state) => state.auth);
  const dispatch = useAppDispatch();
  const items = role ? NAV_ITEMS[role] : [];

  return (
    <div className="flex h-svh overflow-hidden bg-background p-2 sm:gap-2 sm:p-3">
      <aside className="flex w-16 shrink-0 flex-col overflow-y-auto rounded-2xl bg-primary p-2 text-primary-foreground sm:w-60 sm:p-4">
        <div className="mb-8 flex items-center justify-center gap-3 pt-3 sm:justify-start sm:px-2"><Layers className="size-6 shrink-0 text-sidebar-highlight" aria-hidden="true" /><span className="hidden text-lg font-semibold tracking-tight sm:block">Agentic HRMS</span></div>
        <p className="mb-3 hidden px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-white/55 sm:block">Workspace</p>
        <nav aria-label="Main navigation" className="flex-1 space-y-1.5">
          {items.map((item) => {
            const Icon = NAV_ICONS[item.label as keyof typeof NAV_ICONS] ?? FileText;
            return (
            <NavLink
              key={item.path}
              to={item.path}
              aria-label={item.label}
              title={item.label}
              className={({ isActive }) =>
                cn(
                  "flex min-h-11 items-center justify-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-sidebar-highlight sm:justify-start",
                  isActive ? "bg-sidebar-highlight text-primary" : "text-white/75 hover:bg-white/10 hover:text-white"
                )
              }
            >
              <Icon className="size-[18px] shrink-0" aria-hidden="true" /><span className="hidden sm:block">{item.label}</span>
            </NavLink>
          ); })}
        </nav>
        <div className="mt-6 border-t border-white/15 pt-4">
          <div className="mb-4 flex items-center justify-center gap-2.5 sm:justify-start sm:px-2">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-sm font-semibold text-sidebar-highlight">
              {(email?.charAt(0) ?? "?").toUpperCase()}
            </span>
            <span className="hidden min-w-0 sm:block">
              <span className="block truncate text-sm font-medium">
                {email?.split("@")[0] ?? "User"}
              </span>
              <span className="mt-0.5 block text-[10px] uppercase tracking-wider text-white/60">
                {role ?? ""}
              </span>
            </span>
          </div>
          <Button variant="outline" size="sm" aria-label="Log out" title="Log out" className="h-10 w-full border-white/20 bg-transparent px-2 text-white/80 hover:bg-white/10 hover:text-white" onClick={() => dispatch(logout())}>
            <LogOut className="size-4 shrink-0" aria-hidden="true" /><span className="hidden sm:inline">Log out</span>
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto px-3 py-5 sm:p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
