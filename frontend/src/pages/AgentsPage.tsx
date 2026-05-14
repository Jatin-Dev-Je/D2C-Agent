import { useState } from "react";
import { Play, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
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

  const totalLogs = data?.count ?? 0;
  const hasMore = offset + AGENT_LOGS_PAGE_SIZE < totalLogs;
  const hasPrev = offset > 0;

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Agent Runs"
        description="AdWatchdog analysis history — all runs are read-only proposals"
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
              <Play className="h-3.5 w-3.5" />
            )}
            Run Agent Now
          </Button>
        }
      />

      <div className="flex-1 overflow-auto p-6">
        <Card>
          <AgentLogTable logs={data?.logs ?? []} loading={isLoading} />

          {/* Pagination */}
          {totalLogs > AGENT_LOGS_PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-border px-4 py-3">
              <span className="text-xs text-muted-foreground">
                {offset + 1}–{Math.min(offset + AGENT_LOGS_PAGE_SIZE, totalLogs)} of {totalLogs}
              </span>
              <div className="flex gap-1">
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
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
