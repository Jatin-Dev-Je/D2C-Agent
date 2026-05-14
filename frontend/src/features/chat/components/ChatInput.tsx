import { useRef, useCallback, type KeyboardEvent } from "react";
import { Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

interface ChatInputProps {
  onSend: (query: string) => void;
  onAbort: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, onAbort, isStreaming, disabled }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const value = textareaRef.current?.value.trim() ?? "";
    if (!value || isStreaming) return;
    onSend(value);
    if (textareaRef.current) textareaRef.current.value = "";
    // Reset height
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  return (
    <div className="border-t border-border bg-background/80 backdrop-blur-sm px-4 py-3">
      <div className="flex items-end gap-2 rounded-lg border border-input bg-card px-3 py-2 focus-within:ring-1 focus-within:ring-ring transition-shadow">
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder="Ask anything about your D2C business…"
          className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none min-h-[28px] max-h-[160px] py-0.5 leading-relaxed"
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={disabled}
          aria-label="Chat input"
        />

        {isStreaming ? (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            onClick={onAbort}
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
            aria-label="Stop generation"
          >
            <Square className="h-3.5 w-3.5" />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            onClick={handleSend}
            disabled={disabled}
            className={cn("h-7 w-7 shrink-0", disabled && "opacity-50")}
            aria-label="Send message"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      <p className="mt-1.5 text-center text-xs text-muted-foreground/50">
        Shift+Enter for new line · Enter to send
      </p>
    </div>
  );
}
