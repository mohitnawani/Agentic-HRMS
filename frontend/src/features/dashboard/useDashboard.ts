import { useQuery } from "@tanstack/react-query";
import { getAdminDashboard, getEmployeeDashboard, getHRDashboard } from "./dashboardApi";

export const useEmployeeDashboard = () =>
  useQuery({ queryKey: ["dashboard", "employee"], queryFn: getEmployeeDashboard });

export const useHRDashboard = () =>
  useQuery({ queryKey: ["dashboard", "hr"], queryFn: getHRDashboard });

export const useAdminDashboard = () =>
  useQuery({ queryKey: ["dashboard", "admin"], queryFn: getAdminDashboard });
