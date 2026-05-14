import { create } from "zustand";
import { persist } from "zustand/middleware";
import { decodeJwtPayload } from "@/lib/auth/session";
import { DEFAULT_API_BASE_URL } from "@/constants";
import type { AuthClaims } from "@/lib/api/types";

interface SessionState {
  apiBaseUrl: string;
  bearerToken: string;
  claims: AuthClaims | null;
  isAuthenticated: boolean;
}

interface SessionActions {
  setApiBaseUrl: (url: string) => void;
  setBearerToken: (token: string) => void;
  clearSession: () => void;
}

type SessionStore = SessionState & SessionActions;

export const useSessionStore = create<SessionStore>()(
  persist(
    (set) => ({
      apiBaseUrl: DEFAULT_API_BASE_URL,
      bearerToken: "",
      claims: null,
      isAuthenticated: false,

      setApiBaseUrl: (url) => set({ apiBaseUrl: url.trim() || DEFAULT_API_BASE_URL }),

      setBearerToken: (token) => {
        const trimmed = token.trim();
        const claims = trimmed ? decodeJwtPayload(trimmed) : null;
        set({
          bearerToken: trimmed,
          claims,
          isAuthenticated: claims !== null,
        });
      },

      clearSession: () =>
        set({
          bearerToken: "",
          claims: null,
          isAuthenticated: false,
        }),
    }),
    {
      name: "d2c-session",
      partialize: (state) => ({
        apiBaseUrl: state.apiBaseUrl,
        bearerToken: state.bearerToken,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.bearerToken) {
          const claims = decodeJwtPayload(state.bearerToken);
          state.claims = claims;
          state.isAuthenticated = claims !== null;
        }
      },
    },
  ),
);
