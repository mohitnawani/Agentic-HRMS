import { store } from "@/store/store";
import { apiClient } from "@/lib/api-client";
import type {
  AgentConversation,
  AgentIntent,
  AgentSource,
  AgentToolResult,
  StreamChatRequest,
} from "./agentTypes";

export const getAgentConversation = (conversationId: string) =>
  apiClient
    .get<AgentConversation>(`/agent/conversations/${conversationId}`)
    .then((response) => response.data);

const API_BASE = (
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

interface StreamHandlers {
  onConversation: (conversationId: string) => void;
  onStatus: (message: string) => void;
  onToken: (text: string) => void;
  onTool: (result: AgentToolResult) => void;
  onSources: (sources: AgentSource[]) => void;
  onDone: (intent: AgentIntent) => void;
  onError: (message: string) => void;
}

interface ParsedEvent {
  event: string;
  data: unknown;
}

function parseEvent(block: string): ParsedEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) as unknown };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function dispatchEvent(parsed: ParsedEvent, handlers: StreamHandlers) {
  const data = parsed.data;
  if (!isRecord(data)) return;
  switch (parsed.event) {
    case "meta":
      if (typeof data.conversation_id === "string") {
        handlers.onConversation(data.conversation_id);
      }
      break;
    case "status":
      if (typeof data.message === "string") handlers.onStatus(data.message);
      break;
    case "token":
      if (typeof data.text === "string") handlers.onToken(data.text);
      break;
    case "tool":
      handlers.onTool(data as unknown as AgentToolResult);
      break;
    case "sources":
      if (Array.isArray(data.items)) {
        handlers.onSources(data.items as AgentSource[]);
      }
      break;
    case "done":
      if (typeof data.intent === "string") {
        handlers.onDone(data.intent as AgentIntent);
      }
      break;
    case "error":
      handlers.onError(
        typeof data.message === "string"
          ? data.message
          : "The assistant could not complete this request.",
      );
      break;
  }
}

export async function streamAgentChat(
  request: StreamChatRequest,
  handlers: StreamHandlers,
  signal: AbortSignal,
) {
  const token = store.getState().auth.accessToken;
  if (!token) throw new Error("Your session has expired. Please sign in again.");

  const response = await fetch(`${API_BASE}/agent/chat/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok) {
    let message = `Assistant request failed (${response.status}).`;
    try {
      const error = (await response.json()) as { detail?: string };
      if (error.detail) message = error.detail;
    } catch {
      // The status-based message remains useful for non-JSON proxy errors.
    }
    throw new Error(message);
  }
  if (!response.body) throw new Error("Streaming is not supported by this browser.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const parsed = parseEvent(block);
      if (parsed) dispatchEvent(parsed, handlers);
    }
    if (done) break;
  }
  if (buffer.trim()) {
    const parsed = parseEvent(buffer);
    if (parsed) dispatchEvent(parsed, handlers);
  }
}
