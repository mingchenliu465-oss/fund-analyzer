"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Calendar,
  Percent,
  Search,
  Star,
  TrendingDown,
  TrendingUp,
  User,
  Zap,
} from "lucide-react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { RiskScore } from "@/components/risk-score";
import { KLineChart } from "@/components/kline-chart";
import { DrawdownChart } from "@/components/drawdown-chart";
import { RiskIndicatorTable } from "@/components/risk-indicator-table";
import { TopHoldingsTable } from "@/components/top-holdings-table";
import { PeerComparison } from "@/components/peer-comparison";
import {
  DrawdownPoint,
  FundDetail,
  KlinePoint,
  NavPeriod,
  PeerComparison as PeerComparisonType,
  ReturnRanking,
  formatCurrency,
  formatPercent,
  formatRatio,
  getFundDetail,
  getFundDrawdownHistory,
  getFundKlineHistory,
  getPeerComparison,
  getReturnRanking,
  searchFunds,
} from "@/services/fund";

const PERIODS: { key: NavPeriod; label: string }[] = [
  { key: "5D", label: "5日" },
  { key: "10D", label: "10日" },
  { key: "20D", label: "20日" },
  { key: "日K", label: "日K" },
  { key: "周K", label: "周K" },
  { key: "月K", label: "月K" },
  { key: "年K", label: "年K" },
];

