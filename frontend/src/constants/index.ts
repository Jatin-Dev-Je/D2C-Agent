export const METRIC_NAMES = [
  "revenue",
  "orders",
  "ad_spend",
  "roas",
  "impressions",
  "clicks",
  "cogs",
  "refunds",
  "avg_order_value",
  "shipping_cost",
  "rto",
] as const;

export type MetricName = (typeof METRIC_NAMES)[number];

export const SOURCE_TYPES = ["shopify", "meta_ads", "shiprocket"] as const;
export type SourceType = (typeof SOURCE_TYPES)[number];

export const CONFIDENCE_LEVELS = ["high", "medium", "low"] as const;
export type ConfidenceLevel = (typeof CONFIDENCE_LEVELS)[number];

export const METRIC_LABELS: Record<MetricName, string> = {
  revenue:         "Revenue",
  orders:          "Orders",
  ad_spend:        "Ad Spend",
  roas:            "ROAS",
  impressions:     "Impressions",
  clicks:          "Clicks",
  cogs:            "COGS",
  refunds:         "Refunds",
  avg_order_value: "Avg Order Value",
  shipping_cost:   "Shipping Cost",
  rto:             "RTO",
};

export const SOURCE_LABELS: Record<SourceType, string> = {
  shopify:    "Shopify",
  meta_ads:   "Meta Ads",
  shiprocket: "Shiprocket",
};

export const SOURCE_DESCRIPTIONS: Record<SourceType, string> = {
  shopify:    "Orders, revenue, and refunds via Shopify Admin API",
  meta_ads:   "Campaign spend, impressions, and clicks via Meta Graph API",
  shiprocket: "Shipping cost and RTO data via Shiprocket API",
};

export const DEFAULT_API_BASE_URL =
  import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8000";

export const DEFAULT_QUERY_STALE_TIME = 30_000;
export const DEFAULT_QUERY_GC_TIME    = 5 * 60_000;
export const DASHBOARD_LOOKBACK_DAYS  = 30;
export const AGENT_LOGS_PAGE_SIZE     = 50;

export const QUERY_KEYS = {
  dashboard:     ["dashboard"] as const,
  agentLogs:     (offset: number) => ["agent-logs", offset] as const,
  connectorHealth: ["connector-health"] as const,
  metricSummary: (metric: MetricName, start: string, end: string) =>
    ["metric-summary", metric, start, end] as const,
  metricCompare: (metric: MetricName, cs: string, ce: string, ps: string, pe: string) =>
    ["metric-compare", metric, cs, ce, ps, pe] as const,
  metricRoas:      (start: string, end: string) => ["metric-roas", start, end] as const,
  metricCampaigns: (start: string, end: string) => ["metric-campaigns", start, end] as const,
} as const;
