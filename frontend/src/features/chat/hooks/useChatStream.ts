import { useCallback, useReducer, useRef } from "react";
import { streamChatResponse } from "@/lib/streaming/sse";
import { useChatStore, streamReducer, initialStreamState } from "@/stores/chat";
import type { ConfidenceLevel } from "@/constants";

/**
 * Manages the streaming chat lifecycle.
 *
 * Design decisions:
 * - Stream state (tokens, processing status) is ephemeral local state via useReducer.
 *   It drives the StreamingMessage component but does NOT live in Zustand.
 * - Refs accumulate the final content during the stream to avoid stale closures.
 * - Messages are only committed to the Zustand store at two points:
 *   1. User message — immediately on send (optimistic)
 *   2. Assistant message — only when the stream completes with actual content
 *   This eliminates the empty-placeholder flash that occurs when updating
 *   a pre-inserted message in place.
 *
 * Stream state machine: idle → processing → streaming → complete | error
 */
export function useChatStream() {
  const [streamState, dispatch] = useReducer(streamReducer, initialStreamState);
  const abortRef = useRef<AbortController | null>(null);

  // Accumulate stream output in refs — avoids stale closure problems
  const tokensRef = useRef("");
  const citationsRef = useRef<string[]>([]);
  const confidenceRef = useRef<ConfidenceLevel | null>(null);

  const addMessage = useChatStore((s) => s.addMessage);

  const sendMessage = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;

      // Cancel any in-flight stream
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      // Reset accumulators
      tokensRef.current = "";
      citationsRef.current = [];
      confidenceRef.current = null;

      // Commit user message immediately
      addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        citations: [],
        confidence: null,
        timestamp: new Date(),
      });

      dispatch({ type: "STREAM_START" });

      try {
        for await (const event of streamChatResponse(trimmed, controller.signal)) {
          if (controller.signal.aborted) break;

          switch (event.type) {
            case "token":
              tokensRef.current += event.token;
              dispatch({ type: "TOKEN", payload: event.token });
              break;

            case "processing":
              dispatch({ type: "PROCESSING", payload: event.message });
              break;

            case "citations":
              citationsRef.current = event.citations;
              dispatch({ type: "CITATIONS", payload: event.citations });
              break;

            case "confidence":
              confidenceRef.current = event.confidence;
              dispatch({ type: "CONFIDENCE", payload: event.confidence });
              break;

            case "error":
              dispatch({ type: "STREAM_ERROR", payload: event.message });
              addMessage({
                id: crypto.randomUUID(),
                role: "assistant",
                content: event.message,
                citations: [],
                confidence: null,
                timestamp: new Date(),
                isError: true,
              });
              return;

            case "done":
              // Commit assistant message and clear stream state in the same
              // synchronous block — React 18 automatic batching ensures a
              // single render, so StreamingMessage and MessageBubble swap
              // without a visible flash.
              addMessage({
                id: crypto.randomUUID(),
                role: "assistant",
                content: tokensRef.current,
                citations: citationsRef.current,
                confidence: confidenceRef.current,
                timestamp: new Date(),
                isError: false,
              });
              dispatch({ type: "STREAM_DONE" });
              break;
          }
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        const message =
          error instanceof Error ? error.message : "Connection failed. Please retry.";
        dispatch({ type: "STREAM_ERROR", payload: message });
        addMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          content: message,
          citations: [],
          confidence: null,
          timestamp: new Date(),
          isError: true,
        });
      }
    },
    [addMessage],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "RESET" });
  }, []);

  return {
    streamState,
    sendMessage,
    abort,
    isStreaming: streamState.status === "streaming" || streamState.status === "processing",
  };
}
