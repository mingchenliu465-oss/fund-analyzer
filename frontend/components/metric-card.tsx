"use client";

import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  icon: LucideIcon;
  delay?: number;
}

export function MetricCard({
  title,
  value,
  subtitle,
  trend,
  trendValue,
  icon: Icon,
  delay = 0,
}: MetricCardProps) {
  const trendColor =
    trend === "up"
      ? "text-positive"
      : trend === "down"
      ? "text-negative"
      : "text-muted-foreground";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.23, 1, 0.32, 1] }}
      className="group relative overflow-hidden rounded-3xl border border-border bg-background p-6 transition-shadow hover:shadow-lg"
    >
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">{title}</span>
        <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-muted transition-colors group-hover:bg-accent/10"
        >
          <Icon className="h-4 w-4 text-foreground transition-colors group-hover:text-accent" />
        </div>
      </div>
      <div className="space-y-1">
        <div className="text-3xl font-semibold tracking-tight">{value}</div>
        {(trendValue || subtitle) && (
          <div className="flex items-center gap-2 text-sm"
          >
            {trendValue && (
              <span className={`font-medium ${trendColor}`}>{trendValue}</span>
            )}
            {subtitle && (
              <span className="text-muted-foreground">{subtitle}</span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
