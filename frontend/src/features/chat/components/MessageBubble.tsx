import { Bot, User, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { CitationChip } from "./CitationChip";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { ChatMessage } from "@/stores/chat";
import { formatRelative } from "@/lib/utils/dates";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isAssistant = message.role === "assistant";
  const isError = message.isError === true;

  return (
    <div className={cn("group flex gap-3 px-4 py-3 animate-fade-up items-start")}>
      {/* Avatar */}
      <div
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors",
          isError
            ? "bg-red-500/10 border border-red-500/20"
            : isAssistant
              ? "bg-violet-500/10 border border-violet-500/20"
              : "bg-primary/10 border border-primary/20",
        )}
        aria-hidden
      >
        {isError ? (
          <AlertCircle className="h-3.5 w-3.5 text-red-400" />
        ) : isAssistant ? (
          <Bot className="h-3.5 w-3.5 text-violet-400" />
        ) : (
          <User className="h-3.5 w-3.5 text-primary" />
        )}
      </div>

      {/* Content */}
      <div className={cn("flex-1 min-w-0 space-y-1", isAssistant ? "" : "max-w-[85%]")}>
        {/* Meta row */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">
            {isAssistant ? "AI Employee" : "You"}
          </span>
          <span className="text-xs text-muted-foreground/40 opacity-0 group-hover:opacity-100 transition-opacity">
            {formatRelative(message.timestamp.toISOString())}
          </span>
        </div>

        {/* Bubble */}
        <div
          className={cn(
            "rounded-lg px-3.5 py-2.5 text-sm leading-relaxed",
            isError
              ? "bg-red-500/5 border border-red-500/20 text-red-300"
              : isAssistant
                ? "bg-card border border-border text-foreground"
                : "bg-primary/10 border border-primary/20 text-foreground",
          )}
        >
          {message.content || (
            <span className="text-muted-foreground/50 italic text-xs">Empty response</span>
          )}
        </div>

        {/* Citations + Confidence (assistant only, non-error) */}
        {isAssistant && !isError && message.content && (
          <div className="space-y-2 pt-0.5">
            {message.citations.length > 0 && <CitationChip citations={message.citations} />}
            {message.confidence && <ConfidenceBadge confidence={message.confidence} />}
          </div>
        )}
      </div>
    </div>
  );
}
