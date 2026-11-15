"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART_BENCHMARK, CHART_GRID, CHART_PRIMARY } from "@/lib/chart-theme";
import { formatPercent, NormalizedCurvePoint } from "@/services/fund";

export function ReturnChart({ data, code }: { data: NormalizedCurvePoint[]; code: string }) {
  return (
    <div className="chart-frame" aria-label="基金与沪深300参考基准归一化收益曲线">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis dataKey="date" minTickGap={36} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
          <YAxis domain={["auto", "auto"]} tickFormatter={(value: number) => formatPercent(value - 1).replace("+", "")} tickLine={false} axisLine={false} width={58} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
          <Tooltip
            labelFormatter={(label) => `日期 ${label}`}
            formatter={(value, name) => [
              typeof value === "number" ? formatPercent(value - 1) : "—",
              name === "fund" ? code : "沪深300",
            ]}
          />
          <Legend formatter={(value) => value === "fund" ? code : "沪深300（参考）"} />
          <ReferenceLine y={1} stroke="var(--border)" />
          <Line type="linear" dataKey="fund" stroke={CHART_PRIMARY} strokeWidth={2} dot={false} activeDot={{ r: 3 }} isAnimationActive={false} />
          <Line type="linear" dataKey="benchmark" stroke={CHART_BENCHMARK} strokeWidth={1.6} strokeDasharray="5 4" dot={false} activeDot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
