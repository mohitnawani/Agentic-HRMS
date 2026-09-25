import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { HatGlasses, Plus, Send, Square } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAppSelector } from "@/store/hooks";
import ChatMessage from "./ChatMessage";
import { getAgentConversation, streamAgentChat } from "./agentApi";
import type { AgentToolResult, ChatMessageModel } from "./agentTypes";

const WELCOME: ChatMessageModel = {
  id: "welcome",
  role: "assistant",
  content:
    "Hello! I can help with company policies, your HR data, and authorized HR actions. What would you like to do?",
};

const ROLE_SUGGESTIONS = {
  employee: ["How many leaves do I have left?", "What's the work-from-home policy?"],
  hr: [
    "List all employees",
    "Add employee Priya Singh",
    "Upload a policy",
    "Create an announcement",
  ],
  admin: ["Show all employees", "Create a department named Product"],
};

export default function ChatPage() {
  const { role, email } = useAppSelector((state) => state.auth);
  const storageKey = `agent-conversation:${email ?? "anonymous"}`;
  const [conversationId, setConversationId] = useState<string | null>(() =>
    sessionStorage.getItem(storageKey),
  );
  const [messages, setMessages] = useState<ChatMessageModel[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isRestoring, setIsRestoring] = useState(Boolean(conversationId));
  const [status, setStatus] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const initialConversationRef = useRef(conversationId);
  const suggestions = role ? ROLE_SUGGESTIONS[role] : [];

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    const initialConversationId = initialConversationRef.current;
    if (!initialConversationId) return;
    let active = true;
    getAgentConversation(initialConversationId)
      .then((conversation) => {
        if (!active) return;
        const restored: ChatMessageModel[] = conversation.messages.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
        }));
        const pending = conversation.pending_interaction;
        const last = restored.at(-1);
        if (pending && last?.role === "assistant") {
          const tool: AgentToolResult = {
            agent: "action",
            status:
              pending.stage === "confirmation"
                ? "confirmation_required"
                : "needs_input",
            tool: pending.tool,
            message: last.content,
            data: {
              stage: pending.stage,
              ...(pending.missing_field
                ? { missing_field: pending.missing_field }
                : {}),
              ...(pending.parameters && Object.keys(pending.parameters).length
                ? { parameters: pending.parameters }
                : {}),
            },
          };
          last.tools = [tool];
        }
        setMessages(restored.length ? [WELCOME, ...restored] : [WELCOME]);
      })
      .catch(() => {
        sessionStorage.removeItem(storageKey);
        setConversationId(null);
      })
      .finally(() => {
        if (active) setIsRestoring(false);
      });
    return () => {
      active = false;
    };
  }, [storageKey]);

  const updateAssistant = (
    id: string,
    update: (message: ChatMessageModel) => ChatMessageModel,
  ) => {
    setMessages((current) =>
      current.map((message) => (message.id === id ? update(message) : message)),
    );
  };

  const sendMessage = async (
    text: string,
    parameters?: Record<string, unknown>,
    displayMessage?: string,
  ) => {
    const message = text.trim();
    if (!message || isStreaming) return;
    const userMessage: ChatMessageModel = {
      id: crypto.randomUUID(),
      role: "user",
      content: displayMessage ?? message,
    };
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantId, role: "assistant", content: "", tools: [], sources: [] },
    ]);
    setInput("");
    setIsStreaming(true);
    setStatus("Connecting to the assistant...");
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAgentChat(
        {
          message,
          ...(conversationId ? { conversation_id: conversationId } : {}),
          ...(parameters ? { parameters } : {}),
        },
        {
          onConversation: (id) => {
            setConversationId(id);
            sessionStorage.setItem(storageKey, id);
          },
          onStatus: setStatus,
          onToken: (token) => {
            setStatus("");
            updateAssistant(assistantId, (item) => ({
              ...item,
              content: item.content + token,
            }));
          },
          onTool: (tool) =>
            updateAssistant(assistantId, (item) => ({
              ...item,
              tools: [...(item.tools ?? []), tool],
            })),
          onSources: (sources) =>
            updateAssistant(assistantId, (item) => ({ ...item, sources })),
          onDone: (intent) =>
            updateAssistant(assistantId, (item) => ({ ...item, intent })),
          onError: (error) =>
            updateAssistant(assistantId, (item) => ({
              ...item,
              content: error,
              error: true,
            })),
        },
        controller.signal,
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        updateAssistant(assistantId, (item) => ({
          ...item,
          content: error instanceof Error ? error.message : "Unable to reach the assistant.",
          error: true,
        }));
      }
    } finally {
      setIsStreaming(false);
      setStatus("");
      abortRef.current = null;
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void sendMessage(input);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  };

  const newConversation = () => {
    abortRef.current?.abort();
    sessionStorage.removeItem(storageKey);
    setConversationId(null);
    setMessages([WELCOME]);
    setStatus("");
    setIsRestoring(false);
  };

  return (
    <div className="mx-auto flex h-[calc(100svh-4rem)] max-w-6xl flex-col">
      <PageHeader
        title="HR Assistant"
        description="Ask about policies, HR data, or actions available to your role"
        actions={
          <Button variant="outline" onClick={newConversation} disabled={isStreaming}>
            <Plus className="size-4" /> New conversation
          </Button>
        }
      />

      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-border bg-secondary/35 shadow-sm">
        <div className="flex items-center gap-3 border-b border-border bg-card/90 px-4 py-3 sm:px-6">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <HatGlasses className="size-5" />
          </span>
          <div>
            <p className="text-sm font-semibold text-primary">Agentic HRMS Assistant</p>
            <p className="text-xs text-muted-foreground">
              {isRestoring
                ? "Restoring your conversation..."
                : isStreaming
                  ? status || "Responding..."
                  : "Ready · Responses follow your role permissions"}
            </p>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6" aria-live="polite">
          <div className="space-y-5">
            {messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                message={message}
                interactive={index === messages.length - 1 && message.role === "assistant"}
                disabled={isStreaming || isRestoring}
                onRespond={(response, responseParameters, responseDisplay) =>
                  void sendMessage(response, responseParameters, responseDisplay)
                }
              />
            ))}
            {messages.length === 1 && (
              <div className="ml-11 flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void sendMessage(suggestion)}
                    className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="border-t border-border bg-card p-3 sm:p-4">
          <div className="flex items-end gap-2">
            <Textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message the HR assistant..."
              aria-label="Message the HR assistant"
              disabled={isStreaming || isRestoring}
              className="min-h-11 max-h-32 resize-none rounded-xl"
              rows={1}
            />
            {isStreaming ? (
              <Button
                type="button"
                variant="outline"
                className="size-11 shrink-0 px-0"
                onClick={() => abortRef.current?.abort()}
                aria-label="Stop response"
              >
                <Square className="size-4 fill-current" />
              </Button>
            ) : (
              <Button
                type="submit"
                className="size-11 shrink-0 px-0"
                disabled={!input.trim() || isRestoring}
                aria-label="Send message"
              >
                <Send className="size-4" />
              </Button>
            )}
          </div>
          <p className="mt-2 text-center text-[11px] text-muted-foreground">
            Enter to send · Shift+Enter for a new line
          </p>
        </form>
      </section>
    </div>
  );
}
