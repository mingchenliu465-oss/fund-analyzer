"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryFrequencyYearRow } from "@/services/fund";

interface YearlyFrequencyChartProps {
  /** 逐年行（后端 HistoryFrequencyReport.yearly 原样）：只读 freq，不重算口径。 */
  data: HistoryFrequencyYearRow[];
}

/**
 * 逐年柱状图：每根柱子 = 该年买入、拿满 12 个月后赚钱的起点占比。
 * 只为把年份差别从表格里提出来（有的年份全赚、有的年份全亏），
 * 数字与逐年表同一来源，不另算。
 */
export function YearlyFrequencyChart({ data }: YearlyFrequencyChartProps) {
  const rows = (data ?? []).filter((row) => row.positive_12m?.freq != null);
  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        暂无逐年数据
      </div>
    );
  }
  const chartData = rows.map((row) => ({
    year: String(row.year),
    pct: Number(((row.positive_12m.freq as number) * 100).toFixed(2)),
    n: row.n,
    insufficient: row.evidence !== "足",
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
        <XAxis
          dataKey="year"
          axisLine={false}
          tickLine={false}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          dy={8}
        />
        <YAxis
          domain={[0, 100]}
          axisLine={false}
          tickLine={false}
          tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          tickFormatter={(v) => `${v}%`}
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid var(--border)",
            borderRadius: "12px",
            boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
          }}
          formatter={(value, _name, item) => {
            const payload = (item as { payload?: { n?: number; insufficient?: boolean } })
              ?.payload;
            const suffix = payload?.insufficient ? "（这一年起点太少，只能参考）" : "";
            return [
              `${typeof value === "number" ? value.toFixed(2) : value}%（共 ${payload?.n ?? "—"} 个起点）${suffix}`,
              "拿满 12 个月后赚钱的起点占比",
            ];
          }}
          labelFormatter={(label) => `${label} 年买入`}
        />
        <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
          {chartData.map((row) => (
            <Cell
              key={row.year}
              fill={row.insufficient ? "var(--muted-foreground)" : "var(--positive)"}
              fillOpacity={row.insufficient ? 0.45 : 0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
