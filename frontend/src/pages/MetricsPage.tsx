import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from "recharts";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge } from "@/components/ui/badge";
import {
  useMetricSummary,
  useMetricCompare,
  useMetricRoas,
  useMetricCampaigns,
} from "@/features/metrics/hooks/useMetrics";
import { last7Days, previous7Days, last30Days } from "@/lib/utils/dates";
import {
  formatCompact,
  formatCurrency,
  formatPercentage,
  formatRoas,
  formatNumber,
  parseDecimal,
} from "@/lib/utils/format";
import { METRIC_LABELS, METRIC_NAMES } from "@/constants";
import type { MetricName } from "@/constants";

// ── Shared chart theme ────────────────────────────────────────────────────────
const CHART_COLORS = {
  primary:   "#6366f1",
  secondary: "#3f3f46",
  emerald:   "#10b981",
  amber:     "#f59e0b",
  violet:    "#8b5cf6",
  muted:     "#71717a",
  border:    "#27272a",
  tooltip:   "#0a0a0f",
};

const tooltipStyle = {
  backgroundColor: CHART_COLORS.tooltip,
  border: `1px solid ${CHART_COLORS.border}`,
  borderRadius: "6px",
  fontSize: "12px",
  color: "#fafafa",
};

// ── Metric picker ─────────────────────────────────────────────────────────────
function MetricSelect({ value, onChange }: { value: MetricName; onChange: (v: MetricName) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {METRIC_NAMES.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
            value === m
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
          }`}
        >
          {METRIC_LABELS[m]}
        </button>
      ))}
    </div>
  );
}

// ── Trend badge ───────────────────────────────────────────────────────────────
function TrendBadge({ delta, percentage }: { delta: string; percentage: string }) {
  const isPositive = !delta.startsWith("-");
  return (
    <Badge variant={isPositive ? "success" : "danger"}>
      {formatPercentage(percentage)}
    </Badge>
  );
}

// ── Compare chart ─────────────────────────────────────────────────────────────
function CompareChart({
  currentValue,
  previousValue,
  label,
}: {
  currentValue: string;
  previousValue: string;
  label: string;
}) {
  const cur = parseDecimal(currentValue);
  const prev = parseDecimal(previousValue);
  const data = [
    { name: "This Week", value: cur },
    { name: "Last Week", value: prev },
  ];
  const max = Math.max(cur, prev, 1);

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} barSize={56} margin={{ top: 20, right: 8, left: 8, bottom: 0 }}>
        <XAxis
          dataKey="name"
          axisLine={false}
          tickLine={false}
          tick={{ fill: CHART_COLORS.muted, fontSize: 12 }}
        />
        <YAxis hide domain={[0, max * 1.15]} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value: number) => [formatCompact(String(value)), label]}
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          <LabelList
            dataKey="value"
            position="top"
            formatter={(v: number) => formatCompact(String(v))}
            style={{ fill: "#fafafa", fontSize: 11, fontWeight: 600 }}
          />
          <Cell fill={CHART_COLORS.primary} />
          <Cell fill={CHART_COLORS.secondary} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── ROAS visual ───────────────────────────────────────────────────────────────
function RoasBreakdown({
  revenue,
  adSpend,
  roas,
}: {
  revenue: string;
  adSpend: string;
  roas: string;
}) {
  const rev = parseDecimal(revenue);
  const spend = parseDecimal(adSpend);
  const spendRatio = rev > 0 ? Math.min((spend / rev) * 100, 100) : 0;

  const data = [
    { name: "Revenue", value: rev, fill: CHART_COLORS.emerald },
    { name: "Ad Spend", value: spend, fill: CHART_COLORS.amber },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-border bg-card/50 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">ROAS</p>
          <p className="text-2xl font-bold text-violet-400 tabular">{formatRoas(roas)}</p>
        </div>
        <div className="rounded-lg border border-border bg-card/50 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Revenue</p>
          <p className="text-2xl font-bold text-emerald-400 tabular">{formatCompact(revenue)}</p>
        </div>
        <div className="rounded-lg border border-border bg-card/50 p-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Ad Spend</p>
          <p className="text-2xl font-bold text-amber-400 tabular">{formatCompact(adSpend)}</p>
        </div>
      </div>

      <div>
        <p className="text-xs text-muted-foreground mb-3">Revenue vs Ad Spend</p>
        <ResponsiveContainer width="100%" height={120}>
          <BarChart data={data} layout="vertical" barSize={24} margin={{ left: 60, right: 40, top: 0, bottom: 0 }}>
            <XAxis type="number" hide domain={[0, rev * 1.1]} />
            <YAxis
              type="category"
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: CHART_COLORS.muted, fontSize: 12 }}
              width={55}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value: number) => [formatCompact(String(value))]}
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              <LabelList
                dataKey="value"
                position="right"
                formatter={(v: number) => formatCompact(String(v))}
                style={{ fill: "#fafafa", fontSize: 11, fontWeight: 600 }}
              />
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="text-xs text-muted-foreground/70 border-t border-border pt-3">
        {spendRatio.toFixed(1)}% of revenue was spent on ads ·{" "}
        {parseDecimal(roas) >= 3
          ? "Healthy return on ad spend"
          : "Below 3x target — consider optimising campaigns"}
      </p>
    </div>
  );
}

// ── Campaign chart ────────────────────────────────────────────────────────────
function CampaignChart({ campaigns }: { campaigns: { campaign_name: string; spend: string }[] }) {
  const data = campaigns.slice(0, 6).map((c) => ({
    name: c.campaign_name.length > 22 ? `${c.campaign_name.slice(0, 22)}…` : c.campaign_name,
    spend: parseDecimal(c.spend),
  }));

  if (data.length === 0) return null;

  return (
    <div className="px-4 pt-4 pb-2">
      <p className="text-xs text-muted-foreground mb-3">Spend by Campaign</p>
      <ResponsiveContainer width="100%" height={data.length * 36 + 16}>
        <BarChart data={data} layout="vertical" barSize={18} margin={{ left: 0, right: 64, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fill: CHART_COLORS.muted, fontSize: 11 }}
            width={150}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value: number) => [formatCurrency(String(value)), "Spend"]}
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
          />
          <Bar dataKey="spend" fill={CHART_COLORS.amber} radius={[0, 4, 4, 0]}>
            <LabelList
              dataKey="spend"
              position="right"
              formatter={(v: number) => formatCurrency(String(v))}
              style={{ fill: CHART_COLORS.muted, fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function MetricsPage() {
  const [selectedMetric, setSelectedMetric] = useState<MetricName>("revenue");

  const { start: cur7Start, end: cur7End } = last7Days();
  const { start: prev7Start, end: prev7End } = previous7Days();
  const { start: d30Start, end: d30End } = last30Days();

  const summary   = useMetricSummary(selectedMetric, d30Start, d30End);
  const compare   = useMetricCompare(selectedMetric, cur7Start, cur7End, prev7Start, prev7End);
  const roas      = useMetricRoas(d30Start, d30End);
  const campaigns = useMetricCampaigns(d30Start, d30End);

  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Metrics" description="Explore grounded metrics across your D2C stack" />

      <div className="flex-1 overflow-auto p-6 space-y-5">
        <MetricSelect value={selectedMetric} onChange={setSelectedMetric} />

        <Tabs defaultValue="summary">
          <TabsList>
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="compare">Week Comparison</TabsTrigger>
            <TabsTrigger value="roas">ROAS</TabsTrigger>
            <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          </TabsList>

          {/* ── Summary ──────────────────────────────────────────────────── */}
          <TabsContent value="summary">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  {METRIC_LABELS[selectedMetric]} — Last 30 Days
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summary.isLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-10 w-40" />
                    <Skeleton className="h-4 w-28" />
                  </div>
                ) : summary.data ? (
                  <div className="space-y-4">
                    <div>
                      <p className="text-4xl font-bold tracking-tight tabular">
                        {formatCompact(summary.data.total)}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {summary.data.row_count} data points from{" "}
                        {new Date(summary.data.start_date).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                        {" "}–{" "}
                        {new Date(summary.data.end_date).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                      </p>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-secondary overflow-hidden">
                      <div className="h-full bg-primary rounded-full w-full animate-pulse" />
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">No data available for this metric</p>
                    <p className="text-xs text-muted-foreground/60 mt-1">
                      Sync your connectors to start seeing data
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Compare ──────────────────────────────────────────────────── */}
          <TabsContent value="compare">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">
                  {METRIC_LABELS[selectedMetric]} — This Week vs Last Week
                </CardTitle>
              </CardHeader>
              <CardContent>
                {compare.isLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-[180px] w-full" />
                    <Skeleton className="h-4 w-48" />
                  </div>
                ) : compare.data ? (
                  <div className="space-y-5">
                    <CompareChart
                      currentValue={compare.data.current_value}
                      previousValue={compare.data.previous_value}
                      label={METRIC_LABELS[selectedMetric]}
                    />
                    <div className="flex items-center gap-3 border-t border-border pt-4">
                      <TrendBadge
                        delta={compare.data.delta}
                        percentage={compare.data.delta_percentage}
                      />
                      <span className="text-sm text-muted-foreground capitalize">
                        {compare.data.trend}
                      </span>
                      <span className="text-xs text-muted-foreground/60 ml-auto">
                        Δ {formatCompact(compare.data.delta)}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">No comparison data available</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── ROAS ─────────────────────────────────────────────────────── */}
          <TabsContent value="roas">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">ROAS — Last 30 Days</CardTitle>
              </CardHeader>
              <CardContent>
                {roas.isLoading ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-4">
                      {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 rounded-lg" />
                      ))}
                    </div>
                    <Skeleton className="h-[120px] w-full" />
                  </div>
                ) : roas.data ? (
                  <RoasBreakdown
                    revenue={roas.data.revenue}
                    adSpend={roas.data.ad_spend}
                    roas={roas.data.roas}
                  />
                ) : (
                  <div className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">No ROAS data available</p>
                    <p className="text-xs text-muted-foreground/60 mt-1">
                      Connect Shopify + Meta Ads to calculate ROAS
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Campaigns ────────────────────────────────────────────────── */}
          <TabsContent value="campaigns">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Campaign Performance — Last 30 Days</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {campaigns.isLoading ? (
                  <div className="divide-y divide-border">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="flex items-center justify-between px-4 py-3">
                        <Skeleton className="h-3.5 w-40" />
                        <Skeleton className="h-3.5 w-20" />
                      </div>
                    ))}
                  </div>
                ) : campaigns.data && campaigns.data.campaigns.length > 0 ? (
                  <>
                    {/* Summary stats */}
                    <div className="grid grid-cols-3 gap-0 border-b border-border">
                      {[
                        { label: "Total Spend", value: formatCompact(campaigns.data.total_spend) },
                        { label: "Total Clicks", value: formatNumber(campaigns.data.total_clicks) },
                        { label: "Impressions", value: formatCompact(campaigns.data.total_impressions) },
                      ].map(({ label, value }) => (
                        <div key={label} className="px-4 py-3 border-r border-border last:border-0">
                          <p className="text-xs text-muted-foreground">{label}</p>
                          <p className="text-base font-semibold mt-0.5 tabular">{value}</p>
                        </div>
                      ))}
                    </div>

                    {/* Chart */}
                    <CampaignChart campaigns={campaigns.data.campaigns} />

                    {/* Table */}
                    <div className="divide-y divide-border border-t border-border">
                      {campaigns.data.campaigns.map((c) => (
                        <div key={c.campaign_id} className="flex items-center justify-between px-4 py-2.5 hover:bg-accent/30 transition-colors">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium truncate max-w-[240px]">{c.campaign_name}</p>
                            <p className="text-xs text-muted-foreground/60 font-mono">{c.campaign_id}</p>
                          </div>
                          <div className="flex items-center gap-5 shrink-0">
                            <div className="text-right">
                              <p className="text-xs text-muted-foreground">Spend</p>
                              <p className="text-sm font-medium tabular">{formatCurrency(c.spend)}</p>
                            </div>
                            <div className="text-right">
                              <p className="text-xs text-muted-foreground">Clicks</p>
                              <p className="text-sm font-medium tabular">{formatNumber(c.clicks)}</p>
                            </div>
                            <div className="text-right hidden sm:block">
                              <p className="text-xs text-muted-foreground">Impr.</p>
                              <p className="text-sm font-medium tabular">{formatCompact(c.impressions)}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="px-4 py-12 text-center">
                    <p className="text-sm text-muted-foreground">No campaign data available</p>
                    <p className="text-xs text-muted-foreground/60 mt-1">
                      Connect Meta Ads to see campaign performance
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
