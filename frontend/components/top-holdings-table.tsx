"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import { TopHolding, formatPercent } from "@/services/fund";

interface TopHoldingsTableProps {
  holdings: TopHolding[];
}

export function TopHoldingsTable({ holdings }: TopHoldingsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 font-medium">重仓方向</th>
            <th className="py-2 font-medium">代码</th>
            <th className="py-2 text-right font-medium">仓位</th>
            <th className="py-2 text-right font-medium">日涨跌</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((item) => (
            <tr key={item.name} className="border-b border-border last:border-0">
              <td className="py-2.5 font-medium">{item.name}</td>
              <td className="py-2.5 text-muted-foreground">{item.code || "—"}</td>
              <td className="py-2.5 text-right tabular-nums">{item.weight}%</td>
              <td
                className={`py-2.5 text-right font-medium tabular-nums ${
                  item.changePct >= 0 ? "text-positive" : "text-negative"
                }`}
              >
                <span className="inline-flex items-center gap-1">
                  {item.changePct >= 0 ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {formatPercent(item.changePct * 0.01)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
