"use client";

import { Briefcase, PiggyBank, TrendingUp, AlertTriangle } from "lucide-react";
import { type PortfolioOverview, formatCurrency, formatPercent } from "@/services/fund";
import { MetricCard } from "./metric-card";
import { RiskScore } from "./risk-score";

interface PortfolioOverviewProps {
  data: PortfolioOverview;
}

export function PortfolioOverview({ data }: PortfolioOverviewProps) {
  const isTodayUp = data.todayReturnPct >= 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard
          title="总资产"
          value={formatCurrency(data.totalAssets)}
          subtitle="示例组合"
          icon={Briefcase}
          delay={0.1}
        />
        <MetricCard
          title="今日收益"
          value={formatCurrency(data.todayReturn)}
          trend={isTodayUp ? "up" : "down"}
          trendValue={formatPercent(data.todayReturnPct)}
          subtitle="今日变动"
          icon={TrendingUp}
          delay={0.15}
        />
        <MetricCard
          title="累计收益"
          value={formatCurrency(data.cumulativeReturn)}
          trend="up"
          trendValue={formatPercent(data.cumulativeReturnPct)}
          subtitle="成立以来"
          icon={PiggyBank}
          delay={0.2}
        />
        <MetricCard
          title="风险评分"
          value={data.riskLevel}
          subtitle={`评分 ${data.riskScore}`}
          icon={AlertTriangle}
          delay={0.25}
        />
      </div>

      <div className="rounded-2xl border border-border bg-background p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium">仓位比例</span>
          <RiskScore score={data.riskScore} label={data.riskLevel} size={72} stroke={6} />
        </div>
        <div className="space-y-2">
          {data.allocation.map((item) => (
            <div key={item.category} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{item.category}</span>
                <span className="font-medium tabular-nums">{item.weight}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${item.weight}%`, backgroundColor: item.color }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
