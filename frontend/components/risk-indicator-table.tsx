"use client";

import { FundMetrics, formatPercent, formatRatio } from "@/services/fund";

interface RiskIndicatorTableProps {
  metrics: FundMetrics;
}

function safeFormatRatio(v: number | null | undefined): string {
  return v != null ? formatRatio(v) : "—";
}

function safeFormatPercent(v: number | null | undefined, digits = 0): string {
  return v != null ? formatPercent(v, digits) : "—";
}

export function RiskIndicatorTable({ metrics }: RiskIndicatorTableProps) {
  const items = [
    { label: "夏普比率", value: safeFormatRatio(metrics.sharpe), desc: "风险调整后收益" },
    { label: "最大回撤", value: safeFormatPercent(metrics.maxDrawdown), desc: "历史极端亏损" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-xl border border-border p-3 transition-colors hover:bg-muted/30"
        >
          <div className="text-xs text-muted-foreground">{item.label}</div>
          <div className="mt-1 text-lg font-semibold tabular-nums">{item.value}</div>
          <div className="text-xs text-muted-foreground">{item.desc}</div>
        </div>
      ))}
    </div>
  );
}
