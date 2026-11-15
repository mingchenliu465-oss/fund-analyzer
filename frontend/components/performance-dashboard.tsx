"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ResearchControls } from "@/components/research-controls";
import { ReturnChart } from "@/components/return-chart";
import { Button } from "@/components/ui/button";
import {
  DataState,
  KeyValueList,
  MetricStrip,
  PageHeader,
  PlainConclusion,
  ResearchSection,
  SourceNote,
  toneFor,
} from "@/components/research-ui";
import { useResearchSelection } from "@/hooks/use-research-selection";
import { RESEARCH_PERIOD_LABELS } from "@/lib/research-preferences";
import { formatPercent, getFundPerformance } from "@/services/fund";

function returnTone(value: number | null) {
  return value == null ? "text-missing" : value >= 0 ? "text-positive" : "text-negative";
}

export default function PerformanceDashboard() {
  const { code, period, ready, setCode, setPeriod } = useResearchSelection();
  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["fundPerformance", code, period],
    queryFn: () => getFundPerformance(code, period),
    enabled: ready,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const current = data?.code === code && data.period === period ? data : undefined;
  const loading = !ready || isPending || (isFetching && !current);

  return (
    <div className="page-container">
      <PageHeader
        title="表现分析"
        description="区间收益、自然周期收益与参考基准对比。所有基金收益只使用真实累计净值。"
        action={<Link className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-accent" href="/">研究概览 <ArrowRight size={15} /></Link>}
      />
      <ResearchControls code={code} period={period} onCodeChange={setCode} onPeriodChange={setPeriod} />

      {loading && <DataState kind="loading" title={`正在计算 ${code} 的表现指标`} description="区间、自然年月和多周期比较使用同一累计净值口径。" />}
      {!loading && isError && <DataState kind="error" title="表现数据暂时不可用" description={error instanceof Error ? error.message : "请稍后重试。"} action={<Button variant="outline" onClick={() => void refetch()}>重新加载</Button>} />}
      {!loading && !isError && !current && <DataState kind="error" title="响应与当前研究对象不一致" description="已丢弃基金或区间不匹配的响应。" />}

      {current && !loading && (
        <>
          <PlainConclusion>
            {current.metrics.periodReturn == null
              ? "所选区间没有足够的真实累计净值，暂不生成收益结论。"
              : `${RESEARCH_PERIOD_LABELS[current.period]}累计收益 ${formatPercent(current.metrics.periodReturn)}，几何年化收益 ${formatPercent(current.metrics.annualizedReturn)}；相对沪深300参考基准的超额收益 ${formatPercent(current.metrics.excessReturn)}。`}
          </PlainConclusion>
          <MetricStrip items={[
            { label: "区间累计收益", value: formatPercent(current.metrics.periodReturn), note: "首末累计净值", tone: toneFor(current.metrics.periodReturn) },
            { label: "几何年化收益", value: formatPercent(current.metrics.annualizedReturn), note: "按真实日期 · 365.25 天", tone: toneFor(current.metrics.annualizedReturn) },
            { label: "沪深300参考收益", value: formatPercent(current.metrics.benchmarkReturn), note: "共同真实交易日", tone: toneFor(current.metrics.benchmarkReturn) },
            { label: "超额收益", value: formatPercent(current.metrics.excessReturn), note: "基金收益 − 参考收益", tone: toneFor(current.metrics.excessReturn) },
          ]} />
          <SourceNote>{current.name}（{current.code}） · 年化是数学换算，不代表全年实际收益或未来预期。</SourceNote>

          <ResearchSection title="收益曲线" description="基金和参考基准在共同首个交易日归一化为 0%，不填充不存在的观测。">
            {current.curve.length >= 2 ? <ReturnChart data={current.curve} code={current.code} /> : <DataState kind="missing" title="收益曲线不可计算" />}
          </ResearchSection>

          <ResearchSection title="自然年度收益" description="首期缺少上一年末基准时只计算所选区间内收益，并标记为不完整。">
            {current.annualReturns.length ? (
              <div className="research-table-wrap">
                <table className="data-table">
                  <thead><tr><th>年度</th><th className="numeric">收益</th><th>实际覆盖</th><th className="numeric">观测点</th><th>完整性</th></tr></thead>
                  <tbody>{current.annualReturns.map((item) => <tr key={item.label}><td>{item.label}</td><td className={`numeric ${returnTone(item.return)}`}>{formatPercent(item.return)}</td><td>{item.startDate} 至 {item.endDate}</td><td className="numeric">{item.observations}</td><td>{item.isPartial ? "不完整区间" : "完整周期"}</td></tr>)}</tbody>
                </table>
              </div>
            ) : <DataState kind="missing" title="年度收益不可计算" description="至少需要两个有效累计净值点。" />}
          </ResearchSection>

          <ResearchSection title="最近月度收益" description="展示所选区间最近 12 个有观测的自然月；当月属于不完整周期。">
            {current.monthlyReturns.length ? (
              <div className="research-table-wrap">
                <table className="data-table">
                  <thead><tr><th>月份</th><th className="numeric">收益</th><th>实际覆盖</th><th className="numeric">观测点</th><th>完整性</th></tr></thead>
                  <tbody>{current.monthlyReturns.slice(-12).reverse().map((item) => <tr key={item.label}><td>{item.label}</td><td className={`numeric ${returnTone(item.return)}`}>{formatPercent(item.return)}</td><td>{item.startDate} 至 {item.endDate}</td><td className="numeric">{item.observations}</td><td>{item.isPartial ? "不完整区间" : "完整周期"}</td></tr>)}</tbody>
                </table>
              </div>
            ) : <DataState kind="missing" title="月度收益不可计算" />}
          </ResearchSection>

          <ResearchSection title="多区间对比" description="点击区间可切换整页；样本不足的指标保留为 —。">
            <div className="research-table-wrap">
              <table className="data-table">
                <thead><tr><th>区间</th><th className="numeric">样本</th><th className="numeric">基金收益</th><th className="numeric">年化收益</th><th className="numeric">参考收益</th><th className="numeric">超额收益</th></tr></thead>
                <tbody>{current.periodComparisons.map((item) => <tr key={item.period}><td><button className="text-link min-h-11" type="button" onClick={() => setPeriod(item.period)}>{RESEARCH_PERIOD_LABELS[item.period]}{item.period === current.period ? " · 当前" : ""}</button></td><td className="numeric">{item.sampleCount}</td><td className="numeric">{formatPercent(item.fundReturn)}</td><td className="numeric">{formatPercent(item.annualizedReturn)}</td><td className="numeric">{formatPercent(item.benchmarkReturn)}</td><td className="numeric">{formatPercent(item.excessReturn)}</td></tr>)}</tbody>
              </table>
            </div>
          </ResearchSection>

          <div className="overview-evidence-grid">
            <ResearchSection title="数据覆盖">
              <KeyValueList items={[
                { label: "实际区间", value: `${current.coverage.dataStart ?? "—"} 至 ${current.coverage.dataEnd ?? "—"}` },
                { label: "基金有效样本", value: current.coverage.sampleCount },
                { label: "共同交易日", value: current.coverage.matchedSamples },
                { label: "基金来源", value: current.source },
                { label: "基准来源", value: current.benchmarkSource },
              ]} />
            </ResearchSection>
            <ResearchSection title="计算定义"><ul className="quality-note-list">{current.definitions.map((item) => <li key={item}>{item}</li>)}</ul></ResearchSection>
          </div>
        </>
      )}
    </div>
  );
}
