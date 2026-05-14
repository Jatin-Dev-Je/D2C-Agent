import { useState } from "react";
import { ChevronDown, ChevronUp, Database, Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/EmptyState";
import { formatDateTime, formatRelative, formatDuration } from "@/lib/utils/dates";
import { formatCurrency } from "@/lib/utils/format";
import type { AgentRunLog } from "@/lib/api/types";

interface AgentLogTableProps {
  logs: AgentRunLog[];
  loading?: boolean;
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "proposed" ? "warning" : status === "failed" ? "danger" : "secondary";
  return <Badge variant={variant}>{status}</Badge>;
}

function AgentLogRow({ log }: { log: AgentRunLog }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-border last:border-0">
      <button
        type="button"
        className="w-full text-left px-4 py-3 hover:bg-accent/50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusBadge status={log.status} />
              <span className="text-xs text-muted-foreground font-mono">
                {log.agent_name}
              </span>
            </div>
            <p className="text-sm text-foreground truncate">{log.proposed_action}</p>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-muted-foreground">
                {formatRelative(log.triggered_at)}
              </span>
              {log.estimated_saving_inr && (
                <span className="text-xs text-emerald-400 font-medium">
                  Est. saving: {formatCurrency(log.estimated_saving_inr)}
                </span>
              )}
              {log.execution_duration_ms !== undefined && (
                <span className="text-xs text-muted-foreground">
                  {formatDuration(log.execution_duration_ms)}
                </span>
              )}
              {log.citations.length > 0 && (
                <span className="flex items-center gap-1 text-xs text-indigo-400">
                  <Database className="h-3 w-3" />
                  {log.citations.length} sources
                </span>
              )}
            </div>
          </div>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 bg-card/50">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Observation
            </p>
            <p className="text-sm text-foreground whitespace-pre-wrap">{log.observation}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Reasoning
            </p>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
              {log.reasoning}
            </p>
          </div>
          {log.citations.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Source rows ({log.citations.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {log.citations.map((id) => (
                  <span
                    key={id}
                    className="rounded-sm bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 font-mono text-xs text-indigo-300"
                  >
                    {id}
                  </span>
                ))}
              </div>
            </div>
          )}
          <p className="text-xs text-muted-foreground/60">
            Triggered {formatDateTime(log.triggered_at)} · executed: {String(log.executed)}
          </p>
        </div>
      )}
    </div>
  );
}

export function AgentLogTable({ logs, loading }: AgentLogTableProps) {
  if (loading) {
    return (
      <div className="divide-y divide-border">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="px-4 py-3 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3.5 w-64" />
            <Skeleton className="h-3 w-40" />
          </div>
        ))}
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <EmptyState
        icon={Bot}
        title="No agent logs yet"
        description='Trigger the agent manually or wait for the next scheduled run (every 6 hours).'
      />
    );
  }

  return (
    <div className="divide-y divide-border">
      {logs.map((log) => (
        <AgentLogRow key={log.id} log={log} />
      ))}
    </div>
  );
}
