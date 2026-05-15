import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, RefreshCw, Rocket } from "lucide-react";
import { siShopify, siMeta } from "simple-icons";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";
import { getConnectorHealth } from "@/lib/api/endpoints";
import { QUERY_KEYS, SOURCE_LABELS } from "@/constants";
import type { SourceType } from "@/constants";
import { formatRelative } from "@/lib/utils/dates";

const SOURCE_ORDER: SourceType[] = ["shopify", "meta_ads", "shiprocket"];

const SOURCE_BG: Record<SourceType, string> = {
  shopify:    "bg-[#96BF48]/10 border-[#96BF48]/25",
  meta_ads:   "bg-[#0081FB]/10 border-[#0081FB]/25",
  shiprocket: "bg-orange-50 border-orange-100",
};

function SourceIcon({ source }: { source: SourceType }) {
  if (source === "shopify") {
    return (
      <svg role="img" viewBox="0 0 24 24" width={14} height={14} fill={`#${siShopify.hex}`}>
        <path d={siShopify.path} />
      </svg>
    );
  }
  if (source === "meta_ads") {
    return (
      <svg role="img" viewBox="0 0 24 24" width={14} height={14} fill={`#${siMeta.hex}`}>
        <path d={siMeta.path} />
      </svg>
    );
  }
  return <Rocket className="h-3.5 w-3.5 text-orange-500" />;
}

export function ConnectorStatusGrid() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: QUERY_KEYS.connectorHealth,
    queryFn: ({ signal }) => getConnectorHealth(signal),
    staleTime: 60_000,
    retry: 1,
  });

  return (
    <Card className="border-border shadow-none">
      <CardHeader className="pb-3 border-b border-border">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Connector Health
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-muted-foreground"
            onClick={() => refetch()}
            disabled={isRefetching}
            aria-label="Refresh connector health"
          >
            <RefreshCw className={cn("h-3 w-3", isRefetching && "animate-spin")} />
          </Button>
        </div>
        {data?.checked_at && (
          <p className="text-[11px] text-muted-foreground/60 mt-0.5">
            Checked {formatRelative(data.checked_at)}
          </p>
        )}
      </CardHeader>

      <CardContent className="pt-3 pb-4 space-y-1">
        {isLoading
          ? Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full rounded-md" />
            ))
          : SOURCE_ORDER.map((source) => {
              const healthy = data?.connectors[source]?.healthy ?? false;

              return (
                <div
                  key={source}
                  className="flex items-center justify-between rounded-md px-3 py-2.5 hover:bg-secondary/60 transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <div className={cn(
                      "flex h-6 w-6 items-center justify-center rounded border shrink-0",
                      SOURCE_BG[source],
                    )}>
                      <SourceIcon source={source} />
                    </div>
                    <span className="text-sm font-medium text-foreground">
                      {SOURCE_LABELS[source]}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {healthy ? (
                      <>
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                        <span className="text-xs font-medium text-green-600">Connected</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="h-3.5 w-3.5 text-red-400" />
                        <span className="text-xs font-medium text-red-500">Offline</span>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
      </CardContent>
    </Card>
  );
}
