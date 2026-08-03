"use client";

import { FundMetrics, formatPercent, formatRatio } from "@/services/fund";

interface RiskIndicatorTableProps {
  metrics: FundMetrics;
}

export function RiskIndicatorTable({ metrics }: RiskIndicatorTableProps) {
  const items = [
    { label: "夏普比率", value: formatRatio(metrics.sharpe), desc: "风险调整后收益" },
    { label: "索提诺比率", value: formatRatio(metrics.sortino), desc: "下行风险调整收益" },
    { label: "Alpha", value: formatPercent(metrics.alpha, 2), desc: "超额收益" },
    { label: "Beta", value: formatRatio(metrics.beta), desc: "相对市场弹性" },
    { label: "信息比率", value: formatRatio(metrics.informationRatio), desc: "主动管理能力" },
    { label: "最大回撤", value: formatPercent(metrics.maxDrawdown), desc: "历史极端亏损" },
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
