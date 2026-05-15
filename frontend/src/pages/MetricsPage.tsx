import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell, LabelList,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import {
  useMetricSummary,
  useMetricCompare,
  useMetricRoas,
  useMetricCampaigns,
} from "@/features/metrics/hooks/useMetrics";
import { last7Days, previous7Days, last30Days } from "@/lib/utils/dates";
import {
  formatCompact, formatCurrency, formatPercentage,
  formatRoas, formatNumber, parseDecimal,
} from "@/lib/utils/format";
import { METRIC_LABELS, METRIC_NAMES } from "@/constants";
import type { MetricName } from "@/constants";

// ── Chart theme (light) ───────────────────────────────────────────────────────
const C = {
  ink:       "#1C1C1E",
  inkLight:  "#E5E7EB",
  blue:      "#3B82F6",
  blueLight: "#DBEAFE",
  green:     "#16A34A",
  amber:     "#D97706",
  muted:     "#787774",
  border:    "#E8E8E4",
};

const tooltipStyle = {
  backgroundColor: "#FFFFFF",
  border: `1px solid ${C.border}`,
  borderRadius: "8px",
  fontSize: "12px",
  color: "#37352F",
  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
};

// ── Metric picker ─────────────────────────────────────────────────────────────
function MetricPicker({ value, onChange }: { value: MetricName; onChange: (v: MetricName) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {METRIC_NAMES.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-150 ${
            value === m
              ? "bg-foreground text-background shadow-sm"
              : "bg-secondary text-muted-foreground hover:bg-accent hover:text-foreground border border-border"
          }`}
        >
          {METRIC_LABELS[m]}
        </button>
      ))}
    </div>
  );
}

// ── Stat cell ─────────────────────────────────────────────────────────────────
function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-5 py-4 border-r border-border last:border-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold mt-0.5 tabular">{value}</p>
    </div>
  );
}

// ── Compare chart (light) ─────────────────────────────────────────────────────
function CompareChart({
  currentValue, previousValue, label,
}: { currentValue: string; previousValue: string; label: string }) {
  const cur  = parseDecimal(currentValue);
  const prev = parseDecimal(previousValue);
  const data = [
    { name: "This week", value: cur },
    { name: "Last week", value: prev },
  ];

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} barSize={52} margin={{ top: 24, right: 12, left: 12, bottom: 0 }}>
        <XAxis
          dataKey="name"
          axisLine={false}
          tickLine={false}
          tick={{ fill: C.muted, fontSize: 12 }}
        />
        <YAxis hide domain={[0, Math.max(cur, prev, 1) * 1.2]} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(v: number) => [formatCompact(String(v)), label]}
          cursor={{ fill: "rgba(0,0,0,0.03)" }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          <LabelList
            dataKey="value"
            position="top"
            formatter={(v: number) => formatCompact(String(v))}
            style={{ fill: C.ink, fontSize: 11, fontWeight: 600 }}
          />
          <Cell fill={C.ink} />
          <Cell fill={C.inkLight} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── ROAS breakdown ────────────────────────────────────────────────────────────
function RoasBreakdown({ revenue, adSpend, roas }: { revenue: string; adSpend: string; roas: string }) {
  const rev      = parseDecimal(revenue);
  const spend    = parseDecimal(adSpend);
  const roasNum  = parseDecimal(roas);
  const ratio    = rev > 0 ? Math.min((spend / rev) * 100, 100) : 0;
  const healthy  = roasNum >= 3;

  const data = [
    { name: "Revenue",  value: rev,   fill: C.green },
    { name: "Ad Spend", value: spend, fill: C.amber },
  ];

  return (
    <div className="space-y-6">
      {/* 3-stat row */}
      <div className="grid grid-cols-3 divide-x divide-border rounded-lg border border-border overflow-hidden">
        <div className="px-5 py-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">ROAS</p>
          <p className="text-2xl font-bold tabular">{formatRoas(roas)}</p>
          <p className={`text-xs mt-1 font-medium ${healthy ? "text-green-600" : "text-amber-600"}`}>
            {healthy ? "Healthy" : "Below 3× target"}
          </p>
        </div>
        <div className="px-5 py-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Revenue</p>
          <p className="text-2xl font-bold tabular">{formatCompact(revenue)}</p>
        </div>
        <div className="px-5 py-4 text-center">
          <p className="text-xs text-muted-foreground mb-1">Ad Spend</p>
          <p className="text-2xl font-bold tabular">{formatCompact(adSpend)}</p>
        </div>
      </div>

      {/* Horizontal bar chart */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-3">Revenue vs Ad Spend</p>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={data} layout="vertical" barSize={22} margin={{ left: 64, right: 56, top: 0, bottom: 0 }}>
            <XAxis type="number" hide domain={[0, rev * 1.1 || 1]} />
            <YAxis
              type="category"
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: C.muted, fontSize: 12 }}
              width={60}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number) => [formatCompact(String(v))]}
              cursor={{ fill: "rgba(0,0,0,0.03)" }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              <LabelList
                dataKey="value"
                position="right"
                formatter={(v: number) => formatCompact(String(v))}
                style={{ fill: C.muted, fontSize: 11, fontWeight: 500 }}
              />
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Footer insight */}
      <p className="text-xs text-muted-foreground border-t border-border pt-3">
        {ratio.toFixed(1)}% of revenue spent on ads
        {" · "}
        {healthy ? "Strong return on ad spend." : "Consider optimising campaign budgets."}
      </p>
    </div>
  );
}

// ── Campaign chart ────────────────────────────────────────────────────────────
function CampaignChart({ campaigns }: { campaigns: { campaign_name: string; spend: string }[] }) {
  const data = campaigns.slice(0, 6).map((c) => ({
    name: c.campaign_name.length > 24 ? `${c.campaign_name.slice(0, 24)}…` : c.campaign_name,
    spend: parseDecimal(c.spend),
  }));
  if (!data.length) return null;

  return (
    <div className="px-5 pt-4 pb-2">
      <p className="text-xs font-medium text-muted-foreground mb-3">Spend by Campaign</p>
      <ResponsiveContainer width="100%" height={data.length * 38 + 8}>
        <BarChart data={data} layout="vertical" barSize={16} margin={{ left: 0, right: 68, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            axisLine={false}
            tickLine={false}
            tick={{ fill: C.muted, fontSize: 11 }}
            width={160}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v: number) => [formatCurrency(String(v)), "Spend"]}
            cursor={{ fill: "rgba(0,0,0,0.03)" }}
          />
          <Bar dataKey="spend" fill={C.ink} radius={[0, 4, 4, 0]}>
            <LabelList
              dataKey="spend"
              position="right"
              formatter={(v: number) => formatCurrency(String(v))}
              style={{ fill: C.muted, fontSize: 10 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Trend pill ────────────────────────────────────────────────────────────────
function TrendPill({ delta, percentage }: { delta: string; percentage: string }) {
  const pct = parseDecimal(percentage);
  const pos = parseDecimal(delta) >= 0;
  const zero = parseDecimal(delta) === 0;

  if (zero) return (
    <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-muted-foreground">
      <Minus className="h-3 w-3" /> 0.0%
    </span>
  );

  return pos ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">
      <TrendingUp className="h-3 w-3" /> +{Math.abs(pct).toFixed(1)}%
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600">
      <TrendingDown className="h-3 w-3" /> -{Math.abs(pct).toFixed(1)}%
    </span>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────
function NoData({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="py-12 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground/60">{hint}</p>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function MetricsPage() {
  const [metric, setMetric] = useState<MetricName>("revenue");

  const { start: c7s, end: c7e } = last7Days();
  const { start: p7s, end: p7e } = previous7Days();
  const { start: d30s, end: d30e } = last30Days();

  const summary   = useMetricSummary(metric, d30s, d30e);
  const compare   = useMetricCompare(metric, c7s, c7e, p7s, p7e);
  const roas      = useMetricRoas(d30s, d30e);
  const campaigns = useMetricCampaigns(d30s, d30e);

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Metrics"
        description="Explore grounded metrics across your D2C stack"
      />

      <div className="flex-1 overflow-auto p-6 space-y-5">
        {/* Metric selector */}
        <MetricPicker value={metric} onChange={setMetric} />

        {/* Tabs */}
        <Tabs defaultValue="summary">
          <TabsList className="bg-secondary border border-border">
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="compare">Week Comparison</TabsTrigger>
            <TabsTrigger value="roas">ROAS</TabsTrigger>
            <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          </TabsList>

          {/* ── Summary ───────────────────────────────────────────────────── */}
          <TabsContent value="summary" className="mt-4">
            <Card className="border-border shadow-none">
              <CardHeader className="border-b border-border pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {METRIC_LABELS[metric]} · Last 30 days
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-6">
                {summary.isLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-12 w-48" />
                    <Skeleton className="h-4 w-36" />
                    <Skeleton className="h-2 w-full rounded-full" />
                  </div>
                ) : summary.data ? (
                  <div className="space-y-5">
                    <div>
                      <p className="text-5xl font-bold tracking-tight tabular text-foreground">
                        {formatCompact(summary.data.total)}
                      </p>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {summary.data.row_count} data points ·{" "}
                        {new Date(summary.data.start_date).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                        {" – "}
                        {new Date(summary.data.end_date).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                      </p>
                    </div>
                    <div className="h-1 w-full rounded-full bg-secondary overflow-hidden">
                      <div className="h-full bg-foreground/20 rounded-full w-full" />
                    </div>
                  </div>
                ) : (
                  <NoData
                    message="No data for this metric"
                    hint="Sync your connectors to start seeing data"
                  />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Compare ───────────────────────────────────────────────────── */}
          <TabsContent value="compare" className="mt-4">
            <Card className="border-border shadow-none">
              <CardHeader className="border-b border-border pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {METRIC_LABELS[metric]} · This week vs last week
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-5">
                {compare.isLoading ? (
                  <div className="space-y-4">
                    <Skeleton className="h-40 w-full" />
                    <Skeleton className="h-5 w-32" />
                  </div>
                ) : compare.data ? (
                  <div className="space-y-5">
                    <CompareChart
                      currentValue={compare.data.current_value}
                      previousValue={compare.data.previous_value}
                      label={METRIC_LABELS[metric]}
                    />
                    <div className="flex items-center gap-3 border-t border-border pt-4">
                      <TrendPill
                        delta={compare.data.delta}
                        percentage={compare.data.delta_percentage}
                      />
                      <span className="text-sm text-muted-foreground capitalize">
                        {compare.data.trend}
                      </span>
                      <span className="ml-auto text-xs text-muted-foreground tabular">
                        Δ {formatCompact(compare.data.delta)}
                      </span>
                    </div>
                  </div>
                ) : (
                  <NoData message="No comparison data available" />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── ROAS ──────────────────────────────────────────────────────── */}
          <TabsContent value="roas" className="mt-4">
            <Card className="border-border shadow-none">
              <CardHeader className="border-b border-border pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  ROAS · Last 30 days
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-5">
                {roas.isLoading ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      {[0, 1, 2].map((i) => <Skeleton key={i} className="h-24 rounded-lg" />)}
                    </div>
                    <Skeleton className="h-28 w-full" />
                  </div>
                ) : roas.data ? (
                  <RoasBreakdown
                    revenue={roas.data.revenue}
                    adSpend={roas.data.ad_spend}
                    roas={roas.data.roas}
                  />
                ) : (
                  <NoData
                    message="No ROAS data available"
                    hint="Connect Shopify + Meta Ads to calculate ROAS"
                  />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── Campaigns ─────────────────────────────────────────────────── */}
          <TabsContent value="campaigns" className="mt-4">
            <Card className="border-border shadow-none overflow-hidden">
              <CardHeader className="border-b border-border pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Campaign Performance · Last 30 days
                </CardTitle>
              </CardHeader>

              {campaigns.isLoading ? (
                <div className="divide-y divide-border">
                  {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center justify-between px-5 py-3.5">
                      <Skeleton className="h-3.5 w-44" />
                      <Skeleton className="h-3.5 w-24" />
                    </div>
                  ))}
                </div>
              ) : campaigns.data && campaigns.data.campaigns.length > 0 ? (
                <>
                  {/* Summary stats row */}
                  <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
                    <StatCell label="Total Spend"   value={formatCompact(campaigns.data.total_spend)} />
                    <StatCell label="Total Clicks"  value={formatNumber(campaigns.data.total_clicks)} />
                    <StatCell label="Impressions"   value={formatCompact(campaigns.data.total_impressions)} />
                  </div>

                  {/* Spend chart */}
                  <CampaignChart campaigns={campaigns.data.campaigns} />

                  {/* Campaign rows */}
                  <div className="divide-y divide-border border-t border-border">
                    {campaigns.data.campaigns.map((c) => (
                      <div
                        key={c.campaign_id}
                        className="flex items-center justify-between px-5 py-3 hover:bg-secondary/60 transition-colors"
                      >
                        <div className="min-w-0 flex-1 pr-4">
                          <p className="text-sm font-medium truncate">{c.campaign_name}</p>
                          <p className="text-xs text-muted-foreground/50 font-mono mt-0.5 truncate">
                            {c.campaign_id}
                          </p>
                        </div>
                        <div className="flex items-center gap-6 shrink-0">
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">Spend</p>
                            <p className="text-sm font-medium tabular mt-0.5">{formatCurrency(c.spend)}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">Clicks</p>
                            <p className="text-sm font-medium tabular mt-0.5">{formatNumber(c.clicks)}</p>
                          </div>
                          <div className="text-right hidden sm:block">
                            <p className="text-xs text-muted-foreground">Impr.</p>
                            <p className="text-sm font-medium tabular mt-0.5">{formatCompact(c.impressions)}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <NoData
                  message="No campaign data available"
                  hint="Connect Meta Ads to see campaign performance"
                />
              )}
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
