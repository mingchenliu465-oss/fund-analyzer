"use client";

import { FormEvent, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, Search } from "lucide-react";
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
import { Button } from "@/components/ui/button";
import {
  DataState,
  KeyValueList,
  MetricStrip,
  PageHeader,
  PlainConclusion,
  ResearchSection,
  SegmentedControl,
  SourceNote,
  toneFor,
} from "@/components/research-ui";
import { useFundSearch } from "@/hooks/use-fund-search";
import { CHART_BENCHMARK, CHART_GRID, CHART_PRIMARY } from "@/lib/chart-theme";
import { excessReturn, isCurrentOverview, overviewConclusion } from "@/lib/overview";
import {
  DEFAULT_RESEARCH_PREFERENCES,
  readResearchPreferences,
  RESEARCH_PERIODS,
  ResearchPeriod,
} from "@/lib/research-preferences";
import { formatPercent, formatRatio, getFundOverview } from "@/services/fund";

const PERIOD_OPTIONS = RESEARCH_PERIODS.map((value) => ({
  value,
  label: { "1m": "近1月", "3m": "近3月", "6m": "近6月", "1y": "近1年", "3y": "近3年", all: "成立以来" }[value],
}));

const qualityState = {
  normal: { kind: "success" as const, title: "区间数据通过基础检查" },
  warning: { kind: "partial" as const, title: "数据经过清洗，请查看处理记录" },
  stale: { kind: "stale" as const, title: "净值可能不是最新，请留意日期" },
  missing: { kind: "missing" as const, title: "所选区间缺少有效累计净值" },
};

