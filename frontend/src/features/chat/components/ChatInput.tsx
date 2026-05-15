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
    if (textareaRef.current) {
      textareaRef.current.value = "";
      textareaRef.current.style.height = "auto";
    }
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
    <div className="px-4 pb-3 pt-0 bg-background">
      <div className="max-w-5xl mx-auto">
      <div className="flex items-end gap-3 rounded-2xl border border-input bg-card px-4 py-1.5 focus-within:ring-1 focus-within:ring-ring transition-shadow shadow-sm">
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder="Ask anything about your D2C business…"
          className="flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none min-h-[22px] max-h-[160px] py-0 leading-relaxed"
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
            className="h-8 w-8 shrink-0 rounded-full text-muted-foreground hover:text-destructive mb-0.5"
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
            className={cn("h-8 w-8 shrink-0 rounded-full mb-0.5", disabled && "opacity-40")}
            aria-label="Send message"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      <p className="mt-1.5 text-[11px] text-muted-foreground/40">
        Shift+Enter for new line · Enter to send
      </p>
      </div>
    </div>
  );
}
