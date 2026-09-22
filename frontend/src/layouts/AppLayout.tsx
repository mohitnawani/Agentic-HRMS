import { NavLink, Outlet } from "react-router";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { logout } from "@/store/authSlice";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_ITEMS: Record<string, { label: string; path: string }[]> = {
  employee: [
    { label: "Dashboard", path: "/employee/dashboard" },
    { label: "My Profile", path: "/employee/profile" },
    { label: "Attendance", path: "/employee/attendance" },
    { label: "Leave", path: "/employee/leave" },
    { label: "Policies", path: "/employee/policies" },
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
    <div className="flex h-screen overflow-hidden ">
      <aside className="w-64 border-r bg-muted/30 p-4 flex flex-col">
        <div className="text-lg font-semibold mb-6 px-2">Agentic HRMS</div>
        <nav className="flex-1 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "block rounded-md px-3 py-2 text-sm font-medium",
                  isActive ? "bg-primary text-primary-foreground" : "hover:bg-muted"
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t pt-3 mt-3">
          <div className="flex items-center gap-2.5 px-2 mb-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-teal-600 text-sm font-semibold text-white">
              {(email?.charAt(0) ?? "?").toUpperCase()}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">
                {email?.split("@")[0] ?? "User"}
              </span>
              <span className="block text-xs uppercase text-muted-foreground">
                {role ?? ""}
              </span>
            </span>
          </div>
          <Button variant="outline" size="sm" className="w-full" onClick={() => dispatch(logout())}>
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-6 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