export default function OverviewDashboard() {
  const [code, setCode] = useState(DEFAULT_RESEARCH_PREFERENCES.defaultCode);
  const [period, setPeriod] = useState<ResearchPeriod>(DEFAULT_RESEARCH_PREFERENCES.defaultPeriod);
  const [draft, setDraft] = useState(DEFAULT_RESEARCH_PREFERENCES.defaultCode);
  const [ready, setReady] = useState(false);
  const [inputError, setInputError] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const { suggestions, isSearching } = useFundSearch(draft, 5);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const preferences = readResearchPreferences();
      setCode(preferences.defaultCode);
      setPeriod(preferences.defaultPeriod);
      setDraft(preferences.defaultCode);
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["fundOverview", code, period],
    queryFn: () => getFundOverview(code, period),
    enabled: ready,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const current = isCurrentOverview(data, code, period) ? data : undefined;
  const loading = !ready || isPending || (isFetching && !current);

  function selectFund(nextCode: string) {
    setCode(nextCode);
    setDraft(nextCode);
    setInputError("");
    setSearchOpen(false);
  }

  function submitFund(event: FormEvent) {
    event.preventDefault();
    const normalized = draft.trim();
    if (!/^\d{6}$/.test(normalized)) {
      setInputError("请输入 6 位基金代码，例如 161725。");
      return;
    }
    selectFund(normalized);
  }

  return (
    <div className="page-container">
      <PageHeader
        title="研究概览"
        description="Research with Evidence. 把区间收益、风险、基准与数据证据放在同一视图。"
        action={current ? (
          <Link className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-accent" href={`/fund/${current.code}`}>
            基金完整档案 <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ) : undefined}
      />

      <section className="overview-controls" aria-label="研究对象与区间">
        <form className="overview-fund-form" onSubmit={submitFund}>
          <label htmlFor="overview-code">研究基金</label>
          <div className="overview-search-wrap">
            <div className="overview-search-field">
              <Search size={16} aria-hidden="true" />
              <input
                id="overview-code"
                value={draft}
                inputMode="numeric"
                autoComplete="off"
                placeholder="输入 6 位基金代码"
                aria-describedby={inputError ? "overview-code-error" : undefined}
                onFocus={() => setSearchOpen(true)}
                onChange={(event) => {
                  setDraft(event.target.value);
                  setSearchOpen(true);
                  setInputError("");
                }}
              />
            </div>
            {searchOpen && draft.trim() && (isSearching || suggestions.length > 0) && (
              <div className="overview-suggestions" role="listbox" aria-label="基金搜索结果">
                {isSearching && <p>正在搜索真实基金名录…</p>}
                {suggestions.map((fund) => (
                  <button type="button" role="option" aria-selected={fund.code === code} key={fund.code} onClick={() => selectFund(fund.code)}>
                    <span><strong>{fund.name}</strong><small>{fund.code} · {fund.type}</small></span>
                    <ArrowRight size={15} aria-hidden="true" />
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button type="submit">切换基金</Button>
          {inputError && <p className="field-error" id="overview-code-error" role="alert">{inputError}</p>}
        </form>
        <SegmentedControl items={PERIOD_OPTIONS} value={period} onChange={setPeriod} label="统计区间" />
      </section>

      {loading && <DataState kind="loading" title={`正在读取 ${code} 的真实区间数据`} description="基金指标与参考基准分别获取；不会使用演示数据补位。" />}
      {!loading && isError && (
        <DataState
          kind="error"
          title="研究数据暂时不可用"
          description={error instanceof Error ? error.message : "请稍后重试。"}
          action={<Button variant="outline" onClick={() => void refetch()}>重新加载</Button>}
        />
      )}
      {!loading && !isError && !current && (
        <DataState kind="error" title="响应与当前研究对象不一致" description="为避免不同基金或区间的数据混用，本页已丢弃该响应。" />
      )}

      {current && !loading && (
        <div aria-busy={isFetching}>
          <PlainConclusion note="历史统计不构成未来收益承诺。沪深300为统一参考基准，并非基金合同基准。">
            {overviewConclusion(current)}
          </PlainConclusion>

          <MetricStrip
            items={[
              { label: "区间累计收益", value: formatPercent(current.metrics.periodReturn), note: `${current.dataStart ?? "—"} 起`, tone: toneFor(current.metrics.periodReturn) },
              { label: "年化波动率", value: formatPercent(current.metrics.volatility).replace(/^\+/, ""), note: "日收益 · 252 日年化", tone: "risk" },
              { label: "最大回撤", value: formatPercent(current.metrics.maxDrawdown), note: "基于区间累计净值", tone: "risk" },
              { label: "Sharpe", value: formatRatio(current.metrics.sharpe), note: "无风险利率 2%", tone: "neutral" },
              { label: "沪深300参考收益", value: formatPercent(current.benchmark.periodReturn), note: `超额 ${formatPercent(excessReturn(current))}`, tone: toneFor(current.benchmark.periodReturn) },
            ]}
          />
          <SourceNote>
            {current.name}（{current.code}） · {current.dataStart ?? "—"} 至 {current.dataEnd ?? "—"} · 有效净值 {current.sampleCount} 点
          </SourceNote>

          <ResearchSection title="基金与参考基准" description="两条曲线均在共同首个交易日归一化为 0%。仅使用双方都有真实观测的日期，不前向填充、不插值。">
            {current.curve.length >= 2 ? (
              <div className="chart-frame" aria-label="基金与沪深300参考基准归一化收益曲线">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={current.curve} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke={CHART_GRID} vertical={false} />
                    <XAxis dataKey="date" minTickGap={36} tickLine={false} axisLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                    <YAxis domain={["auto", "auto"]} tickFormatter={(value: number) => formatPercent(value - 1).replace("+", "")} tickLine={false} axisLine={false} width={58} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} />
                    <Tooltip
                      labelFormatter={(label) => `日期 ${label}`}
                      formatter={(value, name) => [
                        typeof value === "number" ? formatPercent(value - 1) : "—",
                        name === "fund" ? current.code : "沪深300",
                      ]}
                    />
                    <Legend formatter={(value) => value === "fund" ? current.code : "沪深300（参考）"} />
                    <ReferenceLine y={1} stroke="var(--border)" />
                    <Line type="linear" dataKey="fund" stroke={CHART_PRIMARY} strokeWidth={2} dot={false} activeDot={{ r: 3 }} isAnimationActive={false} />
                    <Line type="linear" dataKey="benchmark" stroke={CHART_BENCHMARK} strokeWidth={1.6} strokeDasharray="5 4" dot={false} activeDot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <DataState kind="missing" title="归一化曲线不可计算" description="至少需要两个有效累计净值观测点。" />
            )}
            <SourceNote>{current.benchmark.note} 共同日期 {current.benchmark.matchedSamples} 个；仅基金有值 {current.benchmark.fundOnlyDates} 个，仅基准有值 {current.benchmark.benchmarkOnlyDates} 个。</SourceNote>
          </ResearchSection>

          <div className="overview-evidence-grid">
            <ResearchSection title="数据证据" description="指标状态和实际样本范围与图表同源。">
              <DataState {...qualityState[current.qualityStatus]} description={current.qualityNotes.length ? undefined : "未发现重复日期、非正累计净值或明显时效问题。"} />
              <KeyValueList
                items={[
                  { label: "基金数据来源", value: current.source },
                  { label: "基准数据来源", value: current.benchmark.source },
                  { label: "实际数据范围", value: `${current.dataStart ?? "—"} 至 ${current.dataEnd ?? "—"}` },
                  { label: "有效样本", value: `${current.sampleCount} 个累计净值点` },
                  { label: "重复日期 / 无效记录", value: `${current.duplicateDates} / ${current.invalidNavRecords}` },
                ]}
              />
              {current.qualityNotes.length > 0 && (
                <ul className="quality-note-list">{current.qualityNotes.map((note) => <li key={note}>{note}</li>)}</ul>
              )}
              <SourceNote>响应生成时间：{new Date(current.generatedAt).toLocaleString("zh-CN")}</SourceNote>
            </ResearchSection>

            <ResearchSection title="研究边界" description="历史统计、数据质量与策略回测是不同证据，不能相互替代。">
              <DataState kind="unsupported" title="本页未运行回测" description="Overview 只呈现真实历史净值统计，不生成交易信号，也不把回测结果表述为未来收益。" />
              <KeyValueList
                items={[
                  { label: "收益口径", value: "累计净值" },
                  { label: "波动率 / Sharpe", value: "252 个交易日年化" },
                  { label: "无风险利率", value: "年化 2%" },
                  { label: "基准性质", value: "统一参考，非合同基准" },
                ]}
              />
              <Link className="inline-flex min-h-11 items-center gap-2 pt-4 text-sm font-medium text-accent" href={`/backtest?code=${current.code}`}>
                前往回测实验室 <ArrowRight size={15} aria-hidden="true" />
              </Link>
            </ResearchSection>
          </div>
        </div>
      )}
    </div>
  );
}
