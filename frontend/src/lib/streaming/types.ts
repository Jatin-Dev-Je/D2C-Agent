import type { ConfidenceLevel } from "@/constants";

export type SseEventType =
  | "token"
  | "processing"
  | "citations"
  | "confidence"
  | "error"
  | "done";

export type SseTokenEvent = {
  type: "token";
  token: string;
};

export type SseProcessingEvent = {
  type: "processing";
  message: string;
};

export type SseCitationsEvent = {
  type: "citations";
  citations: string[];
};

export type SseConfidenceEvent = {
  type: "confidence";
  confidence: ConfidenceLevel;
};

export type SseErrorEvent = {
  type: "error";
  message: string;
};

export type SseDoneEvent = {
  type: "done";
};

export type SseEvent =
  | SseTokenEvent
  | SseProcessingEvent
  | SseCitationsEvent
  | SseConfidenceEvent
  | SseErrorEvent
  | SseDoneEvent;

function isSseEvent(value: unknown): value is SseEvent {
  if (typeof value !== "object" || value === null) return false;
  const obj = value as Record<string, unknown>;
  const validTypes: SseEventType[] = [
    "token",
    "processing",
    "citations",
    "confidence",
    "error",
    "done",
  ];
  return typeof obj["type"] === "string" && validTypes.includes(obj["type"] as SseEventType);
}

export function parseSseEvent(raw: unknown): SseEvent | null {
  if (!isSseEvent(raw)) return null;
  return raw;
}
