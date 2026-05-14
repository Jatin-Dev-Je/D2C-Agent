import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: LucideIcon;
  iconClassName?: string;
  loading?: boolean;
  trend?: "growing" | "declining" | "stable";
  deltaLabel?: string;
}

function TrendPill({
  trend,
  deltaLabel,
}: {
  trend: "growing" | "declining" | "stable";
  deltaLabel?: string;
}) {
  if (trend === "growing") {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
        <TrendingUp className="h-2.5 w-2.5" />
        {deltaLabel ?? "Up"}
      </span>
    );
  }
  if (trend === "declining") {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 text-[10px] font-medium text-red-400">
        <TrendingDown className="h-2.5 w-2.5" />
        {deltaLabel ?? "Down"}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
      <Minus className="h-2.5 w-2.5" />
      {deltaLabel ?? "Stable"}
    </span>
  );
}

export function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
  iconClassName,
  loading,
  trend,
  deltaLabel,
}: KpiCardProps) {
  if (loading) {
    return (
      <Card>
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <Skeleton className="h-3.5 w-20" />
              <Skeleton className="h-7 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-8 w-8 rounded-md" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {title}
            </p>
            <p className="mt-1.5 text-2xl font-semibold tracking-tight truncate tabular">
              {value}
            </p>
            <div className="mt-1.5 flex items-center gap-2">
              {subtitle && (
                <p className="text-xs text-muted-foreground">{subtitle}</p>
              )}
              {trend && (
                <TrendPill trend={trend} deltaLabel={deltaLabel} />
              )}
            </div>
          </div>
          <div
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
              iconClassName ?? "bg-primary/10",
            )}
          >
            <Icon className="h-4 w-4 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
