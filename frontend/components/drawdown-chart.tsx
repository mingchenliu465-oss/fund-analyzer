"use client";

import { useId } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DrawdownPoint, formatPercent } from "@/services/fund";
import {
  CHART_FALL,
  RECHARTS_TICK_PROPS,
  RECHARTS_TOOLTIP_STYLE,
} from "@/lib/chart-theme";

interface DrawdownChartProps {
  data: DrawdownPoint[];
}

export function DrawdownChart({ data }: DrawdownChartProps) {
  const gradientId = useId();

  if (!data || data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        暂无回撤数据
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CHART_FALL} stopOpacity={0.15} />
            <stop offset="95%" stopColor={CHART_FALL} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
        <XAxis
          dataKey="date"
          axisLine={false}
          tickLine={false}
          tick={RECHARTS_TICK_PROPS}
          dy={8}
          minTickGap={16}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={RECHARTS_TICK_PROPS}
          tickFormatter={(v) => formatPercent(typeof v === "number" ? v : 0, 0)}
        />
        <Tooltip
          contentStyle={RECHARTS_TOOLTIP_STYLE}
          labelStyle={{ color: "var(--muted-foreground)", fontSize: 12 }}
          itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
          formatter={(value) => [formatPercent(typeof value === "number" ? value : 0), "回撤"]}
        />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke={CHART_FALL}
          strokeWidth={2}
          fill={`url(#${gradientId})`}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0, fill: CHART_FALL }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
