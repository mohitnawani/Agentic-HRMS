import { HatGlasses, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";
import CitationCard from "./CitationCard";
import ToolResultCard from "./ToolResultCard";
import type { ChatMessageModel } from "./agentTypes";

interface ChatMessageProps {
  message: ChatMessageModel;
  interactive?: boolean;
  disabled?: boolean;
  onRespond?: (
    message: string,
    parameters?: Record<string, unknown>,
    displayMessage?: string,
  ) => void;
}

export default function ChatMessage({
  message,
  interactive,
  disabled,
  onRespond,
}: ChatMessageProps) {
  const assistant = message.role === "assistant";
  const hasStructuredPolicySummary = message.tools?.some((tool) => {
    if (tool.tool !== "policy_summary" || tool.status !== "success") return false;
    const data = tool.data;
    return !Array.isArray(data)
      && data != null
      && Array.isArray(data.summaries)
      && data.summaries.length > 0;
  }) ?? false;

  return (
    <article className={cn("flex gap-3", !assistant && "flex-row-reverse")}>
      <span
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-xl",
          assistant ? "bg-primary text-primary-foreground" : "bg-sidebar-highlight text-primary",
        )}
      >
        {assistant ? <HatGlasses className="size-4" /> : <UserRound className="size-4" />}
      </span>
      <div className={cn("max-w-[88%] sm:max-w-[78%]", !assistant && "text-right")}>
        {!hasStructuredPolicySummary && (
          <div
            className={cn(
              "inline-block whitespace-pre-wrap rounded-2xl px-4 py-3 text-left text-sm leading-6",
              assistant
                ? message.error
                  ? "border border-destructive/20 bg-destructive/5 text-destructive"
                  : "border border-border bg-card text-foreground shadow-sm"
                : "bg-primary text-primary-foreground",
            )}
          >
            {message.content || (
              <span className="inline-flex gap-1" aria-label="Assistant is responding">
                <span className="size-1.5 animate-pulse rounded-full bg-current" />
                <span className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:150ms]" />
                <span className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:300ms]" />
              </span>
            )}
          </div>
        )}
        {message.tools?.map((tool, index) => (
          <ToolResultCard
            key={`${tool.tool ?? tool.agent}-${index}`}
            result={tool}
            interactive={interactive}
            disabled={disabled}
            onRespond={onRespond}
          />
        ))}
        {!!message.sources?.length && (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {message.sources.map((source) => (
              <CitationCard
                key={`${source.document_id}-${source.chunk_index}`}
                source={source}
              />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
