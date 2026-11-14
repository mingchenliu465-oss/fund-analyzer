import { FundMetrics, formatPercent, formatRatio } from "@/services/fund";
import { KeyValueList } from "./research-ui";

export function RiskIndicatorTable({ metrics }: { metrics: FundMetrics }) {
  return (
    <KeyValueList
      items={[
        {
          label: "夏普比率",
          note: "每承担一单位波动获得的风险调整后收益",
          value: metrics.sharpe == null ? "—" : formatRatio(metrics.sharpe),
        },
        {
          label: "最大回撤",
          note: "从历史高点到随后低点的最大跌幅",
          value: formatPercent(metrics.maxDrawdown),
        },
        {
          label: "年化波动率",
          note: "历史日收益波动的年化幅度",
          value: formatPercent(metrics.volatility),
        },
        {
          label: "索提诺比率",
          note: "只把下行波动计为风险的收益指标",
          value: metrics.sortino == null ? "—" : formatRatio(metrics.sortino),
        },
      ]}
    />
  );
}
