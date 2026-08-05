"use client";

import { useEffect, useState } from "react";
import { MetricCard } from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Briefcase,
  FileText,
  Lightbulb,
  Target,
  TrendingUp,
  Trophy,
} from "lucide-react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  HoldingItem,
  RealPortfolioSummary,
  getAllHoldings,
  getRealPortfolio,
  formatCurrency,
  formatPercent,
} from "@/services/fund";

export default function ReviewPage() {
  const [portfolio, setPortfolio] = useState<RealPortfolioSummary | null>(null);
  const [allHoldings, setAllHoldings] = useState<HoldingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getRealPortfolio().catch(() => null),
      getAllHoldings().catch(() => [] as HoldingItem[]),
    ])
      .then(([summary, holdings]) => {
        setPortfolio(summary);
        setAllHoldings(holdings);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  // ── Derived data ──

  const activeHoldings = (portfolio?.holdings ?? []).filter((h) => !h.is_sold);
  const soldHoldings = allHoldings.filter((h) => h.is_sold);
  const totalValue = portfolio?.total_value ?? 0;
  const totalCost = portfolio?.total_cost ?? 0;
  const totalProfit = portfolio?.total_profit ?? 0;
  const totalProfitPct = portfolio?.total_profit_pct ?? 0;
  const hasData = activeHoldings.length > 0 || soldHoldings.length > 0;

  // Build cumulative return chart from holdings
  const chartData = activeHoldings
    .filter((h) => h.buy_date && h.current_value != null)
    .map((h) => ({
      name: h.fund_name.length > 8 ? h.fund_name.slice(0, 8) + "…" : h.fund_name,
      cost: h.cost ?? 0,
      value: h.current_value ?? 0,
      profit: h.profit ?? 0,
    }))
    .sort((a, b) => b.value - a.value);

  // Calculate type allocation for attribution
  const typeMap: Record<string, { value: number; cost: number; profit: number; count: number }> = {};
  for (const h of activeHoldings) {
    const t = h.fund_type || "其他";
    if (!typeMap[t]) typeMap[t] = { value: 0, cost: 0, profit: 0, count: 0 };
    typeMap[t].value += h.current_value ?? 0;
    typeMap[t].cost += h.cost ?? 0;
    typeMap[t].profit += h.profit ?? 0;
    typeMap[t].count += 1;
  }

  const attributionData = Object.entries(typeMap).map(([name, d]) => ({
    name,
    value: totalValue > 0 ? Math.round((d.value / totalValue) * 100) : 0,
    profit: d.profit,
    profitPct: d.cost > 0 ? (d.profit / d.cost) * 100 : 0,
    count: d.count,
  }));

  // Generate insights
  const insights: { icon: typeof Trophy; title: string; content: string }[] = [];
  if (hasData) {
    const bestHolding = [...activeHoldings].sort((a, b) => (b.profit_pct ?? 0) - (a.profit_pct ?? 0))[0];
    const worstHolding = [...activeHoldings].sort((a, b) => (a.profit_pct ?? 0) - (b.profit_pct ?? 0))[0];
    const stockRatio = (typeMap["股票型"]?.value ?? 0) + (typeMap["ETF"]?.value ?? 0) + (typeMap["ETF联接"]?.value ?? 0);
    const bondRatio = (typeMap["债券型"]?.value ?? 0) + (typeMap["货币型"]?.value ?? 0);

    if (bestHolding && (bestHolding.profit_pct ?? 0) > 0) {
      insights.push({
        icon: Trophy,
        title: "最佳表现",
        content: `${bestHolding.fund_name} 盈利 ${(bestHolding.profit_pct ?? 0).toFixed(2)}%，是当前持仓中表现最好的基金。`,
      });
    }
    if (worstHolding && (worstHolding.profit_pct ?? 0) < 0) {
      insights.push({
        icon: Target,
        title: "需关注",
        content: `${worstHolding.fund_name} 亏损 ${Math.abs(worstHolding.profit_pct ?? 0).toFixed(2)}%，建议评估是否继续持有或调整仓位。`,
      });
    }
    if (totalValue > 0) {
      const stockPct = (stockRatio / totalValue) * 100;
      const bondPct = (bondRatio / totalValue) * 100;
      if (stockPct > 80) {
        insights.push({
          icon: Lightbulb,
          title: "配置建议",
          content: `权益类占比 ${stockPct.toFixed(0)}%，集中度较高。建议增加债券型基金至 20%-40% 以降低组合波动。`,
        });
      } else if (bondPct > 80) {
        insights.push({
          icon: Lightbulb,
          title: "配置建议",
          content: `固收类占比 ${bondPct.toFixed(0)}%，偏保守。如投资期限较长，可适度增加权益类配置提升长期收益。`,
        });
      } else {
        insights.push({
          icon: Lightbulb,
          title: "配置建议",
          content: `权益 ${stockPct.toFixed(0)}% / 固收 ${bondPct.toFixed(0)}%，配置较为均衡。坚持定投，定期再平衡。`,
        });
      }
    }
  }

  // ── Loading state ──
  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-20 text-center">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-foreground/20 border-t-foreground" />
        <p className="mt-4 text-sm text-muted-foreground">加载投资数据…</p>
      </div>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-20 text-center">
        <FileText className="mx-auto h-12 w-12 text-muted-foreground/30" />
        <h1 className="mt-4 text-xl font-semibold">数据加载失败</h1>
        <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        <Button
          onClick={() => window.location.reload()}
          variant="outline"
          className="mt-4 h-10 rounded-xl"
        >
          重新加载
        </Button>
      </div>
    );
  }

  // ── Empty state ──
  if (!hasData) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <section className="mb-12">
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
            className="text-2xl font-semibold tracking-tight sm:text-3xl"
          >
            投资复盘
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
            className="mt-2 text-muted-foreground"
          >
            回顾投资表现，识别收益来源与改进空间
          </motion.p>
        </section>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="rounded-2xl border border-dashed border-border bg-muted/40 p-16 text-center"
        >
          <Briefcase className="mx-auto mb-4 h-12 w-12 text-muted-foreground/30" />
          <h3 className="text-lg font-medium">暂无持仓数据</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            录入真实交易记录后，这里将展示你的投资收益、持仓分析和优化建议。
          </p>
          <Link href="/portfolio" className="mt-4 inline-block">
            <Button className="h-10 rounded-xl">去录入持仓</Button>
          </Link>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Header */}
      <section className="mb-8">
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          投资复盘
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="mt-2 text-muted-foreground"
        >
          基于真实持仓数据的投资表现回顾
        </motion.p>
      </section>

      {/* Metrics cards */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="持仓市值"
          value={formatCurrency(totalValue, 0)}
          trend="neutral"
          subtitle={`${activeHoldings.length} 只基金`}
          icon={Briefcase}
          delay={0.1}
        />
        <MetricCard
          title="浮动盈亏"
          value={formatCurrency(totalProfit, 0)}
          trend={totalProfit >= 0 ? "up" : "down"}
          trendValue={formatPercent(totalProfitPct * 0.01)}
          subtitle="累计未实现"
          icon={TrendingUp}
          delay={0.15}
        />
        <MetricCard
          title="已平仓数量"
          value={`${soldHoldings.length} 笔`}
          trend="neutral"
          subtitle="历史交易记录"
          icon={Activity}
          delay={0.2}
        />
        <MetricCard
          title="持仓类型"
          value={`${Object.keys(typeMap).length} 种`}
          trend="neutral"
          subtitle="资产类别分布"
          icon={Target}
          delay={0.25}
        />
      </div>

      {/* Attribution + Chart */}
      <div className="mb-8 grid gap-6 lg:grid-cols-2">
        {/* Holdings breakdown */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-4">
            <h3 className="text-base font-semibold tracking-tight">持仓明细</h3>
            <p className="text-xs text-muted-foreground">各基金市值、成本与盈亏</p>
          </div>
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                  dy={8}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                  tickFormatter={(v) => `¥${(v / 10000).toFixed(0)}万`}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--background)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                  }}
                  itemStyle={{ fontSize: 13 }}
                  formatter={(value) => [formatCurrency(Number(value), 0), undefined]}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#0071e3"
                  fill="#0071e3"
                  fillOpacity={0.08}
                  strokeWidth={2}
                  dot={{ r: 3, fill: "#0071e3" }}
                  name="当前市值"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Type attribution */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-4">
            <h3 className="text-base font-semibold tracking-tight">资产类型分布</h3>
            <p className="text-xs text-muted-foreground">按基金类型的仓位与盈亏分析</p>
          </div>
          <div className="space-y-3">
            {attributionData.length > 0 ? (
              attributionData.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between rounded-xl border border-border p-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{item.name}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {item.count} 只
                      </Badge>
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>占比 {item.value}%</span>
                      <span
                        className={`font-medium ${
                          item.profit >= 0 ? "text-positive" : "text-negative"
                        }`}
                      >
                        {item.profit >= 0 ? "+" : ""}
                        {formatCurrency(item.profit, 0)}
                      </span>
                    </div>
                  </div>
                  {/* Mini progress bar */}
                  <div className="ml-3 h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-accent"
                      style={{ width: `${Math.min(100, item.value)}%` }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">暂无数据</p>
            )}
          </div>
        </motion.div>
      </div>

      {/* Trade history */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4, ease: [0.23, 1, 0.32, 1] }}
        className="mb-8 rounded-2xl border border-border bg-background p-2"
      >
        <div className="px-4 py-4">
          <h3 className="text-base font-semibold tracking-tight">交易记录</h3>
          <p className="text-xs text-muted-foreground">
            {allHoldings.length > 0
              ? `共 ${allHoldings.length} 笔交易（含 ${soldHoldings.length} 笔已平仓）`
              : "暂无交易记录"}
          </p>
        </div>
        {allHoldings.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">基金</th>
                  <th className="px-4 py-3 font-medium">买入日期</th>
                  <th className="px-4 py-3 font-medium">卖出日期</th>
                  <th className="px-4 py-3 text-right font-medium">成本</th>
                  <th className="px-4 py-3 text-right font-medium">市值/卖出金额</th>
                  <th className="px-4 py-3 text-right font-medium">盈亏</th>
                  <th className="px-4 py-3 text-center font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                {allHoldings.slice(0, 20).map((h, i) => {
                  const profit = h.is_sold
                    ? (h.sell_amount ?? 0) - (h.cost ?? 0)
                    : h.profit ?? 0;
                  const profitPct = h.is_sold
                    ? (h.cost ?? 0) > 0
                      ? ((h.sell_amount ?? 0) - (h.cost ?? 0)) / (h.cost ?? 1) * 100
                      : 0
                    : h.profit_pct ?? 0;
                  const displayValue = h.is_sold ? h.sell_amount : h.current_value;
                  return (
                    <tr
                      key={h.id}
                      className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium">{h.fund_name}</div>
                        <div className="text-xs text-muted-foreground">{h.fund_code}</div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{h.buy_date}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {h.is_sold ? h.sell_date : "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatCurrency(h.cost ?? 0, 0)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {displayValue != null ? formatCurrency(displayValue, 0) : "—"}
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums font-medium ${
                          profit >= 0 ? "text-positive" : "text-negative"
                        }`}
                      >
                        {profit >= 0 ? "+" : ""}
                        {formatCurrency(profit, 0)}
                        <div className="text-xs">
                          ({profit >= 0 ? "+" : ""}
                          {profitPct.toFixed(2)}%)
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {h.is_sold ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-negative/10 px-2.5 py-1 text-xs font-medium text-negative">
                            <ArrowDownRight className="h-3 w-3" />
                            已平仓
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-positive/10 px-2.5 py-1 text-xs font-medium text-positive">
                            <ArrowUpRight className="h-3 w-3" />
                            持有中
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-12 text-center text-sm text-muted-foreground">
            暂无交易记录，前往
            <Link href="/portfolio" className="mx-1 text-accent hover:underline">
              投资组合
            </Link>
            录入持仓
          </div>
        )}
      </motion.div>

      {/* Insights */}
      {insights.length > 0 && (
        <section>
          <motion.h2
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.45, ease: [0.23, 1, 0.32, 1] }}
            className="mb-4 text-lg font-semibold tracking-tight"
          >
            投资洞察
          </motion.h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {insights.map((item, index) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.5,
                  delay: 0.5 + index * 0.05,
                  ease: [0.23, 1, 0.32, 1],
                }}
                className="rounded-2xl border border-border bg-muted/40 p-5"
              >
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-xl bg-background">
                  <item.icon className="h-4 w-4 text-foreground" />
                </div>
                <h4 className="mb-1.5 font-semibold text-sm">{item.title}</h4>
                <p className="text-sm leading-relaxed text-muted-foreground">{item.content}</p>
              </motion.div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
