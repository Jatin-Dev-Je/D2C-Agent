import { useState } from "react";
import { Database, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface CitationChipProps {
  citations: string[];
  className?: string;
}

export function CitationChip({ citations, className }: CitationChipProps) {
  const [expanded, setExpanded] = useState(false);

  if (citations.length === 0) return null;

  return (
    <div className={cn("mt-3 space-y-1.5", className)}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        aria-expanded={expanded}
      >
        <Database className="h-3 w-3 text-indigo-400" />
        <span className="text-indigo-400 font-medium">
          {citations.length} source{citations.length !== 1 ? "s" : ""}
        </span>
        {expanded ? (
          <ChevronUp className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
      </button>

      {expanded && (
        <div className="rounded-md border border-indigo-500/20 bg-indigo-500/5 p-3 space-y-1">
          <p className="text-xs font-medium text-indigo-400 mb-2">Source rows</p>
          <div className="flex flex-wrap gap-1.5">
            {citations.map((sourceRowId) => (
              <span
                key={sourceRowId}
                className="inline-flex items-center rounded-sm bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 font-mono text-xs text-indigo-300"
                title={sourceRowId}
              >
                {sourceRowId.length > 32 ? `${sourceRowId.slice(0, 32)}…` : sourceRowId}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
