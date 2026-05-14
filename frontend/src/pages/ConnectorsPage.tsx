import { RefreshCw, Play, Loader2, CheckCircle2, XCircle, ShoppingBag, BarChart3, Truck, Clock, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { useConnectorHealth, useTriggerSync } from "@/features/connectors/hooks/useConnectors";
import { formatRelative } from "@/lib/utils/dates";
import { cn } from "@/lib/utils/cn";
import type { SourceType } from "@/constants";

// ── Connector metadata ────────────────────────────────────────────────────────

const CONNECTOR_META: Record<
  SourceType,
  {
    label: string;
    icon: React.ElementType;
    iconBg: string;
    iconColor: string;
    description: string;
    metrics: string[];
    setupHint: string;
  }
> = {
  shopify: {
    label: "Shopify",
    icon: ShoppingBag,
    iconBg: "bg-emerald-500/10 border border-emerald-500/20",
    iconColor: "text-emerald-400",
    description: "Orders, revenue, and refund data via Shopify Admin API",
    metrics: ["Revenue", "Orders", "Refunds", "Avg Order Value"],
    setupHint: "Add SHOPIFY_ACCESS_TOKEN + SHOPIFY_SHOP_DOMAIN to backend/.env",
  },
  meta_ads: {
    label: "Meta Ads",
    icon: BarChart3,
    iconBg: "bg-blue-500/10 border border-blue-500/20",
    iconColor: "text-blue-400",
    description: "Campaign spend, impressions, and clicks via Meta Graph API",
    metrics: ["Ad Spend", "Impressions", "Clicks", "ROAS"],
    setupHint: "Add META_ACCESS_TOKEN + META_AD_ACCOUNT_ID to backend/.env",
  },
  shiprocket: {
    label: "Shiprocket",
    icon: Truck,
    iconBg: "bg-amber-500/10 border border-amber-500/20",
    iconColor: "text-amber-400",
    description: "Shipping cost and return-to-origin (RTO) data via Shiprocket API",
    metrics: ["Shipping Cost", "RTO Rate", "Courier Performance"],
    setupHint: "Add SHIPROCKET_EMAIL + SHIPROCKET_PASSWORD to backend/.env",
  },
};

const SOURCE_ORDER: SourceType[] = ["shopify", "meta_ads", "shiprocket"];

// ── Connector card ────────────────────────────────────────────────────────────

function ConnectorCard({
  source,
  healthy,
  loading,
}: {
  source: SourceType;
  healthy: boolean;
  loading: boolean;
}) {
  const meta = CONNECTOR_META[source];
  const Icon = meta.icon;

  if (loading) {
    return (
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-start justify-between">
            <Skeleton className="h-10 w-10 rounded-lg" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
          <div className="flex gap-1.5">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-16 rounded-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn(
      "transition-all duration-200",
      healthy
        ? "border-border"
        : "border-border/50 opacity-80"
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg shrink-0", meta.iconBg)}>
            <Icon className={cn("h-5 w-5", meta.iconColor)} />
          </div>
          <Badge variant={healthy ? "success" : "danger"} className="shrink-0">
            {healthy ? (
              <span className="flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" />
                Connected
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <XCircle className="h-3 w-3" />
                Offline
              </span>
            )}
          </Badge>
        </div>

        <div className="mt-3">
          <h3 className="text-sm font-semibold">{meta.label}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
            {meta.description}
          </p>
        </div>
      </CardHeader>

      <CardContent className="pt-0 space-y-4">
        {/* Metrics tags */}
        <div className="flex flex-wrap gap-1.5">
          {meta.metrics.map((m) => (
            <span
              key={m}
              className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
            >
              {m}
            </span>
          ))}
        </div>

        {/* Setup hint when offline */}
        {!healthy && (
          <div className="flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2.5">
            <AlertCircle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
            <p className="text-[11px] text-amber-400 leading-relaxed">
              {meta.setupHint}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function ConnectorsPage() {
  const { data, isLoading, refetch, isRefetching } = useConnectorHealth();
  const syncMutation = useTriggerSync();

  const healthyCount = data
    ? SOURCE_ORDER.filter((s) => data.connectors[s]?.healthy).length
    : 0;
  const allHealthy = healthyCount === SOURCE_ORDER.length;

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Connectors"
        description="Data source health and manual sync controls"
        action={
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isRefetching}
              className="gap-1.5 h-8 text-xs"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", isRefetching && "animate-spin")} />
              Check Health
            </Button>
            <Button
              size="sm"
              onClick={() => syncMutation.mutate(undefined)}
              disabled={syncMutation.isPending}
              className="gap-1.5 h-8 text-xs"
            >
              {syncMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              Sync All
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-5">
        {/* Status banner */}
        {!isLoading && data && (
          <div className={cn(
            "flex items-center gap-2.5 rounded-lg border px-4 py-3",
            allHealthy
              ? "border-emerald-500/20 bg-emerald-500/5"
              : "border-amber-500/20 bg-amber-500/5"
          )}>
            {allHealthy ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 text-amber-400 shrink-0" />
            )}
            <div className="flex-1">
              <p className={cn("text-sm font-medium", allHealthy ? "text-emerald-400" : "text-amber-400")}>
                {allHealthy
                  ? "All connectors operational"
                  : `${SOURCE_ORDER.length - healthyCount} of ${SOURCE_ORDER.length} connectors offline`}
              </p>
              {data.checked_at && (
                <p className="text-xs text-muted-foreground/70 mt-0.5 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Checked {formatRelative(data.checked_at)}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Connector cards */}
        <div className="grid gap-4 sm:grid-cols-3">
          {SOURCE_ORDER.map((source) => (
            <ConnectorCard
              key={source}
              source={source}
              healthy={data?.connectors[source]?.healthy ?? false}
              loading={isLoading}
            />
          ))}
        </div>

        {/* Sync policy info */}
        <Card>
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
              <p className="text-sm font-medium">Automatic Sync</p>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              All connectors sync automatically every 15 minutes in the background.
              Manual sync triggers an immediate background job for the last 30 days of data.
              Sync is fully idempotent — re-running never creates duplicate rows.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
