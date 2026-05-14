import { create } from "zustand";
import type { ConfidenceLevel } from "@/constants";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: string[];
  confidence: ConfidenceLevel | null;
  timestamp: Date;
  isError?: boolean;
}

export type StreamStatus = "idle" | "processing" | "streaming" | "complete" | "error";

export interface StreamState {
  status: StreamStatus;
  tokens: string;
  processingMessage: string | null;
  citations: string[];
  confidence: ConfidenceLevel | null;
  error: string | null;
}

export type StreamAction =
  | { type: "STREAM_START" }
  | { type: "TOKEN"; payload: string }
  | { type: "PROCESSING"; payload: string }
  | { type: "CITATIONS"; payload: string[] }
  | { type: "CONFIDENCE"; payload: ConfidenceLevel }
  | { type: "STREAM_DONE" }
  | { type: "STREAM_ERROR"; payload: string }
  | { type: "RESET" };

export const initialStreamState: StreamState = {
  status: "idle",
  tokens: "",
  processingMessage: null,
  citations: [],
  confidence: null,
  error: null,
};

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case "STREAM_START":
      return { ...initialStreamState, status: "processing" };
    case "TOKEN":
      return {
        ...state,
        status: "streaming",
        tokens: state.tokens + action.payload,
        processingMessage: null,
      };
    case "PROCESSING":
      return { ...state, processingMessage: action.payload };
    case "CITATIONS":
      return { ...state, citations: action.payload };
    case "CONFIDENCE":
      return { ...state, confidence: action.payload };
    case "STREAM_DONE":
      return { ...state, status: "complete" };
    case "STREAM_ERROR":
      return { ...state, status: "error", error: action.payload };
    case "RESET":
      return initialStreamState;
    default:
      return state;
  }
}

interface ChatStoreState {
  messages: ChatMessage[];
  addMessage: (message: ChatMessage) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStoreState>()((set) => ({
  messages: [],

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  clearMessages: () => set({ messages: [] }),
}));
