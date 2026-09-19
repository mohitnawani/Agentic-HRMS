import { Navigate, Outlet } from "react-router";
import { useAppSelector } from "@/store/hooks";
import type { Role } from "@/store/authSlice";

interface Props {
  allowedRoles?: Role[];
}

export default function ProtectedRoute({ allowedRoles }: Props) {
  const { accessToken, role } = useAppSelector((state) => state.auth);

  if (!accessToken) return <Navigate to="/login" replace />;
  if (allowedRoles && role && !allowedRoles.includes(role)) {
    return <Navigate to={`/${role}/dashboard`} replace />;
  }
  return <Outlet />;
}
