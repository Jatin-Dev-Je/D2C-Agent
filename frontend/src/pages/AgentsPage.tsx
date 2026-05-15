import { useState } from "react";
import { Play, ChevronLeft, ChevronRight, Loader2, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/shared/PageHeader";
import { AgentLogTable } from "@/features/agents/components/AgentLogTable";
import { useAgentLogs, useTriggerAgent } from "@/features/agents/hooks/useAgents";
import { AGENT_LOGS_PAGE_SIZE } from "@/constants";

export function AgentsPage() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useAgentLogs(offset);
  const triggerMutation = useTriggerAgent();

  const total  = data?.count ?? 0;
  const hasMore = offset + AGENT_LOGS_PAGE_SIZE < total;
  const hasPrev = offset > 0;

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Agent Runs"
        description="AdWatchdog analysis history — every run is a read-only proposal"
        action={
          <Button
            size="sm"
            onClick={() => triggerMutation.mutate(undefined)}
            disabled={triggerMutation.isPending}
            className="gap-1.5 h-8 text-xs"
          >
            {triggerMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" fill="currentColor" />
            )}
            Run Agent
          </Button>
        }
      />

      <div className="flex-1 overflow-auto p-6 space-y-4">

        {/* Agent info banner */}
        <Card className="border-border shadow-none">
          <div className="flex items-start gap-4 px-5 py-4">
            <div className="h-9 w-9 rounded-lg bg-secondary border border-border flex items-center justify-center shrink-0 mt-0.5">
              <Bot className="h-4.5 w-4.5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Ad Watchdog</p>
              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed max-w-xl">
                Runs every 6 hours. Analyses 7-day spend trends, ROAS, and campaign engagement.
                Proposes ₹-saving actions — never executes anything automatically.
              </p>
            </div>
          </div>
        </Card>

        {/* Log list */}
        <Card className="border-border shadow-none overflow-hidden">

          {/* Table header */}
          <div className="px-5 py-3 border-b border-border bg-secondary/40 flex items-center justify-between">
            <p className="text-xs font-medium text-muted-foreground">
              {isLoading ? "Loading…" : `${total} run${total !== 1 ? "s" : ""}`}
            </p>
            {total > 0 && (
              <p className="text-xs text-muted-foreground">
                Showing {offset + 1}–{Math.min(offset + AGENT_LOGS_PAGE_SIZE, total)}
              </p>
            )}
          </div>

          <AgentLogTable logs={data?.logs ?? []} loading={isLoading} />

          {/* Pagination */}
          {total > AGENT_LOGS_PAGE_SIZE && (
            <div className="flex items-center justify-end gap-1 border-t border-border px-5 py-3 bg-secondary/20">
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setOffset((v) => v - AGENT_LOGS_PAGE_SIZE)}
                disabled={!hasPrev}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-7 w-7"
                onClick={() => setOffset((v) => v + AGENT_LOGS_PAGE_SIZE)}
                disabled={!hasMore}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </Card>

      </div>
    </div>
  );
}
