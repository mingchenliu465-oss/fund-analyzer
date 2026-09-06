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
import { type PeerComparison, formatPercent } from "@/services/fund";

interface PeerComparisonProps {
  data: PeerComparison[];
  targetCode: string;
}

export function PeerComparison({ data, targetCode }: PeerComparisonProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        暂无同类对比数据
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              dy={8}
              interval={0}
              angle={0}
              height={50}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <Tooltip
              contentStyle={{
                background: "var(--background)",
                border: "1px solid var(--border)",
                borderRadius: "12px",
                boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
              }}
              itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
              formatter={(value) => [formatPercent(typeof value === "number" ? value : 0), "近一年收益"]}
            />
            <Bar dataKey="oneYearReturn" radius={[4, 4, 0, 0]} maxBarSize={48}>
              {data.map((entry) => (
                <Cell
                  key={entry.code}
                  fill={entry.code === targetCode ? "#171717" : "var(--border)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 font-medium">基金</th>
              <th className="py-2 font-medium">类型</th>
              <th className="py-2 text-right font-medium">近一年收益</th>
              <th className="py-2 text-right font-medium">波动率</th>
              <th className="py-2 text-right font-medium">夏普</th>
              <th className="py-2 text-right font-medium">风险等级</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr
                key={item.code}
                className={`border-b border-border last:border-0 ${
                  item.code === targetCode ? "bg-muted/40" : ""
                }`}
              >
                <td className="py-2.5">
                  <div className="font-medium">{item.name}</div>
                  <div className="text-xs text-muted-foreground">{item.code}</div>
                </td>
                <td className="py-2.5 text-muted-foreground">{item.type}</td>
                <td
                  className={`py-2.5 text-right font-medium ${
                    item.oneYearReturn >= 0 ? "text-positive" : "text-negative"
                  }`}
                >
                  {formatPercent(item.oneYearReturn)}
                </td>
                <td className="py-2.5 text-right text-muted-foreground">
                  {formatPercent(item.volatility)}
                </td>
                <td className="py-2.5 text-right">{item.sharpe.toFixed(2)}</td>
                <td className="py-2.5 text-right text-muted-foreground">{item.riskLevel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
