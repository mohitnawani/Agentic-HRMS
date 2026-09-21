import { createBrowserRouter, Navigate } from "react-router";
import LoginPage from "@/features/auth/LoginPage";
import ProtectedRoute from "./ProtectedRoute";
import AppLayout from "@/layouts/AppLayout";
import PlaceholderPage from "@/pages/PlaceholderPage";
import EmployeeDashboard from "@/features/dashboard/EmployeeDashboard";
import HRDashboard from "@/features/dashboard/HRDashboard";
import AdminDashboard from "@/features/dashboard/AdminDashboard";
import EmployeeListPage from "@/features/employees/EmployeeListPage";
import EmployeeForm from "@/features/employees/EmployeeForm";
import EmployeeDetailPage from "@/features/employees/EmployeeDetailPage";
import DepartmentPage from "@/features/departments/DepartmentPage";
import DesignationPage from "@/features/designations/DesignationPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage/> },
  {
    element: <ProtectedRoute allowedRoles={["employee"]} />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/employee/dashboard", element: <EmployeeDashboard /> },
          { path: "/employee/profile", element: <PlaceholderPage title="My Profile" /> },
          { path: "/employee/attendance", element: <PlaceholderPage title="Attendance" /> },
          { path: "/employee/leave", element: <PlaceholderPage title="Leave" /> },
          { path: "/employee/policies", element: <PlaceholderPage title="Policies" /> },
          { path: "/employee/assistant", element: <PlaceholderPage title="Assistant" /> },
        ],
      },
    ],
  },
  {
    element: <ProtectedRoute allowedRoles={["hr"]} />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/hr/dashboard", element: <HRDashboard /> },
          { path: "/hr/employees", element: <EmployeeListPage /> },
          { path: "/hr/employees/new", element: <EmployeeForm /> },
          { path: "/hr/employees/:id", element: <EmployeeDetailPage /> },
          { path: "/hr/attendance", element: <PlaceholderPage title="Attendance" /> },
          { path: "/hr/leave", element: <PlaceholderPage title="Leave Approvals" /> },
          { path: "/hr/policies", element: <PlaceholderPage title="Policies" /> },
          { path: "/hr/assistant", element: <PlaceholderPage title="Assistant" /> },
        ],
      },
    ],
  },
  {
    element: <ProtectedRoute allowedRoles={["admin"]} />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/admin/dashboard", element: <AdminDashboard /> },
          { path: "/admin/employees", element: <EmployeeListPage /> },
          { path: "/admin/employees/new", element: <EmployeeForm /> },
          { path: "/admin/employees/:id", element: <EmployeeDetailPage /> },
          { path: "/admin/departments", element: <DepartmentPage /> },
          { path: "/admin/designations", element: <DesignationPage /> },
          { path: "/admin/users", element: <PlaceholderPage title="Users" /> },
          { path: "/admin/assistant", element: <PlaceholderPage title="Assistant" /> },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
