import { createBrowserRouter, Navigate } from "react-router";
import LoginPage from "@/features/auth/LoginPage";
import ProtectedRoute from "./ProtectedRoute";
import AppLayout from "@/layouts/AppLayout";
import PlaceholderPage from "@/pages/PlaceholderPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage/> },
  {
    element: <ProtectedRoute allowedRoles={["employee"]} />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/employee/dashboard", element: <PlaceholderPage title="Employee Dashboard" /> },
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
          { path: "/hr/dashboard", element: <PlaceholderPage title="HR Dashboard" /> },
          { path: "/hr/employees", element: <PlaceholderPage title="Employees" /> },
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
          { path: "/admin/dashboard", element: <PlaceholderPage title="Admin Dashboard" /> },
          { path: "/admin/employees", element: <PlaceholderPage title="Employees" /> },
          { path: "/admin/departments", element: <PlaceholderPage title="Departments" /> },
          { path: "/admin/users", element: <PlaceholderPage title="Users" /> },
          { path: "/admin/assistant", element: <PlaceholderPage title="Assistant" /> },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
