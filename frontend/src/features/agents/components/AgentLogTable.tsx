import { useState } from "react";
import { ChevronDown, Database, Bot, TrendingDown } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/EmptyState";
import { formatDateTime, formatRelative, formatDuration } from "@/lib/utils/dates";
import { formatCurrency, parseDecimal } from "@/lib/utils/format";
import type { AgentRunLog } from "@/lib/api/types";

// ── Status indicator ──────────────────────────────────────────────────────────
function StatusDot({ status }: { status: string }) {
  if (status === "proposed")
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-600">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
        Proposed
      </span>
    );
  if (status === "failed")
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-red-500">
        <span className="h-1.5 w-1.5 rounded-full bg-red-400 shrink-0" />
        Failed
      </span>
    );
  return (
    <span className="text-[11px] text-muted-foreground capitalize">{status}</span>
  );
}

// ── Single log row ────────────────────────────────────────────────────────────
function AgentLogRow({ log }: { log: AgentRunLog }) {
  const [expanded, setExpanded] = useState(false);
  const hasSaving =
    log.estimated_saving_inr && parseDecimal(log.estimated_saving_inr) > 0;

  return (
    <div className="border-b border-border last:border-0">
      {/* Summary row */}
      <button
        type="button"
        className="w-full text-left px-5 py-4 hover:bg-secondary/50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Agent name + status */}
            <div className="flex items-center gap-2.5 mb-1.5">
              <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
                {log.agent_name.replace(/_/g, " ")}
              </span>
              <StatusDot status={log.status} />
            </div>

            {/* Proposed action — headline */}
            <p className="text-sm font-medium text-foreground leading-snug">
              {log.proposed_action}
            </p>

            {/* Metadata chips */}
            <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-2">
              <span className="text-xs text-muted-foreground">
                {formatRelative(log.triggered_at)}
              </span>

              {hasSaving && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600">
                  <TrendingDown className="h-3 w-3" />
                  Est. {formatCurrency(log.estimated_saving_inr)} saving
                </span>
              )}

              {log.citations.length > 0 && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Database className="h-3 w-3" />
                  {log.citations.length} source{log.citations.length !== 1 ? "s" : ""}
                </span>
              )}

              {log.execution_duration_ms !== undefined && (
                <span className="text-xs text-muted-foreground">
                  {formatDuration(log.execution_duration_ms)}
                </span>
              )}
            </div>
          </div>

          <ChevronDown
            className={`h-4 w-4 text-muted-foreground shrink-0 mt-1 transition-transform duration-200 ${
              expanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="px-5 pb-5 space-y-4 bg-secondary/30 border-t border-border">
          {/* Observation */}
          <div className="pt-4 space-y-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Observation
            </p>
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
              {log.observation}
            </p>
          </div>

          {/* Reasoning */}
          <div className="space-y-1.5">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Reasoning
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
              {log.reasoning}
            </p>
          </div>

          {/* Source citations */}
          {log.citations.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Source rows ({log.citations.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {log.citations.map((id) => (
                  <span
                    key={id}
                    className="rounded border border-border bg-card font-mono text-[11px] text-muted-foreground px-2 py-0.5"
                  >
                    {id}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Footer */}
          <p className="text-[11px] text-muted-foreground/50 pt-1 border-t border-border">
            {formatDateTime(log.triggered_at)} · proposal only, not executed
          </p>
        </div>
      )}
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
export function AgentLogTable({ logs, loading }: { logs: AgentRunLog[]; loading?: boolean }) {
  if (loading) {
    return (
      <div className="divide-y divide-border">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="px-5 py-4 space-y-2.5">
            <div className="flex items-center gap-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-14" />
            </div>
            <Skeleton className="h-4 w-72" />
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
        title="No agent runs yet"
        description="Trigger the agent manually or wait for the next scheduled run every 6 hours."
      />
    );
  }

  return (
    <div>
      {logs.map((log) => (
        <AgentLogRow key={log.id} log={log} />
      ))}
    </div>
  );
}
