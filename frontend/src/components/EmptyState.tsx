import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-secondary/35 px-4 py-12 text-center">
      <span className="mb-3 flex size-10 items-center justify-center rounded-xl bg-background text-primary shadow-sm">
        <Inbox className="size-5" aria-hidden="true" />
      </span>
      <p className="text-sm font-semibold text-primary">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
