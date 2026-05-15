import { Bot, TrendingDown, AlertTriangle, CheckCircle2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/EmptyState";
import { cn } from "@/lib/utils/cn";
import { formatRelative } from "@/lib/utils/dates";
import { formatCurrency } from "@/lib/utils/format";
import type { AgentRunLog } from "@/lib/api/types";

function findingIcon(findings: string[]) {
  if (findings.includes("spend_spike") || findings.includes("roas_decline"))
    return TrendingDown;
  if (findings.includes("low_engagement")) return AlertTriangle;
  return CheckCircle2;
}

function StatusDot({ status }: { status: string }) {
  if (status === "proposed")
    return <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />;
  if (status === "failed")
    return <span className="h-1.5 w-1.5 rounded-full bg-red-400 shrink-0" />;
  return <span className="h-1.5 w-1.5 rounded-full bg-secondary-foreground/20 shrink-0" />;
}

export function RecentAgentLogs({ logs, loading }: { logs: AgentRunLog[]; loading?: boolean }) {
  return (
    <Card className="border-border shadow-none">
      <CardHeader className="pb-3 border-b border-border">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Recent Agent Runs
          </CardTitle>
          <Button variant="ghost" size="sm" className="h-6 text-xs gap-1 text-muted-foreground" asChild>
            <Link to="/agents">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardHeader>

      <CardContent className="pt-3 pb-2">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-start gap-3">
                <Skeleton className="h-7 w-7 rounded-md shrink-0 mt-0.5" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-full" />
                  <Skeleton className="h-3 w-28" />
                </div>
              </div>
            ))}
          </div>
        ) : logs.length === 0 ? (
          <EmptyState
            icon={Bot}
            title="No agent runs yet"
            description="Agent runs will appear here after the first watchdog cycle."
          />
        ) : (
          <div className="space-y-0.5">
            {logs.map((log) => {
              const findings = log.findings ?? [];
              const Icon = findingIcon(findings);
              const hasFindings = findings.length > 0 && !findings.includes("stable");

              return (
                <div
                  key={log.id}
                  className="flex items-start gap-3 rounded-lg px-3 py-3 hover:bg-secondary/50 transition-colors"
                >
                  {/* Icon */}
                  <div className={cn(
                    "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border",
                    hasFindings
                      ? "bg-amber-50 border-amber-100"
                      : "bg-green-50 border-green-100",
                  )}>
                    <Icon className={cn(
                      "h-3.5 w-3.5",
                      hasFindings ? "text-amber-600" : "text-green-600",
                    )} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-medium text-foreground leading-snug truncate">
                        {log.proposed_action}
                      </p>
                      <span className="text-[11px] text-muted-foreground shrink-0 whitespace-nowrap">
                        {formatRelative(log.triggered_at)}
                      </span>
                    </div>

                    <div className="mt-1.5 flex items-center gap-2">
                      <StatusDot status={log.status} />
                      <span className="text-[11px] text-muted-foreground capitalize">{log.status}</span>
                      {log.estimated_saving_inr && (
                        <span className="text-[11px] font-medium text-green-600">
                          Est. {formatCurrency(log.estimated_saving_inr)} saving
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
