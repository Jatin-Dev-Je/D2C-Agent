import { Bot, TrendingDown, AlertTriangle, CheckCircle2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/EmptyState";
import { cn } from "@/lib/utils/cn";
import { formatRelative } from "@/lib/utils/dates";
import { formatCurrency } from "@/lib/utils/format";
import type { AgentRunLog } from "@/lib/api/types";

interface RecentAgentLogsProps {
  logs: AgentRunLog[];
  loading?: boolean;
}

function findingIcon(findings: string[]) {
  if (findings.includes("spend_spike")) return TrendingDown;
  if (findings.includes("roas_decline")) return TrendingDown;
  if (findings.includes("low_engagement")) return AlertTriangle;
  return CheckCircle2;
}

export function RecentAgentLogs({ logs, loading }: RecentAgentLogsProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Recent Agent Runs</CardTitle>
          <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" asChild>
            <Link to="/agents">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full rounded-md" />
            ))}
          </div>
        ) : logs.length === 0 ? (
          <EmptyState
            icon={Bot}
            title="No agent runs yet"
            description="Agent runs will appear here after the first watchdog cycle."
          />
        ) : (
          <div className="space-y-2">
            {logs.map((log) => {
              const findings = log.findings ?? [];
              const Icon = findingIcon(findings);
              const hasFindings = findings.length > 0 && !findings.includes("stable");

              return (
                <div
                  key={log.id}
                  className="flex items-start gap-3 rounded-md border border-border p-3"
                >
                  <div
                    className={cn(
                      "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md",
                      hasFindings
                        ? "bg-amber-500/10 border border-amber-500/20"
                        : "bg-emerald-500/10 border border-emerald-500/20",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-3.5 w-3.5",
                        hasFindings ? "text-amber-400" : "text-emerald-400",
                      )}
                    />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-medium text-foreground truncate">
                        {log.proposed_action}
                      </p>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {formatRelative(log.triggered_at)}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center gap-2">
                      <Badge variant={log.status === "proposed" ? "warning" : "secondary"} className="text-xs">
                        {log.status}
                      </Badge>
                      {log.estimated_saving_inr && (
                        <span className="text-xs text-emerald-400">
                          Save {formatCurrency(log.estimated_saving_inr)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
