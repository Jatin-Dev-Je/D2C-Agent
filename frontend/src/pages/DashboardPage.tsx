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
import { formatCompact, formatRoas, formatNumber, formatPercentage, parseDecimal } from "@/lib/utils/format";
import { last7Days, previous7Days } from "@/lib/utils/dates";
import { QUERY_KEYS, DEFAULT_QUERY_STALE_TIME } from "@/constants";

function RoasVisual({
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
  const ratio = rev > 0 ? Math.min((spend / rev) * 100, 100) : 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Performance Snapshot</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Revenue</span>
            <span className="font-semibold tabular">{formatCompact(revenue)}</span>
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full w-full" />
          </div>
        </div>

        <div className="space-y-2.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Ad Spend</span>
            <span className="font-semibold tabular">{formatCompact(adSpend)}</span>
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(ratio, 2)}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-border pt-3">
          <span className="text-xs text-muted-foreground">ROAS</span>
          <span className="text-lg font-bold text-violet-400 tabular">
            {formatRoas(roas)}
          </span>
        </div>

        <p className="text-[11px] text-muted-foreground/60 leading-relaxed">
          {parseDecimal(roas) >= 3
            ? "Healthy ROAS — every ₹1 of ad spend returns " + formatRoas(roas).replace("x", "x revenue")
            : "Consider optimising campaigns — target ROAS ≥ 3x"}
        </p>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { data, isLoading, refetch, isRefetching } = useDashboard();
  const metrics = data?.metrics;

  const { start: cur7Start, end: cur7End } = last7Days();
  const { start: prev7Start, end: prev7End } = previous7Days();

  const compares = useQueries({
    queries: [
      {
        queryKey: QUERY_KEYS.metricCompare("revenue", cur7Start, cur7End, prev7Start, prev7End),
        queryFn: ({ signal }: { signal?: AbortSignal }) =>
          getMetricCompare("revenue", cur7Start, cur7End, prev7Start, prev7End, signal),
        staleTime: DEFAULT_QUERY_STALE_TIME,
        retry: 1,
      },
      {
        queryKey: QUERY_KEYS.metricCompare("ad_spend", cur7Start, cur7End, prev7Start, prev7End),
        queryFn: ({ signal }: { signal?: AbortSignal }) =>
          getMetricCompare("ad_spend", cur7Start, cur7End, prev7Start, prev7End, signal),
        staleTime: DEFAULT_QUERY_STALE_TIME,
        retry: 1,
      },
      {
        queryKey: QUERY_KEYS.metricCompare("orders", cur7Start, cur7End, prev7Start, prev7End),
        queryFn: ({ signal }: { signal?: AbortSignal }) =>
          getMetricCompare("orders", cur7Start, cur7End, prev7Start, prev7End, signal),
        staleTime: DEFAULT_QUERY_STALE_TIME,
        retry: 1,
      },
    ],
  });

  const [revCompare, spendCompare, ordersCompare] = compares;

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

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* KPI Grid */}
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard
            title="Revenue"
            value={metrics ? formatCompact(metrics.revenue_inr) : "—"}
            subtitle="30-day total"
            icon={TrendingUp}
            iconClassName="bg-emerald-500/10 border border-emerald-500/20"
            loading={isLoading}
            trend={revCompare.data?.trend}
            deltaLabel={revCompare.data ? formatPercentage(revCompare.data.delta_percentage) : undefined}
          />
          <KpiCard
            title="Orders"
            value={metrics ? formatNumber(metrics.orders) : "—"}
            subtitle="30-day total"
            icon={ShoppingBag}
            iconClassName="bg-blue-500/10 border border-blue-500/20"
            loading={isLoading}
            trend={ordersCompare.data?.trend}
            deltaLabel={ordersCompare.data ? formatPercentage(ordersCompare.data.delta_percentage) : undefined}
          />
          <KpiCard
            title="Ad Spend"
            value={metrics ? formatCompact(metrics.ad_spend_inr) : "—"}
            subtitle="30-day total"
            icon={DollarSign}
            iconClassName="bg-amber-500/10 border border-amber-500/20"
            loading={isLoading}
            trend={spendCompare.data?.trend === "growing" ? "declining" : spendCompare.data?.trend === "declining" ? "growing" : spendCompare.data?.trend}
            deltaLabel={spendCompare.data ? formatPercentage(spendCompare.data.delta_percentage) : undefined}
          />
          <KpiCard
            title="ROAS"
            value={metrics ? formatRoas(metrics.roas) : "—"}
            subtitle="Revenue / Ad Spend"
            icon={BarChart3}
            iconClassName="bg-violet-500/10 border border-violet-500/20"
            loading={isLoading}
          />
        </div>

        {/* Middle row */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <RecentAgentLogs
              logs={data?.recent_agent_logs ?? []}
              loading={isLoading}
            />
          </div>
          <div className="space-y-4">
            {metrics && !isLoading && (
              <RoasVisual
                revenue={metrics.revenue_inr}
                adSpend={metrics.ad_spend_inr}
                roas={metrics.roas}
              />
            )}
            <ConnectorStatusGrid />
          </div>
        </div>
      </div>
    </div>
  );
}
