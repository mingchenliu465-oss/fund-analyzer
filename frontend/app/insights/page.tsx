"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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
import { PortfolioHistoryPeriod, PortfolioInsights, getPortfolioInsights, formatCurrency } from "@/services/fund";

const periods: { key: PortfolioHistoryPeriod; label: string }[] = [
  { key: "1W", label: "1周" }, { key: "1M", label: "1月" }, { key: "3M", label: "3月" }, { key: "1Y", label: "1年" }, { key: "ALL", label: "全部" },
];
function signedCurrency(value: number) { return `${value >= 0 ? "+" : "−"}${formatCurrency(Math.abs(value), 2)}`; }
function signedPercent(value: number | null) { return value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`; }
function tone(value: number) { return value >= 0 ? "text-positive" : "text-negative"; }

export default function PortfolioInsightsPage() {
  const [period, setPeriod] = useState<PortfolioHistoryPeriod>("1M");
  const [data, setData] = useState<PortfolioInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    getPortfolioInsights(period)
      .then(setData)
      .catch((requestError) => { console.error("Portfolio insights request failed", requestError); setData(null); setError(true); })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      getPortfolioInsights(period)
        .then((result) => { if (!cancelled) { setData(result); setError(false); } })
        .catch((requestError) => { if (!cancelled) { console.error("Portfolio insights request failed", requestError); setData(null); setError(true); } })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 0);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [period]);

  if (loading) return <div className="page-container"><DataState kind="loading" title="正在整理组合数据" description="读取真实持仓、净值、历史快照与市场指数。" /></div>;
  if (error || !data) {
    return <div className="page-container"><PageHeader title="组合洞察" description="解释组合收益来源、集中度和相对市场表现。" /><DataState kind="error" title="暂时无法生成组合洞察" description="请确认后端服务已启动，或稍后重试；不会使用示例组合。" action={<Button onClick={load} variant="outline">重新加载</Button>} /></div>;
  }

  const { headline, return_explanation: explanation, risk, market_comparison: markets, history } = data;
  const hasHoldings = explanation.contributions.length > 0;

  return (
    <div className="page-container">
      <PageHeader
        title="组合洞察"
        description="把收益来源、集中度、历史变化和指数表现放在一起看。"
        action={<SegmentedControl label="组合洞察区间" value={period} onChange={setPeriod} items={periods.map((item) => ({ value: item.key, label: item.label }))} />}
      />

      {!hasHoldings ? (
        <DataState kind="empty" title="还没有组合数据" description="录入真实持仓后，这里会解释每天的收益来源和风险。" action={<Link href="/portfolio"><Button>去录入持仓</Button></Link>} />
      ) : (
        <>
          <PlainConclusion note={data.data_status === "partial" ? "部分基金行情待更新，当前解释可能不完整。根据历史数据生成，仅帮助理解，不构成买卖建议。" : undefined}>
            {headline.sentence}
          </PlainConclusion>
          <MetricStrip items={[
            { label: "今日收益", value: signedCurrency(headline.today_return), note: "按可用净值计算", tone: toneFor(headline.today_return) },
            { label: "今日收益率", value: signedPercent(headline.today_return_pct), note: "相对上一交易日", tone: toneFor(headline.today_return_pct) },
            { label: "集中度", value: risk.concentration_level, note: `HHI ${risk.hhi.toFixed(0)}` },
            { label: "最大持仓占比", value: `${risk.max_holding.weight_pct.toFixed(1)}%`, note: risk.max_holding.fund_name ?? "—" },
          ]} />
          <SourceNote>生成时间：{data.generated_at} · 区间：{period} · 数据状态：{data.data_status}</SourceNote>

          <ResearchSection title="今天的收益来自哪里" description="按基金贡献排序：正数表示增加组合收益，负数表示拖累。">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>基金</th><th className="numeric">当日涨跌</th><th className="numeric">收益贡献</th><th className="numeric">贡献占比</th></tr></thead>
                <tbody>{explanation.contributions.map((item) => (
                  <tr key={item.fund_code}>
                    <td><span className="font-medium">{item.fund_name}</span><span className="block text-xs text-muted-foreground">{item.fund_code}</span></td>
                    <td className={`numeric ${tone(item.change_pct)}`}>{signedPercent(item.change_pct)}</td>
                    <td className={`numeric font-semibold ${tone(item.contribution)}`}>{item.nav_stale ? "待更新" : signedCurrency(item.contribution)}</td>
                    <td className="numeric">{Math.abs(item.contribution_rate * 100).toFixed(1)}%</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <SourceNote>正贡献合计 {signedCurrency(explanation.positive_total)}；负贡献合计 {signedCurrency(explanation.negative_total)}；待更新净值 {explanation.stale_count} 只。</SourceNote>
          </ResearchSection>

          <ResearchSection title="组合风险与仓位" description="集中度基于当前持仓市值；HHI 越高，持仓越集中。">
            <div className="grid gap-x-12 lg:grid-cols-2">
              <div>
                {risk.allocation.map((item) => (
                  <div className="allocation-row" key={item.category}>
                    <span>{item.category}<small className="block text-xs text-muted-foreground">{item.holding_count} 只</small></span>
                    <div className="allocation-track"><div className="allocation-fill" style={{ width: `${Math.min(100, item.weight_pct)}%` }} /></div>
                    <span className="numeric font-semibold">{item.weight_pct.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
              <KeyValueList items={[
                { label: "最大持仓", value: risk.max_holding.fund_name ?? "—" },
                { label: "最大持仓市值", value: formatCurrency(risk.max_holding.value, 2) },
                { label: "最大持仓占比", value: `${risk.max_holding.weight_pct.toFixed(1)}%` },
                { label: "集中度比率", value: `${risk.concentration_ratio.toFixed(1)}%` },
                { label: "基金底层重叠", value: risk.overlap_status === "available" ? `${risk.overlap_pairs.length} 组存在明显重叠` : "—", note: risk.overlap_status === "available" ? "基于真实季报持仓" : "暂无足够真实季报数据，暂不判断" },
              ]} />
            </div>
            {risk.notes.length > 0 && <div className="disclosure mt-4">{risk.notes.map((note) => <p key={note}>{note}</p>)}</div>}
          </ResearchSection>

          <ResearchSection title="最近组合变化" description={history.note}>
            {history.points.length >= 2 ? (
              <div className="chart-frame h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={history.points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                    <XAxis dataKey="date" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} />
                    <YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(value) => `¥${Number(value).toLocaleString()}`} />
                    <Tooltip contentStyle={{ background: "var(--background)", border: "1px solid var(--border)", borderRadius: 6 }} formatter={(value) => [formatCurrency(Number(value), 2), "总资产"]} />
                    <Area type="monotone" dataKey="total_value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.08} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : <DataState kind="empty" title="历史快照还不够" description="继续使用组合页后，这里会逐渐形成趋势。" />}
            <SourceNote>趋势：{history.trend}{history.anomaly_detected ? ` · ${history.anomaly_date} 出现异常波动${history.anomaly_reason ? `：${history.anomaly_reason}` : ""}` : ""}</SourceNote>
          </ResearchSection>

          <ResearchSection title="相对市场表现" description={`区间：${period}。相对收益 = 组合区间收益 − 指数区间收益。`}>
            <div className="overflow-x-auto"><table className="data-table">
              <thead><tr><th>指数</th><th className="numeric">组合收益</th><th className="numeric">指数收益</th><th className="numeric">相对收益</th></tr></thead>
              <tbody>{markets.map((market) => <tr key={market.code}>
                <td>{market.name}<span className="block text-xs text-muted-foreground">{market.code}</span></td>
                <td className="numeric">{signedPercent(market.portfolio_return_pct)}</td>
                <td className="numeric">{signedPercent(market.index_return_pct)}</td>
                <td className={`numeric font-semibold ${market.available && market.relative_return_pct != null ? tone(market.relative_return_pct) : "text-muted-foreground"}`}>{market.available ? signedPercent(market.relative_return_pct) : "—"}<span className="block text-xs font-normal text-muted-foreground">{market.available ? "组合减指数" : market.reason ?? "数据不足"}</span></td>
              </tr>)}</tbody>
            </table></div>
          </ResearchSection>

          <ResearchSection title="每日复盘基础" description="当前使用真实持仓、净值和快照生成，暂未接入大模型。" action={<Link href="/review" className="text-link text-sm">查看完整复盘</Link>}>
            <KeyValueList columns={2} items={data.review_context.map((fact) => ({ label: fact.label, value: fact.value, note: fact.source }))} />
            <SourceNote>规则分析。根据历史数据生成，仅帮助理解，不构成买卖建议。</SourceNote>
          </ResearchSection>

          <div className="disclosure border-t border-border pt-5">
            <p>数据说明：场外基金通常为 T-1 净值；历史资产变化未扣除期间现金流；底层重叠仅在真实季报数据可用时判断。</p>
            {data.notes.map((note) => <p key={note}>{note}</p>)}
          </div>
        </>
      )}
    </div>
  );
}
