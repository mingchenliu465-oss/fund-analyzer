"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ResearchControls } from "@/components/research-controls";
import { Button } from "@/components/ui/button";
import {
  DataState,
  KeyValueList,
  MetricStrip,
  PageHeader,
  PlainConclusion,
  ResearchSection,
  SourceNote,
} from "@/components/research-ui";
import { useResearchSelection } from "@/hooks/use-research-selection";
import { CHART_BENCHMARK, CHART_DRAWDOWN, CHART_GRID } from "@/lib/chart-theme";
import { RESEARCH_PERIOD_LABELS } from "@/lib/research-preferences";
import { formatPercent, formatRatio, getFundRisk } from "@/services/fund";

function magnitude(value: number | null) {
  return formatPercent(value).replace(/^\+/, "");
}

export default function RiskDashboard() {
  const { code, period, ready, setCode, setPeriod } = useResearchSelection();
  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["fundRisk", code, period],
    queryFn: () => getFundRisk(code, period),
    enabled: ready,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const current = data?.code === code && data.period === period ? data : undefined;
  const loading = !ready || isPending || (isFetching && !current);

  return (
    <div className="page-container">
      <PageHeader
        title="风险分析"
        description="把收益波动与净值回撤分开观察，并披露恢复状态、下行风险和年化假设。"
        action={<Link className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-accent" href="/data-audit">检查数据证据 <ArrowRight size={15} /></Link>}
      />
      <ResearchControls code={code} period={period} onCodeChange={setCode} onPeriodChange={setPeriod} />

      {loading && <DataState kind="loading" title={`正在计算 ${code} 的风险指标`} description="基金风险使用累计净值，参考基准使用共同交易日。" />}
      {!loading && isError && <DataState kind="error" title="风险数据暂时不可用" description={error instanceof Error ? error.message : "请稍后重试。"} action={<Button variant="outline" onClick={() => void refetch()}>重新加载</Button>} />}
      {!loading && !isError && !current && <DataState kind="error" title="响应与当前研究对象不一致" description="已丢弃基金或区间不匹配的响应。" />}

      {current && !loading && (
        <>
          <PlainConclusion>
            {current.metrics.maxDrawdown == null
              ? "有效样本不足，波动、回撤和 Sharpe 不作误导性输出。"
              : `区间最大回撤 ${formatPercent(current.metrics.maxDrawdown)}，年化波动率 ${magnitude(current.metrics.volatility)}，下行风险 ${magnitude(current.metrics.downsideDeviation)}。${current.drawdown.recoveryStatus === "unrecovered" ? "截至区间末尚未修复最大回撤。" : current.drawdown.recoveryStatus === "recovered" ? `最大回撤已在 ${current.drawdown.recoveryDate} 修复。` : "区间内未出现负回撤。"}`}
          </PlainConclusion>
          <MetricStrip items={[
            { label: "年化波动率", value: magnitude(current.metrics.volatility), note: "日收益总体标准差", tone: "risk" },
            { label: "最大回撤", value: formatPercent(current.metrics.maxDrawdown), note: "累计净值相对峰值", tone: "risk" },
            { label: "下行风险", value: magnitude(current.metrics.downsideDeviation), note: "低于日无风险利率部分", tone: "risk" },
            { label: "Sharpe", value: formatRatio(current.metrics.sharpe), note: "无风险利率年化 2%", tone: "neutral" },
            { label: "基准年化波动率", value: magnitude(current.benchmarkMetrics.volatility), note: "沪深300 · 共同日期", tone: "risk" },
          ]} />
          <SourceNote>{current.name}（{current.code}） · {current.dataStart ?? "—"} 至 {current.dataEnd ?? "—"} · {current.sampleCount} 个有效样本。历史风险不代表未来损失上限。</SourceNote>

          <ResearchSection title="回撤曲线" description="0% 表示处于历史峰值；向下表示浮亏。基金与参考基准均按各自共同日期曲线计算。">
            {current.drawdownCurve.length >= 2 ? (
              <div className="chart-frame" aria-label="基金与参考基准回撤曲线">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={current.drawdownCurve} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={CHART_GRID} vertical={false} />
                    <XAxis dataKey="date" minTickGap={36} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                    <YAxis domain={["auto", 0]} tickFormatter={(value: number) => formatPercent(value)} tickLine={false} axisLine={false} width={58} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                    <Tooltip labelFormatter={(label) => `日期 ${label}`} formatter={(value, name) => [typeof value === "number" ? formatPercent(value) : "—", name === "fund" ? current.code : "沪深300"]} />
                    <Legend formatter={(value) => value === "fund" ? current.code : "沪深300（参考）"} />
                    <ReferenceLine y={0} stroke="var(--border)" />
                    <Line type="linear" dataKey="fund" stroke={CHART_DRAWDOWN} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type="linear" dataKey="benchmark" stroke={CHART_BENCHMARK} strokeWidth={1.5} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <DataState kind="missing" title="回撤曲线不可计算" />}
          </ResearchSection>

          <div className="overview-evidence-grid">
            <ResearchSection title="最大回撤路径" description="下跌、修复和整段水下期分别披露。">
              {current.drawdown.recoveryStatus === "unrecovered" && <DataState kind="partial" title="最大回撤尚未修复" description="恢复日期与恢复天数保持缺失，不假设未来会回到前高。" />}
              <KeyValueList items={[
                { label: "峰值日期", value: current.drawdown.peakDate ?? "—" },
                { label: "谷底日期", value: current.drawdown.troughDate ?? "—" },
                { label: "下跌持续", value: current.drawdown.drawdownDays == null ? "—" : `${current.drawdown.drawdownDays} 个自然日` },
                { label: "恢复日期", value: current.drawdown.recoveryDate ?? "尚未恢复" },
                { label: "恢复时间", value: current.drawdown.recoveryDays == null ? "—" : `${current.drawdown.recoveryDays} 个自然日` },
                { label: "水下时间", value: current.drawdown.underwaterDays == null ? "—" : `${current.drawdown.underwaterDays} 个自然日` },
              ]} />
            </ResearchSection>
            <ResearchSection title="基准风险比较" description="相同共同交易日；基准为统一参考而非合同基准。">
              <div className="research-table-wrap">
                <table className="data-table"><thead><tr><th>指标</th><th className="numeric">基金</th><th className="numeric">沪深300</th></tr></thead><tbody>
                  <tr><td>年化波动率</td><td className="numeric">{magnitude(current.metrics.volatility)}</td><td className="numeric">{magnitude(current.benchmarkMetrics.volatility)}</td></tr>
                  <tr><td>最大回撤</td><td className="numeric">{formatPercent(current.metrics.maxDrawdown)}</td><td className="numeric">{formatPercent(current.benchmarkMetrics.maxDrawdown)}</td></tr>
                  <tr><td>下行风险</td><td className="numeric">{magnitude(current.metrics.downsideDeviation)}</td><td className="numeric">{magnitude(current.benchmarkMetrics.downsideDeviation)}</td></tr>
                  <tr><td>Sharpe</td><td className="numeric">{formatRatio(current.metrics.sharpe)}</td><td className="numeric">{formatRatio(current.benchmarkMetrics.sharpe)}</td></tr>
                </tbody></table>
              </div>
            </ResearchSection>
          </div>

          <ResearchSection title="不同区间风险变化" description="点击区间切换整页；样本不足保持 —，不填 0。">
            <div className="research-table-wrap"><table className="data-table">
              <thead><tr><th>区间</th><th className="numeric">样本</th><th className="numeric">波动率</th><th className="numeric">最大回撤</th><th className="numeric">下行风险</th><th className="numeric">Sharpe</th></tr></thead>
              <tbody>{current.periodComparisons.map((item) => <tr key={item.period}><td><button className="text-link min-h-11" type="button" onClick={() => setPeriod(item.period)}>{RESEARCH_PERIOD_LABELS[item.period]}{item.period === current.period ? " · 当前" : ""}</button></td><td className="numeric">{item.sampleCount}</td><td className="numeric">{magnitude(item.volatility)}</td><td className="numeric">{formatPercent(item.maxDrawdown)}</td><td className="numeric">{magnitude(item.downsideDeviation)}</td><td className="numeric">{formatRatio(item.sharpe)}</td></tr>)}</tbody>
            </table></div>
          </ResearchSection>

          <ResearchSection title="指标口径与边界"><ul className="quality-note-list">{current.definitions.map((item) => <li key={item}>{item}</li>)}</ul><SourceNote>{current.source}；{current.benchmarkSource}。</SourceNote></ResearchSection>
        </>
      )}
    </div>
  );
}
