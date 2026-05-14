import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";
import { getConnectorHealth } from "@/lib/api/endpoints";
import { QUERY_KEYS, SOURCE_LABELS } from "@/constants";
import type { SourceType } from "@/constants";
import { formatRelative } from "@/lib/utils/dates";

const SOURCE_ORDER: SourceType[] = ["shopify", "meta_ads", "shiprocket"];

export function ConnectorStatusGrid() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: QUERY_KEYS.connectorHealth,
    queryFn: ({ signal }) => getConnectorHealth(signal),
    staleTime: 60_000,
    retry: 1,
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Connector Health</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => refetch()}
            disabled={isRefetching}
            aria-label="Refresh connector health"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isRefetching && "animate-spin")} />
          </Button>
        </div>
        {data?.checked_at && (
          <p className="text-xs text-muted-foreground">
            Checked {formatRelative(data.checked_at)}
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading
          ? Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full rounded-md" />
            ))
          : SOURCE_ORDER.map((source) => {
              const status = data?.connectors[source];
              const healthy = status?.healthy ?? false;

              return (
                <div
                  key={source}
                  className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                >
                  <span className="text-sm text-muted-foreground">
                    {SOURCE_LABELS[source]}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {healthy ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        <span className="text-xs text-emerald-400">Healthy</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="h-4 w-4 text-red-400" />
                        <span className="text-xs text-red-400">Offline</span>
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
