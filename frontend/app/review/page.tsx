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
  SourceNote,
  toneFor,
} from "@/components/research-ui";
import {
  DailyReview,
  HoldingItem,
  RealPortfolioSummary,
  getAllHoldings,
  getDailyReview,
  getRealPortfolio,
  formatCurrency,
  formatPercent,
} from "@/services/fund";

export default function ReviewPage() {
  const [portfolio, setPortfolio] = useState<RealPortfolioSummary | null>(null);
  const [allHoldings, setAllHoldings] = useState<HoldingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dailyReview, setDailyReview] = useState<DailyReview | null>(null);

  useEffect(() => {
    Promise.all([getRealPortfolio(), getAllHoldings()])
      .then(([summary, holdings]) => { setPortfolio(summary); setAllHoldings(holdings); })
      .catch((requestError) => { console.error("Review portfolio request failed", requestError); setError("投资数据暂时不可用，请重新加载。"); })
      .finally(() => setLoading(false));
    getDailyReview().then(setDailyReview).catch((requestError) => { console.error("Daily review request failed", requestError); setDailyReview(null); });
  }, []);

  const activeHoldings = (portfolio?.holdings ?? []).filter((holding) => !holding.is_sold);
  const soldHoldings = allHoldings.filter((holding) => holding.is_sold);
  const totalValue = portfolio?.total_value ?? 0;
  const totalProfit = portfolio?.total_profit ?? 0;
  const totalProfitPct = portfolio?.total_profit_pct ?? 0;
  const hasData = activeHoldings.length > 0 || soldHoldings.length > 0;

  const chartData = activeHoldings
    .filter((holding) => holding.buy_date && holding.current_value != null)
    .map((holding) => ({
      name: holding.fund_name.length > 8 ? holding.fund_name.slice(0, 8) + "…" : holding.fund_name,
      value: holding.current_value as number,
    }))
    .sort((a, b) => b.value - a.value);

  const typeMap: Record<string, {
    value: number;
    cost: number;
    profit: number;
    count: number;
    valueComplete: boolean;
    costComplete: boolean;
    profitComplete: boolean;
  }> = {};
  for (const holding of activeHoldings) {
    const type = holding.fund_type || "其他";
    if (!typeMap[type]) {
      typeMap[type] = {
        value: 0,
        cost: 0,
        profit: 0,
        count: 0,
        valueComplete: true,
        costComplete: true,
        profitComplete: true,
      };
    }
    typeMap[type].value += holding.current_value ?? 0;
    typeMap[type].cost += holding.cost ?? 0;
    typeMap[type].profit += holding.profit ?? 0;
    typeMap[type].valueComplete &&= holding.current_value != null;
    typeMap[type].costComplete &&= holding.cost != null;
    typeMap[type].profitComplete &&= holding.profit != null;
    typeMap[type].count += 1;
  }
  const attributionData = Object.entries(typeMap).map(([name, data]) => ({
    name,
    value: totalValue > 0 && data.valueComplete ? Math.round((data.value / totalValue) * 100) : null,
    profit: data.profitComplete ? data.profit : null,
    profitPct: data.costComplete && data.profitComplete && data.cost > 0 ? (data.profit / data.cost) * 100 : null,
    count: data.count,
  }));

  const observations: { title: string; content: string }[] = [];
  if (hasData) {
    const ratedHoldings = activeHoldings.filter((holding): holding is HoldingItem & { profit_pct: number } => holding.profit_pct != null);
    const bestHolding = [...ratedHoldings].sort((a, b) => b.profit_pct - a.profit_pct)[0];
    const worstHolding = [...ratedHoldings].sort((a, b) => a.profit_pct - b.profit_pct)[0];
    const stockRatio = (typeMap["股票型"]?.value ?? 0) + (typeMap["ETF"]?.value ?? 0) + (typeMap["ETF联接"]?.value ?? 0);
    const bondRatio = (typeMap["债券型"]?.value ?? 0) + (typeMap["货币型"]?.value ?? 0);
    if (bestHolding && bestHolding.profit_pct > 0) observations.push({ title: "最佳表现", content: `${bestHolding.fund_name} 盈利 ${bestHolding.profit_pct.toFixed(2)}%，是当前持仓中表现最好的基金。` });
    if (worstHolding && worstHolding.profit_pct < 0) observations.push({ title: "需关注", content: `${worstHolding.fund_name} 亏损 ${Math.abs(worstHolding.profit_pct).toFixed(2)}%，建议评估是否继续持有或调整仓位。` });
    if (totalValue > 0 && activeHoldings.every((holding) => holding.current_value != null)) {
      const stockPct = (stockRatio / totalValue) * 100;
      const bondPct = (bondRatio / totalValue) * 100;
      if (stockPct > 80) observations.push({ title: "配置建议", content: `权益类占比 ${stockPct.toFixed(0)}%，集中度较高。建议增加债券型基金至 20%-40% 以降低组合波动。` });
      else if (bondPct > 80) observations.push({ title: "配置建议", content: `固收类占比 ${bondPct.toFixed(0)}%，偏保守。如投资期限较长，可适度增加权益类配置提升长期收益。` });
      else observations.push({ title: "配置建议", content: `权益 ${stockPct.toFixed(0)}% / 固收 ${bondPct.toFixed(0)}%，配置较为均衡。坚持定投，定期再平衡。` });
    }
  }

  if (loading) return <div className="page-container"><DataState kind="loading" title="加载投资数据" description="正在读取真实持仓、交易记录与每日复盘。" /></div>;
  if (error) return <div className="page-container"><PageHeader title="投资复盘" description="基于真实持仓数据回顾收益来源和配置。" /><DataState kind="error" title="数据加载失败" description={error} action={<Button onClick={() => window.location.reload()} variant="outline">重新加载</Button>} /></div>;
  if (!hasData) return <div className="page-container"><PageHeader title="投资复盘" description="回顾投资表现，识别收益来源与改进空间。" /><DataState kind="empty" title="暂无持仓数据" description="录入真实交易记录后，这里将展示投资收益、持仓分析和配置观察。" action={<Link href="/portfolio"><Button>去录入持仓</Button></Link>} /></div>;

  return (
    <div className="page-container">
      <PageHeader title="投资复盘" description="基于真实持仓与交易记录，回顾当前盈亏、资产配置和历史交易。" />
      <PlainConclusion>
        {dailyReview?.summary || (portfolio?.total_value != null && portfolio.total_profit != null && portfolio.total_profit_pct != null
          ? `当前持仓市值为 ${formatCurrency(totalValue, 0)}，浮动盈亏为 ${formatCurrency(totalProfit, 0)}（${formatPercent(totalProfitPct * 0.01)}）。以下按基金、资产类型和交易记录展开。`
          : "部分组合估值指标缺失，相关位置显示为“—”；以下仅展开可用的基金、资产类型和交易记录。")}
      </PlainConclusion>
      <MetricStrip items={[
        { label: "持仓市值", value: portfolio?.total_value != null ? formatCurrency(totalValue, 0) : "—", note: `${activeHoldings.length} 只基金` },
        { label: "浮动盈亏", value: portfolio?.total_profit != null ? formatCurrency(totalProfit, 0) : "—", note: portfolio?.total_profit_pct != null ? formatPercent(totalProfitPct * 0.01) : "估值不完整", tone: toneFor(portfolio?.total_profit) },
        { label: "已平仓数量", value: `${soldHoldings.length} 笔`, note: "历史交易记录" },
        { label: "持仓类型", value: `${Object.keys(typeMap).length} 种`, note: "资产类别分布" },
      ]} />

      <ResearchSection title="每日复盘" description={`${dailyReview?.date ? `${dailyReview.date} · ` : ""}基于你的真实持仓与今日收益归因自动生成，仅供参考。`}>
        {dailyReview && dailyReview.segments.length > 0 ? (
          <div className="border-t border-border">
            {dailyReview.segments.map((segment, index) => (
              <div key={`${segment.type}-${index}`} className="grid gap-1 border-b border-border py-4 sm:grid-cols-[96px_1fr] sm:gap-5">
                <span className="text-xs font-medium text-muted-foreground">{segment.type}</span>
                <p className="m-0 leading-relaxed">{segment.text}</p>
              </div>
            ))}
          </div>
        ) : <DataState kind="empty" title="暂无复盘内容" description="复盘接口未返回内容，不影响下方真实持仓数据。" />}
        <SourceNote>{dailyReview?.provider === "llm" ? "模型生成" : "规则生成"}。根据历史数据生成，仅帮助理解，不构成买卖建议。</SourceNote>
      </ResearchSection>

      <ResearchSection title="持仓市值分布" description="按当前市值从高到低排列；图中数值仍使用原有持仓计算。">
        {chartData.length > 0 ? <div className="chart-frame h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} dy={8} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} tickFormatter={(value) => `¥${(value / 10000).toFixed(0)}万`} />
              <Tooltip contentStyle={{ background: "var(--background)", border: "1px solid var(--border)", borderRadius: 6 }} formatter={(value) => [formatCurrency(Number(value), 0), "当前市值"]} />
              <Area type="monotone" dataKey="value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.08} strokeWidth={2} dot={{ r: 3, fill: "var(--accent)" }} name="当前市值" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div> : <DataState kind="empty" title="暂无可用持仓市值" description="当前净值缺失的持仓不会被填成 0。" />}
      </ResearchSection>

      <ResearchSection title="资产类型分布" description="按基金类型汇总仓位与浮动盈亏；任一来源值缺失时，该类型相关结果显示为“—”。">
        <div className="grid gap-x-12 lg:grid-cols-2">
          <div>{attributionData.map((item) => (
            <div className="allocation-row" key={item.name}>
              <span>{item.name}<small className="block text-xs text-muted-foreground">{item.count} 只</small></span>
              <div className="allocation-track"><div className="allocation-fill" style={{ width: `${item.value != null ? Math.min(100, item.value) : 0}%` }} /></div>
              <span className="numeric font-semibold">{item.value != null ? `${item.value}%` : "—"}</span>
            </div>
          ))}</div>
          <KeyValueList items={attributionData.map((item) => ({
            label: `${item.name}浮动盈亏`, note: `成本口径收益率 ${item.profitPct != null ? `${item.profitPct.toFixed(2)}%` : "—"}`,
            value: <span className={item.profit == null ? "text-muted-foreground" : item.profit >= 0 ? "text-positive" : "text-negative"}>{item.profit != null ? `${item.profit >= 0 ? "+" : ""}${formatCurrency(item.profit, 0)}` : "—"}</span>,
          }))} />
        </div>
      </ResearchSection>

      <ResearchSection title="交易记录" description={allHoldings.length > 0 ? `共 ${allHoldings.length} 笔交易（含 ${soldHoldings.length} 笔已平仓），最多展示前 20 笔。` : "暂无交易记录"}>
        {allHoldings.length > 0 ? <div className="overflow-x-auto"><table className="data-table min-w-[760px]">
          <thead><tr><th>基金</th><th>买入日期</th><th>卖出日期</th><th className="numeric">成本</th><th className="numeric">市值/卖出金额</th><th className="numeric">盈亏</th><th className="numeric">状态</th></tr></thead>
          <tbody>{allHoldings.slice(0, 20).map((holding) => {
            const profit = holding.is_sold
              ? holding.sell_amount != null && holding.cost != null
                ? holding.sell_amount - holding.cost
                : null
              : holding.profit;
            const profitPct = holding.is_sold
              ? holding.cost != null && holding.cost > 0 && holding.sell_amount != null
                ? (holding.sell_amount - holding.cost) / holding.cost * 100
                : null
              : holding.profit_pct;
            const displayValue = holding.is_sold ? holding.sell_amount : holding.current_value;
            return <tr key={holding.id}>
              <td><span className="font-medium">{holding.fund_name}</span><span className="block text-xs text-muted-foreground">{holding.fund_code}</span></td>
              <td className="text-muted-foreground">{holding.buy_date}</td><td className="text-muted-foreground">{holding.is_sold ? holding.sell_date : "—"}</td>
              <td className="numeric">{holding.cost != null ? formatCurrency(holding.cost, 0) : "—"}</td><td className="numeric">{displayValue != null ? formatCurrency(displayValue, 0) : "—"}</td>
              <td className={`numeric font-semibold ${profit == null ? "text-muted-foreground" : profit >= 0 ? "text-positive" : "text-negative"}`}>
                {profit != null ? (
                  <>{profit >= 0 ? "+" : ""}{formatCurrency(profit, 0)}<span className="block text-xs">{profitPct != null ? `(${profitPct >= 0 ? "+" : ""}${profitPct.toFixed(2)}%)` : "收益率 —"}</span></>
                ) : "—"}
              </td>
              <td className="numeric">{holding.is_sold ? "已平仓" : "持有中"}</td>
            </tr>;
          })}</tbody>
        </table></div> : <DataState kind="empty" title="暂无交易记录" action={<Link href="/portfolio" className="text-link">前往我的组合录入持仓</Link>} />}
      </ResearchSection>

      {observations.length > 0 && (
        <ResearchSection title="配置与持仓观察" description="以下内容沿用既有规则，仅用于复盘，不替代个人判断。">
          <div className="border-t border-border">{observations.map((item) => <div key={item.title} className="grid gap-1 border-b border-border py-4 sm:grid-cols-[128px_1fr] sm:gap-5"><h3 className="m-0 text-sm font-semibold">{item.title}</h3><p className="m-0 text-sm leading-relaxed text-muted-foreground">{item.content}</p></div>)}</div>
          <SourceNote>根据历史数据生成，仅帮助理解，不构成买卖建议。</SourceNote>
        </ResearchSection>
      )}
    </div>
  );
}
