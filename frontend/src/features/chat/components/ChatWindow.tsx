import { useEffect, useRef, useCallback } from "react";
import { Trash2, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/EmptyState";
import { MessageBubble } from "./MessageBubble";
import { StreamingMessage } from "./StreamingMessage";
import { ChatInput } from "./ChatInput";
import { useChatStream } from "../hooks/useChatStream";
import { useChatStore } from "@/stores/chat";
import { useSessionStore } from "@/stores/session";
import { QUICK_PROMPTS } from "../types";
import { Link } from "react-router-dom";

export function ChatWindow() {
  const { messages, clearMessages } = useChatStore();
  const { streamState, sendMessage, abort, isStreaming } = useChatStream();
  const { isAuthenticated } = useSessionStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isNearBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
  }, []);

  useEffect(() => {
    if (isNearBottom()) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages.length, streamState.tokens, isNearBottom]);

  const handleSend = useCallback(
    (query: string) => sendMessage(query),
    [sendMessage],
  );

  const hasMessages = messages.length > 0;
  const isActive    = isStreaming || hasMessages;
  const showPrompts = !isActive && isAuthenticated;

  return (
    <div className="flex h-full flex-col bg-background">

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Grounded Chat</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Every number traces back to a source row
          </p>
        </div>
        {hasMessages && !isStreaming && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearMessages}
            className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="h-3 w-3" />
            Clear
          </Button>
        )}
      </div>

      {/* Messages / Empty state */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {!isActive ? (
          <div className="flex flex-col items-center justify-center h-full px-8 text-center">
            <EmptyState
              icon={MessageSquare}
              title="Ask your AI employee anything"
              description="Revenue, ROAS, ad spend, campaign performance — all grounded in real data."
            />
            {!isAuthenticated && (
              <p className="mt-4 text-xs text-muted-foreground">
                Set your bearer token in{" "}
                <Link to="/settings" className="underline underline-offset-2 hover:text-foreground">
                  Settings
                </Link>{" "}
                to start chatting.
              </p>
            )}
          </div>
        ) : (
          <div className="py-2">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {isStreaming && <StreamingMessage streamState={streamState} />}
            <div ref={bottomRef} className="h-4" />
          </div>
        )}
      </div>

      {/* Quick prompts — left-aligned with chat bar, pinned above input */}
      {showPrompts && (
        <div className="px-4 pb-1.5">
          <div className="max-w-5xl mx-auto flex flex-wrap gap-1.5">
            {QUICK_PROMPTS.map((prompt) => (
              <button
                key={prompt.query}
                type="button"
                onClick={() => handleSend(prompt.query)}
                className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-all duration-150 whitespace-nowrap"
              >
                {prompt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        onAbort={abort}
        isStreaming={isStreaming}
        disabled={!isAuthenticated}
      />
    </div>
  );
}
