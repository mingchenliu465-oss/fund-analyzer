import type { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  icon: LucideIcon;
  delay?: number;
}

/** Legacy API kept for feature components; presentation is now a borderless metric row. */
export function MetricCard({
  title,
  value,
  subtitle,
  trend,
  trendValue,
  icon: Icon,
}: MetricCardProps) {
  const trendColor =
    trend === "up" ? "text-positive" : trend === "down" ? "text-negative" : "text-muted-foreground";

  return (
    <div className="border-b border-border py-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        <span>{title}</span>
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {(trendValue || subtitle) && (
        <div className="mt-1 flex flex-wrap gap-2 text-xs">
          {trendValue && <span className={`font-medium ${trendColor}`}>{trendValue}</span>}
          {subtitle && <span className="text-muted-foreground">{subtitle}</span>}
        </div>
      )}
    </div>
  );
}
