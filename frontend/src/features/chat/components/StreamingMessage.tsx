import { Bot, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import type { StreamState } from "@/stores/chat";

interface StreamingMessageProps {
  streamState: StreamState;
}

export function StreamingMessage({ streamState }: StreamingMessageProps) {
  const { status, tokens, processingMessage } = streamState;

  if (status === "idle" || status === "complete") return null;

  const isProcessing = status === "processing";
  const isStreaming = status === "streaming";
  const isError = status === "error";

  return (
    <div className="flex gap-3 px-4 py-3 items-start" aria-live="polite" aria-label="AI is responding">
      {/* Avatar */}
      <div
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md",
          isError
            ? "bg-red-500/10 border border-red-500/20"
            : "bg-violet-500/10 border border-violet-500/20",
        )}
      >
        {isProcessing ? (
          <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin" />
        ) : (
          <Bot className={cn("h-3.5 w-3.5", isError ? "text-red-400" : "text-violet-400")} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1">
        {/* Status row */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">AI Employee</span>
          {isProcessing && (
            <span className="text-xs text-blue-400/80">
              {processingMessage ?? "Fetching data…"}
            </span>
          )}
          {isStreaming && (
            <span className="text-xs text-muted-foreground/50">writing</span>
          )}
        </div>

        {/* Bubble */}
        <div className="rounded-lg border border-border bg-card px-3.5 py-2.5 text-sm leading-relaxed min-h-[40px]">
          {isProcessing && !tokens && (
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse [animation-delay:300ms]" />
            </div>
          )}

          {tokens && (
            <span className={cn(isStreaming && "streaming-cursor")}>{tokens}</span>
          )}

          {isError && streamState.error && (
            <span className="text-red-400">{streamState.error}</span>
          )}
        </div>
      </div>
    </div>
  );
}
