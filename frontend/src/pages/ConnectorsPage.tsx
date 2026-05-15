import { RefreshCw, Play, Loader2, CheckCircle2, XCircle, Clock, AlertCircle, Rocket } from "lucide-react";
import { siShopify, siMeta } from "simple-icons";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { useConnectorHealth, useTriggerSync } from "@/features/connectors/hooks/useConnectors";
import { formatRelative } from "@/lib/utils/dates";
import { cn } from "@/lib/utils/cn";
import type { SourceType } from "@/constants";

// ── Brand icons ───────────────────────────────────────────────────────────────
function ConnectorIcon({ source, size = 20 }: { source: SourceType; size?: number }) {
  if (source === "shopify")
    return (
      <svg role="img" viewBox="0 0 24 24" width={size} height={size} fill={`#${siShopify.hex}`}>
        <path d={siShopify.path} />
      </svg>
    );
  if (source === "meta_ads")
    return (
      <svg role="img" viewBox="0 0 24 24" width={size} height={size} fill={`#${siMeta.hex}`}>
        <path d={siMeta.path} />
      </svg>
    );
  return <Rocket style={{ width: size, height: size }} className="text-orange-500" />;
}

// ── Connector metadata ────────────────────────────────────────────────────────
const CONNECTOR_META: Record<SourceType, {
  label: string;
  iconBg: string;
  description: string;
  metrics: string[];
  setupHint: string;
}> = {
  shopify: {
    label: "Shopify",
    iconBg: "bg-[#7AB55C]/10 border border-[#7AB55C]/20",
    description: "Orders, revenue, and refund data via Shopify Admin API",
    metrics: ["Revenue", "Orders", "Refunds", "Avg Order Value"],
    setupHint: "Add SHOPIFY_ACCESS_TOKEN and SHOPIFY_SHOP_DOMAIN to backend/.env",
  },
  meta_ads: {
    label: "Meta Ads",
    iconBg: "bg-[#0467DF]/10 border border-[#0467DF]/20",
    description: "Campaign spend, impressions, and clicks via Meta Graph API",
    metrics: ["Ad Spend", "Impressions", "Clicks", "ROAS"],
    setupHint: "Add META_ACCESS_TOKEN and META_AD_ACCOUNT_ID to backend/.env",
  },
  shiprocket: {
    label: "Shiprocket",
    iconBg: "bg-orange-50 border border-orange-100",
    description: "Shipping cost and return-to-origin (RTO) data via Shiprocket API",
    metrics: ["Shipping Cost", "RTO Rate", "Courier Performance"],
    setupHint: "Add SHIPROCKET_EMAIL and SHIPROCKET_PASSWORD to backend/.env",
  },
};

const SOURCE_ORDER: SourceType[] = ["shopify", "meta_ads", "shiprocket"];

// ── Connector card ────────────────────────────────────────────────────────────
function ConnectorCard({ source, healthy, loading }: { source: SourceType; healthy: boolean; loading: boolean }) {
  const meta = CONNECTOR_META[source];

  if (loading) {
    return (
      <Card className="border-border shadow-none">
        <CardContent className="p-5 space-y-4">
          <div className="flex items-start justify-between">
            <Skeleton className="h-11 w-11 rounded-lg" />
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-16 rounded-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border shadow-none">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          {/* Brand icon */}
          <div className={cn("flex h-11 w-11 items-center justify-center rounded-lg shrink-0", meta.iconBg)}>
            <ConnectorIcon source={source} size={22} />
          </div>

          {/* Status badge */}
          {healthy ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-50 border border-green-100 px-2.5 py-1 text-xs font-medium text-green-700 shrink-0">
              <CheckCircle2 className="h-3 w-3" />
              Connected
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-50 border border-red-100 px-2.5 py-1 text-xs font-medium text-red-600 shrink-0">
              <XCircle className="h-3 w-3" />
              Offline
            </span>
          )}
        </div>

        <div className="mt-3">
          <h3 className="text-sm font-semibold text-foreground">{meta.label}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
            {meta.description}
          </p>
        </div>
      </CardHeader>

      <CardContent className="pt-0 space-y-3">
        {/* Metric tags */}
        <div className="flex flex-wrap gap-1.5">
          {meta.metrics.map((m) => (
            <span
              key={m}
              className="rounded-full bg-secondary border border-border px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground"
            >
              {m}
            </span>
          ))}
        </div>

        {/* Setup hint */}
        {!healthy && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2.5">
            <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-[11px] text-amber-700 leading-relaxed">{meta.setupHint}</p>
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

  const healthyCount  = data ? SOURCE_ORDER.filter((s) => data.connectors[s]?.healthy).length : 0;
  const allHealthy    = healthyCount === SOURCE_ORDER.length;
  const offlineCount  = SOURCE_ORDER.length - healthyCount;

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
              {syncMutation.isPending
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <Play className="h-3.5 w-3.5" fill="currentColor" />}
              Sync All
            </Button>
          </div>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-5">

        {/* Status banner */}
        {!isLoading && data && (
          <div className={cn(
            "flex items-center gap-3 rounded-lg border px-4 py-3",
            allHealthy
              ? "border-green-100 bg-green-50"
              : "border-amber-100 bg-amber-50",
          )}>
            {allHealthy
              ? <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
              : <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />}
            <div className="flex-1">
              <p className={cn("text-sm font-medium", allHealthy ? "text-green-700" : "text-amber-700")}>
                {allHealthy
                  ? "All connectors operational"
                  : `${offlineCount} of ${SOURCE_ORDER.length} connectors offline`}
              </p>
              {data.checked_at && (
                <p className="mt-0.5 text-xs text-muted-foreground flex items-center gap-1">
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

        {/* Sync info */}
        <Card className="border-border shadow-none">
          <CardContent className="p-4 flex items-start gap-3">
            <Clock className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">Automatic Sync · every 15 minutes</p>
              <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                Manual sync triggers an immediate background job for the last 30 days of data.
                Sync is idempotent — re-running never creates duplicate rows.
              </p>
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
