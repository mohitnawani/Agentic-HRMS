export type AgentIntent = "rag" | "database" | "action" | "general";

export interface AgentSource {
  source_number: number;
  document_id: string;
  title: string;
  category: string;
  page_number: number;
  chunk_index: number;
  similarity: number;
}

export interface AgentToolResult {
  agent: AgentIntent;
  status:
    | "stub"
    | "success"
    | "denied"
    | "error"
    | "needs_input"
    | "confirmation_required"
    | "cancelled";
  message: string;
  tool?: string;
  data?: Record<string, unknown> | Record<string, unknown>[];
}

export interface ChatMessageModel {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: AgentIntent;
  sources?: AgentSource[];
  tools?: AgentToolResult[];
  error?: boolean;
}

export interface StreamChatRequest {
  message: string;
  conversation_id?: string;
  parameters?: Record<string, unknown>;
}

export interface AgentConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface AgentPendingInteraction {
  tool: string;
  stage: "slots" | "confirmation";
  missing_field: string | null;
  parameters?: Record<string, unknown>;
}

export interface AgentConversation {
  conversation_id: string;
  messages: AgentConversationMessage[];
  pending_interaction: AgentPendingInteraction | null;
}
