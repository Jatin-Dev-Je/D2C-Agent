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
  iconColor?: string;
  loading?: boolean;
  trend?: "growing" | "declining" | "stable";
  deltaLabel?: string;
}

function TrendPill({ trend, deltaLabel }: { trend: "growing" | "declining" | "stable"; deltaLabel?: string }) {
  if (trend === "growing")
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-green-50 border border-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-700">
        <TrendingUp className="h-2.5 w-2.5" />
        {deltaLabel ?? "Up"}
      </span>
    );
  if (trend === "declining")
    return (
      <span className="inline-flex items-center gap-0.5 rounded-full bg-red-50 border border-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-600">
        <TrendingDown className="h-2.5 w-2.5" />
        {deltaLabel ?? "Down"}
      </span>
    );
  return (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-secondary border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
      <Minus className="h-2.5 w-2.5" />
      {deltaLabel ?? "Stable"}
    </span>
  );
}

export function KpiCard({ title, value, subtitle, icon: Icon, iconColor, loading, trend, deltaLabel }: KpiCardProps) {
  if (loading) {
    return (
      <Card className="border-border shadow-none">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div className="space-y-2.5 flex-1">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-7 w-28" />
              <Skeleton className="h-3 w-20" />
            </div>
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border shadow-none">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-muted-foreground">{title}</p>
            <p className="mt-2 text-2xl font-bold tracking-tight tabular text-foreground truncate">
              {value}
            </p>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
              {trend && <TrendPill trend={trend} deltaLabel={deltaLabel} />}
            </div>
          </div>
          <div className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border",
            iconColor ?? "bg-secondary border-border text-muted-foreground"
          )}>
            <Icon className="h-4 w-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
