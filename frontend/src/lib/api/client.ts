import { useSessionStore } from "@/stores/session";
import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: ApiErrorBody,
  ) {
    const message =
      body.detail ?? body.error ?? `Request failed with status ${status}`;
    super(message);
    this.name = "ApiError";
  }

  get isUnauthorized() {
    return this.status === 401;
  }

  get isRateLimited() {
    return this.status === 429;
  }

  get isUnprocessable() {
    return this.status === 422;
  }
}

function buildHeaders(extra?: HeadersInit): Headers {
  const { bearerToken } = useSessionStore.getState();
  const headers = new Headers({
    "Content-Type": "application/json",
    Accept: "application/json",
    ...extra,
  });
  if (bearerToken) {
    headers.set("Authorization", `Bearer ${bearerToken}`);
  }
  return headers;
}

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const { apiBaseUrl } = useSessionStore.getState();
  const url = new URL(path, apiBaseUrl.endsWith("/") ? apiBaseUrl : `${apiBaseUrl}/`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");

  if (!response.ok) {
    const body: ApiErrorBody = isJson
      ? await response.json().catch(() => ({}))
      : { detail: await response.text().catch(() => "Unknown error") };
    throw new ApiError(response.status, body);
  }

  if (response.status === 204 || !isJson) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  signal?: AbortSignal,
): Promise<T> {
  const url = buildUrl(path, params);
  const response = await fetch(url, {
    method: "GET",
    headers: buildHeaders(),
    signal,
  });
  return parseResponse<T>(response);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = buildUrl(path);
  const response = await fetch(url, {
    method: "POST",
    headers: buildHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  return parseResponse<T>(response);
}

export function buildStreamUrl(path: string): string {
  return buildUrl(path);
}

export function buildStreamHeaders(): Headers {
  return buildHeaders({ Accept: "text/event-stream" });
}
