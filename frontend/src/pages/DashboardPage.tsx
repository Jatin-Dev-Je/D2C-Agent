import { useQueries } from "@tanstack/react-query";
import { ShoppingBag, TrendingUp, DollarSign, BarChart3, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { KpiCard } from "@/features/dashboard/components/KpiCard";
import { ConnectorStatusGrid } from "@/features/dashboard/components/ConnectorStatusGrid";
import { RecentAgentLogs } from "@/features/dashboard/components/RecentAgentLogs";
import { useDashboard } from "@/features/dashboard/hooks/useDashboard";
import { getMetricCompare } from "@/lib/api/endpoints";
import {
  formatCompact, formatRoas, formatNumber,
  formatPercentage, parseDecimal,
} from "@/lib/utils/format";
import { last7Days, previous7Days } from "@/lib/utils/dates";
import { QUERY_KEYS, DEFAULT_QUERY_STALE_TIME } from "@/constants";

// ── ROAS snapshot card ────────────────────────────────────────────────────────
function RoasSnapshot({ revenue, adSpend, roas }: { revenue: string; adSpend: string; roas: string }) {
  const roasNum = parseDecimal(roas);
  const healthy = roasNum >= 3;

  return (
    <Card className="border-border shadow-none">
      <CardHeader className="pb-3 border-b border-border">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Performance · 30 days
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 space-y-4">
        {/* Stats */}
        <div className="grid grid-cols-3 divide-x divide-border text-center">
          <div className="pr-3">
            <p className="text-[11px] text-muted-foreground">ROAS</p>
            <p className="text-xl font-bold tabular mt-1">{formatRoas(roas)}</p>
          </div>
          <div className="px-3">
            <p className="text-[11px] text-muted-foreground">Revenue</p>
            <p className="text-sm font-semibold tabular mt-1">{formatCompact(revenue)}</p>
          </div>
          <div className="pl-3">
            <p className="text-[11px] text-muted-foreground">Ad Spend</p>
            <p className="text-sm font-semibold tabular mt-1">{formatCompact(adSpend)}</p>
          </div>
        </div>

        {/* Health pill */}
        <div className={`rounded-lg px-3 py-2.5 text-xs font-medium leading-relaxed ${
          healthy
            ? "bg-green-50 text-green-700 border border-green-100"
            : "bg-amber-50 text-amber-700 border border-amber-100"
        }`}>
          {healthy
            ? `Every ₹1 of ad spend returned ${formatRoas(roas)} in revenue`
            : "ROAS below 3× — consider pausing low-performing campaigns"}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function DashboardPage() {
  const { data, isLoading, refetch, isRefetching } = useDashboard();
  const metrics = data?.metrics;

  const { start: c7s, end: c7e } = last7Days();
  const { start: p7s, end: p7e } = previous7Days();

  const compares = useQueries({
    queries: [
      {
        queryKey: QUERY_KEYS.metricCompare("revenue", c7s, c7e, p7s, p7e),
        queryFn: ({ signal }: { signal?: AbortSignal }) =>
          getMetricCompare("revenue", c7s, c7e, p7s, p7e, signal),
        staleTime: DEFAULT_QUERY_STALE_TIME,
        retry: 1,
      },
      {
        queryKey: QUERY_KEYS.metricCompare("ad_spend", c7s, c7e, p7s, p7e),
        queryFn: ({ signal }: { signal?: AbortSignal }) =>
          getMetricCompare("ad_spend", c7s, c7e, p7s, p7e, signal),
        staleTime: DEFAULT_QUERY_STALE_TIME,
        retry: 1,
      },
      {
        queryKey: QUERY_KEYS.metricCompare("orders", c7s, c7e, p7s, p7e),
        queryFn: ({ signal }: { signal?: AbortSignal }) =>
          getMetricCompare("orders", c7s, c7e, p7s, p7e, signal),
        staleTime: DEFAULT_QUERY_STALE_TIME,
        retry: 1,
      },
    ],
  });

  const [revCmp, spendCmp, ordersCmp] = compares;

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Dashboard"
        description="Last 30 days · Grounded in synced data"
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
            className="gap-1.5 h-8 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-5">

        {/* KPI row */}
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard
            title="Revenue"
            value={metrics ? formatCompact(metrics.revenue_inr) : "—"}
            subtitle="30-day total"
            icon={TrendingUp}
            iconColor="bg-green-50 border-green-100 text-green-600"
            loading={isLoading}
            trend={revCmp.data?.trend}
            deltaLabel={revCmp.data ? formatPercentage(revCmp.data.delta_percentage) : undefined}
          />
          <KpiCard
            title="Orders"
            value={metrics ? formatNumber(metrics.orders) : "—"}
            subtitle="30-day total"
            icon={ShoppingBag}
            iconColor="bg-blue-50 border-blue-100 text-blue-600"
            loading={isLoading}
            trend={ordersCmp.data?.trend}
            deltaLabel={ordersCmp.data ? formatPercentage(ordersCmp.data.delta_percentage) : undefined}
          />
          <KpiCard
            title="Ad Spend"
            value={metrics ? formatCompact(metrics.ad_spend_inr) : "—"}
            subtitle="30-day total"
            icon={DollarSign}
            iconColor="bg-amber-50 border-amber-100 text-amber-600"
            loading={isLoading}
            trend={
              spendCmp.data?.trend === "growing"
                ? "declining"
                : spendCmp.data?.trend === "declining"
                ? "growing"
                : spendCmp.data?.trend
            }
            deltaLabel={spendCmp.data ? formatPercentage(spendCmp.data.delta_percentage) : undefined}
          />
          <KpiCard
            title="ROAS"
            value={metrics ? formatRoas(metrics.roas) : "—"}
            subtitle="Revenue / Ad Spend"
            icon={BarChart3}
            iconColor="bg-violet-50 border-violet-100 text-violet-600"
            loading={isLoading}
          />
        </div>

        {/* Content row */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* Agent activity — takes 2/3 width */}
          <div className="lg:col-span-2">
            <RecentAgentLogs
              logs={data?.recent_agent_logs ?? []}
              loading={isLoading}
            />
          </div>

          {/* Right column — ROAS snapshot + connectors */}
          <div className="space-y-5">
            {metrics && !isLoading ? (
              <RoasSnapshot
                revenue={metrics.revenue_inr}
                adSpend={metrics.ad_spend_inr}
                roas={metrics.roas}
              />
            ) : isLoading ? (
              <Card className="border-border shadow-none">
                <CardContent className="p-5 space-y-3">
                  <div className="h-3 w-24 bg-secondary rounded animate-pulse" />
                  <div className="h-12 bg-secondary rounded animate-pulse" />
                  <div className="h-8 bg-secondary rounded animate-pulse" />
                </CardContent>
              </Card>
            ) : null}
            <ConnectorStatusGrid />
          </div>
        </div>

      </div>
    </div>
  );
}
