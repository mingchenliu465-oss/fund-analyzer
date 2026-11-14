import { type PortfolioOverview, formatCurrency, formatPercentValue } from "@/services/fund";
import { MetricStrip, SourceNote } from "./research-ui";

export function PortfolioOverview({ data }: { data: PortfolioOverview }) {
  const hasToday = data.todayReturn !== null && data.todayReturnPct !== null;

  return (
    <div>
      <MetricStrip
        items={[
          { label: "总资产", value: formatCurrency(data.totalAssets), note: "持仓市值" },
          {
            label: "今日收益",
            value: hasToday ? formatCurrency(data.todayReturn) : "—",
            note: hasToday ? formatPercentValue(data.todayReturnPct) : "数据源未提供日内收益",
            tone: hasToday && data.todayReturn != null ? (data.todayReturn >= 0 ? "up" : "down") : "neutral",
          },
          {
            label: "累计收益",
            value: formatCurrency(data.cumulativeReturn),
            note: data.cumulativeReturn == null ? "持仓估值不完整" : formatPercentValue(data.cumulativeReturnPct),
            tone: data.cumulativeReturn == null ? "neutral" : data.cumulativeReturn >= 0 ? "up" : "down",
          },
          { label: "风险评分", value: "—", note: "没有可复现的综合评分" },
        ]}
      />
      <div className="space-y-0">
        {data.allocation.length > 0 ? (
          data.allocation.map((item) => (
            <div className="allocation-row" key={item.category}>
              <span>{item.category}</span>
              <div className="allocation-track" aria-hidden="true">
                <div className="allocation-fill" style={{ width: `${Math.min(100, item.weight)}%` }} />
              </div>
              <span className="numeric font-medium">{item.weight}%</span>
            </div>
          ))
        ) : (
          <p className="py-5 text-sm text-muted-foreground">暂无足够持仓数据计算仓位比例。</p>
        )}
      </div>
      <SourceNote>仓位按现有持仓市值与基金类型汇总；未提供的数据以“—”表示。</SourceNote>
    </div>
  );
}
