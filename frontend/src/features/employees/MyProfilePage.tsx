import PageHeader from "@/components/PageHeader";
import LoadingSkeleton from "@/components/LoadingSkeleton";
import { useMyProfile } from "./useEmployees";
import ProfileView from "./ProfileView";

export default function MyProfilePage() {
  const { data: employee, isLoading, isError } = useMyProfile();

  if (isLoading) return <LoadingSkeleton rows={4} />;
  if (isError || !employee) return <p className="text-destructive">Profile not found.</p>;

  return (
    <div>
      <PageHeader title="My Profile" />
      <ProfileView employee={employee} />
    </div>
  );
}