export default function FundDetailPage() {
  const params = useParams();
  const rawId = params?.id;
  const code = typeof rawId === "string" ? rawId.toUpperCase() : "";

  const [fund, setFund] = useState<FundDetail | null | undefined>(undefined);
  const [klineData, setKlineData] = useState<KlinePoint[]>([]);
  const [drawdownData, setDrawdownData] = useState<DrawdownPoint[]>([]);
  const [peers, setPeers] = useState<PeerComparisonType[]>([]);
  const [ranking, setRanking] = useState<ReturnRanking | null>(null);
  const [period, setPeriod] = useState<NavPeriod>("日K");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<{ code: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    Promise.all([
      getFundDetail(code),
      getFundKlineHistory(code, period),
      getFundDrawdownHistory(code, period),
      getPeerComparison(code),
      getReturnRanking(code),
    ])
      .then(([detail, kline, drawdown, peerData, rankData]) => {
        setFund(detail);
        setKlineData(kline);
        setDrawdownData(drawdown);
        setPeers(peerData);
        setRanking(rankData);
      })
      .finally(() => setLoading(false));
  }, [code]);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    Promise.all([getFundKlineHistory(code, period), getFundDrawdownHistory(code, period)])
      .then(([kline, drawdown]) => {
        setKlineData(kline);
        setDrawdownData(drawdown);
      })
      .finally(() => setLoading(false));
  }, [period, code]);

  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => {
      searchFunds(query).then((results) => {
        setSuggestions(results.slice(0, 6).map((f) => ({ code: f.code, name: f.name })));
      });
    }, 200);
    return () => clearTimeout(timer);
  }, [query]);

  if (!code) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20 text-center sm:px-6">
        <h1 className="text-2xl font-semibold">缺少基金代码</h1>
        <p className="mt-2 text-muted-foreground">请在 URL 中输入基金代码，例如 /fund/000300。</p>
        <Link href="/" className="mt-6 inline-block">
          <Button className="h-12 rounded-2xl bg-foreground px-6 text-background hover:bg-foreground/90">
            <ArrowLeft className="mr-2 h-4 w-4" /> 返回首页
          </Button>
        </Link>
      </div>
    );
  }

  if (fund === null) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20 text-center sm:px-6">
        <AlertTriangle className="mx-auto h-12 w-12 text-warning" />
        <h1 className="mt-4 text-2xl font-semibold">未找到基金 {code}</h1>
        <p className="mt-2 text-muted-foreground">请检查基金代码是否正确，或返回首页搜索。当前展示的是模拟数据。</p>
        <Link href="/" className="mt-6 inline-block">
          <Button className="h-12 rounded-2xl bg-foreground px-6 text-background hover:bg-foreground/90">
            <ArrowLeft className="mr-2 h-4 w-4" /> 返回首页
          </Button>
        </Link>
      </div>
    );
  }

  if (!fund) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20 text-center text-muted-foreground sm:px-6">
        加载中…
      </div>
    );
  }

  const isUp = fund.changePct >= 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Header */}
      <section className="mb-6">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
        >
          <Link
            href="/"
            className="mb-3 inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-1 h-4 w-4" /> 返回首页
          </Link>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{fund.name}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="default" className="font-medium">{fund.code}</Badge>
                <span className="text-muted-foreground">{fund.type}</span>
                <span className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">{fund.company}</span>
                <span className="text-muted-foreground">·</span>
                <Badge variant={getRiskBadgeVariant(fund.metrics.riskScore)}>
                  风险 {fund.metrics.riskLevel}
                </Badge>
                <Badge variant="outline" className="inline-flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {fund.manager}
                </Badge>
                <Badge variant="outline" className="inline-flex items-center gap-1">
                  <Star className="h-3 w-3 fill-warning text-warning" />
                  {fund.rating} 星
                </Badge>
                {fund.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-4 text-right">
              <div>
                <div className="text-xs text-muted-foreground">最新净值</div>
                <div className="text-2xl font-semibold tabular-nums">{formatCurrency(fund.nav, 4)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">日涨跌幅</div>
                <div
                  className={`flex items-center justify-end gap-1 text-2xl font-semibold tabular-nums ${
                    isUp ? "text-positive" : "text-negative"
                  }`}
                >
                  {isUp ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
                  {formatPercent(fund.changePct * 0.01)}
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Inline search */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="relative mt-4 max-w-xl"
        >
          <div className="relative">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索基金代码 / 名称切换"
              className="h-11 rounded-2xl border-border bg-background pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
            />
          </div>
          {suggestions.length > 0 && (
            <div className="absolute z-20 mt-2 w-full rounded-2xl border border-border bg-background p-2 shadow-lg">
              {suggestions.map((s) => (
                <Link
                  key={s.code}
                  href={`/fund/${s.code}`}
                  onClick={() => {
                    setQuery("");
                    setSuggestions([]);
                  }}
                  className="flex items-center justify-between rounded-xl px-3 py-2.5 text-sm hover:bg-muted"
                >
                  <span className="font-medium">{s.name}</span>
                  <span className="text-muted-foreground">{s.code}</span>
                </Link>
              ))}
            </div>
          )}
        </motion.div>
      </section>

      {/* Meta info */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.08, ease: [0.23, 1, 0.32, 1] }}
        className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"
      >
        <MetaItem label="基金规模" value={fund.size} />
        <MetaItem label="成立时间" value={fund.inceptionDate} />
        <MetaItem label="投资风格" value={fund.investmentStyle} />
        <MetaItem label="基金经理" value={fund.manager} />
      </motion.div>

      {/* Return metric cards */}
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="近一年收益"
          value={formatPercent(fund.returns.yearly)}
          trend={fund.returns.yearly >= 0 ? "up" : "down"}
          trendValue={fund.returns.yearly >= 0 ? "跑赢基准" : "短期承压"}
          subtitle="近12个月"
          icon={TrendingUp}
          delay={0.1}
        />
        <MetricCard
          title="最大回撤"
          value={formatPercent(fund.metrics.maxDrawdown)}
          trend="down"
          trendValue="历史极端情况"
          subtitle="成立以来"
          icon={TrendingDown}
          delay={0.15}
        />
        <MetricCard
          title="夏普比率"
          value={formatRatio(fund.metrics.sharpe)}
          trend="neutral"
          subtitle="风险调整后收益"
          icon={Zap}
          delay={0.2}
        />
        <MetricCard
          title="波动率"
          value={formatPercent(fund.metrics.volatility)}
          trend="neutral"
          subtitle="年度波动幅度"
          icon={Percent}
          delay={0.25}
        />
      </div>

      {/* Return breakdown + ranking */}
      <div className="mb-5 grid gap-4 lg:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.28, ease: [0.23, 1, 0.32, 1] }}
          className="grid grid-cols-3 gap-3 lg:col-span-3"
        >
          {[
            { label: "日收益", value: fund.returns.daily },
            { label: "周收益", value: fund.returns.weekly },
            { label: "月收益", value: fund.returns.monthly },
          ].map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-border bg-background p-4"
            >
              <div className="text-xs text-muted-foreground">{item.label}</div>
              <div
                className={`mt-1 text-xl font-semibold tabular-nums ${
                  item.value >= 0 ? "text-positive" : "text-negative"
                }`}
              >
                {formatPercent(item.value)}
              </div>
            </div>
          ))}
        </motion.div>

        {ranking && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3, ease: [0.23, 1, 0.32, 1] }}
            className="flex flex-col justify-center rounded-2xl border border-border bg-background p-4"
          >
            <div className="text-xs text-muted-foreground">收益排名</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">
              #{ranking.rank}
              <span className="text-sm font-normal text-muted-foreground">
                {" "}
                / {ranking.total}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">前 {ranking.percentile}%（近一年收益）</div>
          </motion.div>
        )}
      </div>

      {/* K-line chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.32, ease: [0.23, 1, 0.32, 1] }}
        className="mb-5 rounded-2xl border border-border bg-background p-4 sm:p-5"
      >
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-semibold tracking-tight">净值走势（K线）</h3>
            <p className="text-xs text-muted-foreground">红涨绿跌 · 悬停查看 OHLC</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                onClick={() => setPeriod(p.key)}
                disabled={loading}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  period === p.key
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="h-[320px] w-full">
          {klineData.length > 0 ? (
            <KLineChart data={klineData} fundType={fund.type} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              暂无数据
            </div>
          )}
        </div>
      </motion.div>

      {/* Drawdown + Risk indicators */}
      <div className="mb-5 grid gap-4 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h3 className="text-base font-semibold tracking-tight">历史最大回撤</h3>
            <p className="text-xs text-muted-foreground">基于选定周期计算的滚动回撤</p>
          </div>
          <div className="h-[260px]">
            {drawdownData.length > 0 ? (
              <DrawdownChart data={drawdownData} />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                暂无数据
              </div>
            )}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.38, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h3 className="text-base font-semibold tracking-tight">风险指标</h3>
            <p className="text-xs text-muted-foreground">综合评估基金风险收益特征</p>
          </div>
          <RiskIndicatorTable metrics={fund.metrics} />
        </motion.div>
      </div>

      {/* Sector + Holdings */}
      <div className="mb-5 grid gap-4 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.41, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h3 className="text-base font-semibold tracking-tight">行业分布</h3>
            <p className="text-xs text-muted-foreground">按行业/资产类别划分的持仓占比</p>
          </div>
          <div className="h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={fund.sectors}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="weight"
                  strokeWidth={0}
                >
                  {fund.sectors.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--background)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                  }}
                  itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
                  formatter={(value, name) => [`${value}%`, name]}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  iconType="circle"
                  formatter={(value: string) => (
                    <span className="text-xs text-muted-foreground">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {fund.sectors.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between rounded-lg border border-border p-2"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs">{item.name}</span>
                </div>
                <span className="text-xs font-medium tabular-nums">{item.weight}%</span>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.44, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h3 className="text-base font-semibold tracking-tight">重仓方向</h3>
            <p className="text-xs text-muted-foreground">前五大持仓 / 资产方向</p>
          </div>
          <TopHoldingsTable holdings={fund.topHoldings} />
        </motion.div>
      </div>

      {/* Peer comparison */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.47, ease: [0.23, 1, 0.32, 1] }}
        className="mb-5 rounded-2xl border border-border bg-background p-4 sm:p-5"
      >
        <div className="mb-3">
          <h3 className="text-base font-semibold tracking-tight">同类基金对比</h3>
          <p className="text-xs text-muted-foreground">与相同类型基金的近一年收益、风险指标对比</p>
        </div>
        <PeerComparison data={peers} targetCode={fund.code} />
      </motion.div>

      {/* CTA */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.5, ease: [0.23, 1, 0.32, 1] }}
        className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-border bg-muted/40 p-4 sm:flex-row sm:items-center sm:p-5"
      >
        <div>
          <h4 className="text-base font-semibold">想对比多只基金？</h4>
          <p className="text-xs text-muted-foreground">将 {fund.name} 加入对比，看看它在同类中的表现。</p>
        </div>
        <Link href="/compare">
          <Button className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:bg-foreground/90">
            去对比
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </Link>
      </motion.div>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium">{value}</div>
    </div>
  );
}

function getRiskBadgeVariant(score: number): "positive" | "warning" | "negative" | "default" {
  if (score < 30) return "positive";
  if (score < 60) return "warning";
  if (score < 80) return "default";
  return "negative";
}
