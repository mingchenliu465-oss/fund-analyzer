"use client";

import { TopHolding } from "@/services/fund";
import { SignedChange } from "@/components/signed-change";

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
            <th className="py-2 font-medium">资产</th>
            <th className="py-2 text-right font-medium">仓位</th>
            <th className="py-2 text-right font-medium">日涨跌</th>
          </tr>
        </thead>
        <tbody>
          {holdings.slice(0, 10).map((item) => {
            const assetType = item.assetType ?? (item.code
              ? (/债|转债|国开|国债/.test(item.name) ? "债券" : "股票")
              : (/基金|ETF/.test(item.name) ? "基金" : "其他"));
            return (
            <tr key={item.name} className="border-b border-border last:border-0">
              <td className="py-2.5 font-medium">{item.name}</td>
              <td className="py-2.5 text-muted-foreground">{item.code || "—"}</td>
              <td className="py-2.5 text-muted-foreground">{assetType}</td>
              <td className="py-2.5 text-right tabular-nums">{item.weight}%</td>
              {/* 日涨跌统一用 SignedChange：红涨绿跌、缺失显示「—」 */}
              <td className="py-2.5 text-right tabular-nums">
                <SignedChange value={item.changePct} />
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
