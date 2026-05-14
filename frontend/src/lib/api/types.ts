import type { ConfidenceLevel, MetricName, SourceType } from "@/constants";

// ── Auth ────────────────────────────────────────────────────────────────────

export interface AuthClaims {
  merchant_id: string;
  email: string;
  role: string;
}

// ── Chat ────────────────────────────────────────────────────────────────────

export interface ChatQueryRequest {
  query: string;
}

export interface ChatQueryResponse {
  answer: string;
  citations: string[];
  confidence: ConfidenceLevel;
}

// ── Agents ──────────────────────────────────────────────────────────────────

export interface AgentRunLog {
  id: string;
  agent_name: string;
  merchant_id: string;
  triggered_at: string;
  observation: string;
  reasoning: string;
  proposed_action: string;
  estimated_saving_inr: string | null;
  citations: string[];
  executed: false;
  status: "proposed" | "failed" | string;
  execution_duration_ms?: number;
  findings?: string[];
}

export interface AgentLogsResponse {
  merchant_id: string;
  logs: AgentRunLog[];
  count: number;
  limit: number;
  offset: number;
}

// ── Metrics ─────────────────────────────────────────────────────────────────

export interface MetricSummaryResponse {
  merchant_id?: string;
  metric_name: MetricName;
  total: string;
  row_count: number;
  start_date: string;
  end_date: string;
}

export interface MetricCompareResponse {
  merchant_id?: string;
  metric_name: MetricName;
  current_value: string;
  previous_value: string;
  delta: string;
  delta_percentage: string;
  trend: "growing" | "declining" | "stable";
  current_start: string;
  current_end: string;
  previous_start: string;
  previous_end: string;
}

export interface RoasSummaryResponse {
  merchant_id: string;
  revenue: string;
  ad_spend: string;
  roas: string;
  start_date: string;
  end_date: string;
}

export interface CampaignRow {
  campaign_id: string;
  campaign_name: string;
  spend: string;
  impressions: string;
  clicks: string;
  source_row_ids: string[];
}

export interface CampaignPerformanceResponse {
  merchant_id: string;
  start_date: string;
  end_date: string;
  campaign_count: number;
  total_spend: string;
  total_clicks: string;
  total_impressions: string;
  campaigns: CampaignRow[];
  limit: number;
}

// ── Connectors ──────────────────────────────────────────────────────────────

export interface ConnectorStatus {
  healthy: boolean;
  source: SourceType;
}

export interface ConnectorHealthResponse {
  merchant_id: string;
  all_healthy: boolean;
  connectors: Record<SourceType, ConnectorStatus>;
  checked_at: string;
}

export interface ConnectorSyncResponse {
  merchant_id: string;
  status: "accepted";
  connectors: SourceType[];
  lookback_days: number;
  message: string;
}

// ── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardMetrics {
  revenue_inr: string;
  orders: string;
  ad_spend_inr: string;
  roas: string;
}

export interface DashboardResponse {
  merchant_id: string;
  period: {
    start: string;
    end: string;
    days: number;
  };
  metrics: DashboardMetrics;
  recent_agent_logs: AgentRunLog[];
  generated_at: string;
}

// ── System ──────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok";
  env: string;
  version: string;
  timestamp: string;
}

// ── Errors ──────────────────────────────────────────────────────────────────

export interface ApiErrorBody {
  detail?: string;
  error?: string;
  type?: string;
}
