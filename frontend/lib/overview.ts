import type { FundOverview } from "../services/fund";
import type { ResearchPeriod } from "./research-preferences";

export function isCurrentOverview(
  data: FundOverview | undefined,
  code: string,
  period: ResearchPeriod
): data is FundOverview {
  return data?.code === code && data.period === period;
}

export function excessReturn(data: FundOverview): number | null {
  const fund = data.metrics.periodReturn;
  const benchmark = data.benchmark.periodReturn;
  return fund == null || benchmark == null ? null : fund - benchmark;
}

export function overviewConclusion(data: FundOverview): string {
  const fundReturn = data.metrics.periodReturn;
  if (fundReturn == null) {
    return "所选区间没有足够的真实累计净值，暂不生成收益或风险结论。";
  }
  const returnText = `基金区间收益为 ${(fundReturn * 100).toFixed(2)}%`;
  const drawdown = data.metrics.maxDrawdown;
  const riskText = drawdown == null
    ? "风险指标因样本不足而不可计算"
    : `最大回撤为 ${(drawdown * 100).toFixed(2)}%`;
  const benchmarkReturn = data.benchmark.periodReturn;
  if (benchmarkReturn == null) {
    return `${returnText}，${riskText}。参考基准当前不可用，未计算超额收益。`;
  }
  const excess = fundReturn - benchmarkReturn;
  return `${returnText}，相对沪深300参考基准的超额收益为 ${(excess * 100).toFixed(2)}%，${riskText}。`;
}
