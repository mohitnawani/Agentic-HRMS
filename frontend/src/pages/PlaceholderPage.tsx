import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <PageHeader title={title} />
      <EmptyState title="Coming soon" description="This module's UI lands in the next build step." />
    </div>
  );
}
