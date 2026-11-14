"use client";

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

interface DrawdownChartProps {
  data: DrawdownPoint[];
}

export function DrawdownChart({ data }: DrawdownChartProps) {
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
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
        <XAxis
          dataKey="date"
          axisLine={false}
          tickLine={false}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          dy={8}
          minTickGap={16}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          tickFormatter={(v) => formatPercent(typeof v === "number" ? v : 0, 0)}
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            boxShadow: "none",
          }}
          labelStyle={{ color: "var(--muted-foreground)", fontSize: 12 }}
          itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
          formatter={(value) => [formatPercent(typeof value === "number" ? value : 0), "回撤"]}
        />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="var(--negative)"
          strokeWidth={2}
          fill="var(--muted)"
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0, fill: "var(--negative)" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
