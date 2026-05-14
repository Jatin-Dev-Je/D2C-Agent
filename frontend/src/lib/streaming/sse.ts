import { buildStreamHeaders, buildStreamUrl, ApiError } from "@/lib/api/client";
import { parseSseEvent } from "./types";
import type { SseEvent } from "./types";

/**
 * Async generator that streams SSE events from /chat/stream.
 *
 * Handles chunked delivery: a single read() call may contain multiple
 * events or a partial event. The buffer accumulates until a full
 * `data: {...}\n\n` frame is available before yielding.
 */
export async function* streamChatResponse(
  query: string,
  signal: AbortSignal,
): AsyncGenerator<SseEvent> {
  const url = buildStreamUrl("/chat/stream");
  const headers = buildStreamHeaders();

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ query }),
      signal,
    });
  } catch (error) {
    if (signal.aborted) return;
    throw error;
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body);
  }

  if (!response.body) {
    throw new Error("Response body is null — SSE requires a readable body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      if (signal.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by double newlines
      const frames = buffer.split("\n\n");
      // Keep the last (possibly incomplete) frame in buffer
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const trimmed = frame.trim();
        if (!trimmed.startsWith("data:")) continue;

        const jsonStr = trimmed.slice("data:".length).trim();
        if (!jsonStr) continue;

        try {
          const raw: unknown = JSON.parse(jsonStr);
          const event = parseSseEvent(raw);
          if (event) yield event;
        } catch {
          // Malformed JSON — skip silently, stream continues
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
