import { createBrowserRouter, Navigate } from "react-router";
import LoginPage from "@/features/auth/LoginPage";
import ProtectedRoute from "./ProtectedRoute";
import AppLayout from "@/layouts/AppLayout";
import ChatPage from "@/features/agent/ChatPage";
import EmployeeDashboard from "@/features/dashboard/EmployeeDashboard";
import HRDashboard from "@/features/dashboard/HRDashboard";
import AdminDashboard from "@/features/dashboard/AdminDashboard";
import EmployeeListPage from "@/features/employees/EmployeeListPage";
import EmployeeForm from "@/features/employees/EmployeeForm";
import EmployeeDetailPage from "@/features/employees/EmployeeDetailPage";
import MyProfilePage from "@/features/employees/MyProfilePage";
import DepartmentPage from "@/features/departments/DepartmentPage";
import DesignationPage from "@/features/designations/DesignationPage";
import AttendanceHistoryPage from "@/features/attendance/AttendanceHistoryPage";
import AttendanceCorrectionPage from "@/features/attendance/AttendanceCorrectionPage";
import LeavePage from "@/features/leave/LeavePage";
import LeaveApprovalsPage from "@/features/leave/LeaveApprovalsPage";
import PoliciesPage from "@/features/policies/PoliciesPage";
import HolidaysPage from "@/features/holidays/HolidaysPage";
import AnnouncementsPage from "@/features/announcements/AnnouncementsPage";
import UsersPage from "@/features/users/UsersPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage/> },
  {
    element: <ProtectedRoute allowedRoles={["employee"]} />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/employee/dashboard", element: <EmployeeDashboard /> },
          { path: "/employee/profile", element: <MyProfilePage /> },
          { path: "/employee/attendance", element: <AttendanceHistoryPage /> },
          { path: "/employee/leave", element: <LeavePage /> },
          { path: "/employee/policies", element: <PoliciesPage /> },
          { path: "/employee/announcements", element: <AnnouncementsPage /> },
          { path: "/employee/assistant", element: <ChatPage /> },
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
          { path: "/hr/attendance", element: <AttendanceCorrectionPage /> },
          { path: "/hr/leave", element: <LeaveApprovalsPage /> },
          { path: "/hr/policies", element: <PoliciesPage /> },
          { path: "/hr/announcements", element: <AnnouncementsPage /> },
          { path: "/hr/assistant", element: <ChatPage /> },
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
          { path: "/admin/holidays", element: <HolidaysPage /> },
          { path: "/admin/announcements", element: <AnnouncementsPage /> },
          { path: "/admin/users", element: <UsersPage /> },
          { path: "/admin/assistant", element: <ChatPage /> },
        ],
      },
    ],
  },
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
