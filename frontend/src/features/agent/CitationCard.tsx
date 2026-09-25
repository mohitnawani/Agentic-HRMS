import { BookOpenText } from "lucide-react";
import type { AgentSource } from "./agentTypes";

export default function CitationCard({ source }: { source: AgentSource }) {
  return (
    <div className="rounded-xl border border-border bg-background/80 p-3 text-left">
      <div className="flex items-start gap-2">
        <BookOpenText className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-primary">
            [{source.source_number}] {source.title}
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Page {source.page_number} · {source.category} · {Math.round(source.similarity * 100)}% match
          </p>
        </div>
      </div>
    </div>
  );
}
