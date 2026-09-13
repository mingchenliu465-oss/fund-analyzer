"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  ShieldAlert,
  Sparkles,
  Target,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  PortfolioHistoryPeriod,
  PortfolioInsights,
  getPortfolioInsights,
  formatCurrency,
} from "@/services/fund";

const periods: { key: PortfolioHistoryPeriod; label: string }[] = [
  { key: "1W", label: "1周" },
  { key: "1M", label: "1月" },
  { key: "3M", label: "3月" },
  { key: "1Y", label: "1年" },
  { key: "ALL", label: "全部" },
];

function signedCurrency(value: number) {
  return `${value >= 0 ? "+" : "−"}${formatCurrency(Math.abs(value), 2)}`;
}

function signedPercent(value: number | null) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function tone(value: number) {
  return value >= 0 ? "text-positive" : "text-negative";
}

export default function PortfolioInsightsPage() {
  const [period, setPeriod] = useState<PortfolioHistoryPeriod>("1M");
  const [data, setData] = useState<PortfolioInsights | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = () => {
    setLoading(true);
    setError(false);
    getPortfolioInsights(period)
      .then((result) => {
        setData(result);
        if (!result) setError(true);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let cancelled = false;
    getPortfolioInsights(period).then((result) => {
      if (cancelled) return;
      setData(result);
      setError(!result);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [period]);

  if (loading) {
    return <div className="mx-auto max-w-6xl px-6 py-24 text-center text-sm text-muted-foreground">正在整理你的组合数据…</div>;
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-6xl px-6 py-24 text-center">
        <AlertTriangle className="mx-auto h-10 w-10 text-muted-foreground/40" />
        <h1 className="mt-4 text-xl font-semibold">暂时无法生成组合洞察</h1>
        <p className="mt-2 text-sm text-muted-foreground">请确认后端服务已启动，或稍后再试。</p>
        <Button onClick={load} variant="outline" className="mt-5 h-9 rounded-xl">重新加载</Button>
      </div>
    );
  }

  const { headline, return_explanation: explanation, risk, market_comparison: markets, history } = data;
  const hasHoldings = explanation.contributions.length > 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <section className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-accent"><Sparkles className="h-4 w-4" />组合洞察</div>
          <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">我的组合今天发生了什么？</motion.h1>
          <p className="mt-2 text-muted-foreground">把收益、风险和市场表现放在一起看。</p>
        </div>
        <div className="flex gap-1 rounded-xl border border-border bg-muted/40 p-1">
          {periods.map(({ key, label }) => (
            <button key={key} onClick={() => setPeriod(key)} className={`rounded-lg px-3 py-1.5 text-xs font-medium ${period === key ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}>{label}</button>
          ))}
        </div>
      </section>

      {!hasHoldings ? (
        <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-16 text-center">
          <Target className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <h2 className="mt-4 text-lg font-semibold">还没有组合数据</h2>
          <p className="mt-2 text-sm text-muted-foreground">录入真实持仓后，这里会解释每天的收益来源和风险。</p>
          <Link href="/portfolio" className="mt-5 inline-block"><Button className="h-9 rounded-xl">去录入持仓</Button></Link>
        </div>
      ) : (
        <>
          <section className="mb-6 rounded-2xl border border-accent/20 bg-accent/5 p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div><div className="text-xs text-muted-foreground">今日结论</div><div className="mt-1 text-xl font-semibold leading-relaxed">{headline.sentence}</div></div>
              <div className="grid grid-cols-2 gap-3 sm:min-w-[260px]">
                <div className="rounded-xl border border-border bg-background/70 p-3"><div className="text-xs text-muted-foreground">今日收益</div><div className={`mt-1 text-lg font-semibold tabular-nums ${tone(headline.today_return)}`}>{signedCurrency(headline.today_return)}</div></div>
                <div className="rounded-xl border border-border bg-background/70 p-3"><div className="text-xs text-muted-foreground">今日收益率</div><div className={`mt-1 text-lg font-semibold tabular-nums ${tone(headline.today_return_pct)}`}>{signedPercent(headline.today_return_pct)}</div></div>
              </div>
            </div>
            {data.data_status === "partial" && <p className="mt-4 border-t border-accent/10 pt-3 text-xs text-amber-700 dark:text-amber-300">部分基金行情待更新，当前解释可能不完整。</p>}
          </section>

          <div className="mb-6 grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border border-border bg-background p-4 sm:p-5">
              <div className="mb-4 flex items-start justify-between"><div><h2 className="font-semibold">今天的收益来自哪里</h2><p className="mt-1 text-xs text-muted-foreground">按基金贡献排序，正数是帮忙，负数是拖累</p></div><Activity className="h-5 w-5 text-muted-foreground" /></div>
              <div className="space-y-2">
                {explanation.contributions.map((item) => (
                  <div key={item.fund_code} className="flex items-center justify-between rounded-xl border border-border px-3 py-2.5">
                    <div className="min-w-0"><div className="truncate text-sm font-medium">{item.fund_name}</div><div className="text-xs text-muted-foreground">{item.fund_code} · 涨跌 {signedPercent(item.change_pct)}</div></div>
                    <div className={`ml-3 text-right text-sm font-semibold tabular-nums ${tone(item.contribution)}`}>{item.nav_stale ? "待更新" : signedCurrency(item.contribution)}<div className="text-xs font-normal text-muted-foreground">贡献占比 {Math.abs(item.contribution_rate * 100).toFixed(1)}%</div></div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-2xl border border-border bg-background p-4 sm:p-5">
              <div className="mb-4 flex items-start justify-between"><div><h2 className="font-semibold">我的组合有什么风险</h2><p className="mt-1 text-xs text-muted-foreground">基于当前持仓市值计算</p></div><ShieldAlert className="h-5 w-5 text-muted-foreground" /></div>
              <div className="mb-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-muted/40 p-3"><div className="text-xs text-muted-foreground">集中度</div><div className="mt-1 text-xl font-semibold">{risk.concentration_level}</div><div className="mt-1 text-xs text-muted-foreground">HHI {risk.hhi.toFixed(0)}</div></div>
                <div className="rounded-xl bg-muted/40 p-3"><div className="text-xs text-muted-foreground">最大持仓</div><div className="mt-1 truncate text-sm font-semibold">{risk.max_holding.fund_name ?? "—"}</div><div className="mt-1 text-xs text-muted-foreground">占比 {risk.max_holding.weight_pct.toFixed(1)}%</div></div>
              </div>
              <div className="space-y-2.5">
                {risk.allocation.map((item) => <div key={item.category}><div className="mb-1 flex justify-between text-xs"><span>{item.category}</span><span className="tabular-nums">{item.weight_pct.toFixed(1)}%</span></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, item.weight_pct)}%` }} /></div></div>)}
              </div>
              {risk.notes.length > 0 && <div className="mt-4 space-y-1 text-xs text-muted-foreground">{risk.notes.map((note) => <p key={note}>· {note}</p>)}</div>}
              <div className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">基金底层重叠：{risk.overlap_status === "available" ? `${risk.overlap_pairs.length} 组存在明显重叠` : "暂无足够真实季报数据，暂不判断"}</div>
            </section>
          </div>

          <div className="mb-6 grid gap-6 lg:grid-cols-[1.15fr_.85fr]">
            <section className="rounded-2xl border border-border bg-background p-4 sm:p-5">
              <div className="mb-4 flex items-start justify-between"><div><h2 className="font-semibold">最近组合变化</h2><p className="mt-1 text-xs text-muted-foreground">{history.note}</p></div><BarChart3 className="h-5 w-5 text-muted-foreground" /></div>
              {history.points.length >= 2 ? <div className="h-[220px]"><ResponsiveContainer width="100%" height="100%"><AreaChart data={history.points} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}><defs><linearGradient id="insights-value" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#0071e3" stopOpacity={0.2} /><stop offset="95%" stopColor="#0071e3" stopOpacity={0} /></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" /><XAxis dataKey="date" tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} /><YAxis tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(value) => `¥${Number(value).toLocaleString()}`} /><Tooltip formatter={(value) => [formatCurrency(Number(value), 2), "总资产"]} /><Area type="monotone" dataKey="total_value" stroke="#0071e3" fill="url(#insights-value)" strokeWidth={2} dot={false} /></AreaChart></ResponsiveContainer></div> : <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">历史快照还不够，继续使用组合页后这里会逐渐形成趋势。</div>}
              <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground"><span>趋势：{history.trend}</span>{history.anomaly_detected && <span className="text-amber-700 dark:text-amber-300">{history.anomaly_date} 出现异常波动</span>}</div>
            </section>

            <section className="rounded-2xl border border-border bg-background p-4 sm:p-5">
              <div className="mb-4 flex items-start justify-between"><div><h2 className="font-semibold">相对市场表现</h2><p className="mt-1 text-xs text-muted-foreground">区间：{period}</p></div><ArrowUpRight className="h-5 w-5 text-muted-foreground" /></div>
              <div className="space-y-2">{markets.map((market) => <div key={market.code} className="flex items-center justify-between rounded-xl border border-border px-3 py-2.5"><div><div className="text-sm font-medium">{market.name}</div><div className="text-xs text-muted-foreground">组合 {signedPercent(market.portfolio_return_pct)} · 指数 {signedPercent(market.index_return_pct)}</div></div><div className={`text-right text-sm font-semibold ${market.available ? tone(market.relative_return_pct ?? 0) : "text-muted-foreground"}`}>{market.available ? `相对 ${signedPercent(market.relative_return_pct)}` : "数据不足"}</div></div>)}</div>
            </section>
          </div>

          <section className="rounded-2xl border border-border bg-muted/30 p-4 sm:p-5">
            <div className="flex items-center justify-between gap-2"><div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-accent" /><h2 className="font-semibold">每日复盘基础</h2><Badge variant="outline" className="text-[10px]">规则分析</Badge></div><Link href="/review" className="text-xs font-medium text-accent hover:underline">查看完整复盘 →</Link></div>
            <p className="mt-1 text-xs text-muted-foreground">当前使用真实持仓、净值和快照生成，暂未接入大模型。</p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{data.review_context.map((fact) => <div key={fact.key} className="rounded-xl border border-border bg-background px-3 py-2.5"><div className="text-xs text-muted-foreground">{fact.label}</div><div className="mt-1 text-sm font-medium">{fact.value}</div></div>)}</div>
          </section>
          <p className="mt-4 text-xs text-muted-foreground">数据说明：场外基金通常为 T-1 净值；历史资产变化未扣除期间现金流；底层重叠仅在真实季报数据可用时判断。</p>
        </>
      )}
    </div>
  );
}
