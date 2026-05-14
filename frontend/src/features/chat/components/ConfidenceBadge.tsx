import type { ConfidenceLevel } from "@/constants";
import { cn } from "@/lib/utils/cn";

interface ConfidenceBadgeProps {
  confidence: ConfidenceLevel;
  className?: string;
}

const CONFIG: Record<ConfidenceLevel, { label: string; className: string; dot: string }> = {
  high: {
    label: "High confidence",
    className: "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20",
    dot: "bg-emerald-400",
  },
  medium: {
    label: "Medium confidence",
    className: "text-amber-400 bg-amber-500/10 border border-amber-500/20",
    dot: "bg-amber-400",
  },
  low: {
    label: "Low confidence",
    className: "text-red-400 bg-red-500/10 border border-red-500/20",
    dot: "bg-red-400",
  },
};

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const { label, className: variantClass, dot } = CONFIG[confidence];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium",
        variantClass,
        className,
      )}
      title={label}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", dot)} />
      {label}
    </span>
  );
}
