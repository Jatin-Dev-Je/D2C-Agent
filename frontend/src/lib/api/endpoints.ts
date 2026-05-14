import { apiGet, apiPost } from "./client";
import type {
  AgentLogsResponse,
  AgentRunLog,
  CampaignPerformanceResponse,
  ChatQueryRequest,
  ChatQueryResponse,
  ConnectorHealthResponse,
  ConnectorSyncResponse,
  DashboardResponse,
  HealthResponse,
  MetricCompareResponse,
  MetricSummaryResponse,
  RoasSummaryResponse,
} from "./types";
import type { MetricName } from "@/constants";

// ── System ──────────────────────────────────────────────────────────────────

export const getHealth = (signal?: AbortSignal) =>
  apiGet<HealthResponse>("/health", undefined, signal);

// ── Dashboard ───────────────────────────────────────────────────────────────

export const getDashboard = (signal?: AbortSignal) =>
  apiGet<DashboardResponse>("/dashboard", undefined, signal);

// ── Chat ────────────────────────────────────────────────────────────────────

export const postChatQuery = (body: ChatQueryRequest, signal?: AbortSignal) =>
  apiPost<ChatQueryResponse>("/chat/query", body, signal);

// ── Agents ──────────────────────────────────────────────────────────────────

export const getAgentLogs = (
  limit = 50,
  offset = 0,
  signal?: AbortSignal,
) =>
  apiGet<AgentLogsResponse>("/agents/logs", { limit, offset }, signal);

export const triggerAgent = (signal?: AbortSignal) =>
  apiPost<AgentRunLog>("/agents/trigger", undefined, signal);

// ── Metrics ─────────────────────────────────────────────────────────────────

export const getMetricSummary = (
  metric_name: MetricName,
  start_date: string,
  end_date: string,
  signal?: AbortSignal,
) =>
  apiGet<MetricSummaryResponse>(
    "/metrics/summary",
    { metric_name, start_date, end_date },
    signal,
  );

export const getMetricCompare = (
  metric_name: MetricName,
  current_start: string,
  current_end: string,
  previous_start: string,
  previous_end: string,
  signal?: AbortSignal,
) =>
  apiGet<MetricCompareResponse>(
    "/metrics/compare",
    { metric_name, current_start, current_end, previous_start, previous_end },
    signal,
  );

export const getMetricRoas = (
  start_date: string,
  end_date: string,
  signal?: AbortSignal,
) =>
  apiGet<RoasSummaryResponse>("/metrics/roas", { start_date, end_date }, signal);

export const getMetricCampaigns = (
  start_date: string,
  end_date: string,
  limit = 100,
  signal?: AbortSignal,
) =>
  apiGet<CampaignPerformanceResponse>(
    "/metrics/campaigns",
    { start_date, end_date, limit },
    signal,
  );

// ── Connectors ──────────────────────────────────────────────────────────────

export const getConnectorHealth = (signal?: AbortSignal) =>
  apiGet<ConnectorHealthResponse>("/connectors/health", undefined, signal);

export const triggerConnectorSync = (signal?: AbortSignal) =>
  apiPost<ConnectorSyncResponse>("/connectors/sync", undefined, signal);
