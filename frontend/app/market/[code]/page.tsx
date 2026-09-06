"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CalendarDays,
  Clock,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { DrawdownChart } from "@/components/drawdown-chart";
import { KLineChart } from "@/components/kline-chart";
import { MetricCard } from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DrawdownPoint,
  KlinePoint,
  NavPeriod,
  formatPercent,
  getMarketIndexKlineHistory,
  getMarketIndices,
  getMarketStatus,
} from "@/services/fund";

const PERIODS: { key: NavPeriod; label: string }[] = [
  { key: "日K", label: "日K" },
  { key: "周K", label: "周K" },
  { key: "月K", label: "月K" },
];

type ChartRange = "1M" | "3M" | "6M" | "1Y" | "3Y";

const RANGES: { key: ChartRange; label: string }[] = [
  { key: "1M", label: "1月" },
  { key: "3M", label: "3月" },
  { key: "6M", label: "6月" },
  { key: "1Y", label: "1年" },
  { key: "3Y", label: "3年" },
];

interface IndexProfile {
  code: string;
  name: string;
  category: string;
  market: string;
  publisher: string;
  riskLevel: "中低" | "中高";
  description: string;
}

const INDEX_PROFILES: Record<string, IndexProfile> = {
  sh000001: {
    code: "sh000001",
    name: "上证指数",
    category: "股票宽基指数",
    market: "上海证券交易所",
    publisher: "上交所",
    riskLevel: "中高",
    description: "反映上海证券交易所上市股票整体表现的综合指数。",
  },
  sz399001: {
    code: "sz399001",
    name: "深证成指",
    category: "股票宽基指数",
    market: "深圳证券交易所",
    publisher: "深交所",
    riskLevel: "中高",
    description: "反映深圳证券市场代表性上市公司整体表现的成份指数。",
  },
  sh000300: {
    code: "sh000300",
    name: "沪深300",
    category: "大盘宽基指数",
    market: "沪深市场",
    publisher: "中证指数",
    riskLevel: "中高",
    description: "由沪深市场规模大、流动性好的代表性证券组成的宽基指数。",
  },
  sz399006: {
    code: "sz399006",
    name: "创业板指",
    category: "成长宽基指数",
    market: "深圳证券交易所",
    publisher: "深交所",
    riskLevel: "中高",
    description: "反映创业板市场代表性成长企业整体表现的核心指数。",
  },
  sh000905: {
    code: "sh000905",
    name: "中证500",
    category: "中盘宽基指数",
    market: "沪深市场",
    publisher: "中证指数",
    riskLevel: "中高",
    description: "反映沪深市场中等市值上市公司整体表现的宽基指数。",
  },
  h11001: {
    code: "H11001",
    name: "中证全债",
    category: "债券宽基指数",
    market: "中国债券市场",
    publisher: "中证指数",
    riskLevel: "中低",
    description: "反映银行间和交易所债券市场整体价格变动趋势的债券指数。",
  },
};

export default function MarketIndexDetailPage() {
  const params = useParams();
  const rawCode = params?.code;
  const code = typeof rawCode === "string" ? rawCode.trim().toLowerCase() : "";
  const profile = INDEX_PROFILES[code];

  const [period, setPeriod] = useState<NavPeriod>("日K");
  const [chartRange, setChartRange] = useState<ChartRange>("1Y");

  const { data: indices = [], isLoading: indicesLoading } = useQuery({
    queryKey: ["marketIndices"],
    queryFn: getMarketIndices,
    staleTime: 2 * 60 * 1000,
  });

  const snapshot = indices.find((item) => (item.code ?? "").toLowerCase() === code);
  const isKnownIndex = Boolean(profile || snapshot);

  const { data: dailyData = [], isFetching: dailyFetching } = useQuery({
    queryKey: ["indexKline", code, "日K"],
    queryFn: () => getMarketIndexKlineHistory(profile?.code ?? code, "日K"),
    enabled: Boolean(code && isKnownIndex),
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });

  const { data: chartData = [], isFetching: chartFetching } = useQuery({
    queryKey: ["indexKline", code, period],
    queryFn: () => getMarketIndexKlineHistory(profile?.code ?? code, period),
    enabled: Boolean(code && isKnownIndex),
    staleTime: 5 * 60 * 1000,
    retry: 0,
    placeholderData: keepPreviousData,
  });

  const { data: marketStatus = null } = useQuery({
    queryKey: ["marketStatus"],
    queryFn: getMarketStatus,
    staleTime: 5 * 60 * 1000,
  });

  const analytics = useMemo(() => calculateAnalytics(dailyData), [dailyData]);
  const displayName = profile?.name ?? snapshot?.name ?? code;
  const latestValue = snapshot?.value ?? formatIndexValue(analytics.latest?.close);
  const dailyReturn = snapshot
    ? snapshot.change * 0.01
    : analytics.returns.daily;

  if (!code) {
    return <IndexNotFound message="缺少指数代码" />;
  }

  if (!indicesLoading && !isKnownIndex) {
    return <IndexNotFound message={`未找到指数 ${code}`} />;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
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

          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                {displayName}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="default" className="font-medium uppercase">
                  {profile?.code ?? code}
                </Badge>
                <span className="text-muted-foreground">
                  {profile?.category ?? "市场指数"}
                </span>
                <Badge variant={profile?.riskLevel === "中低" ? "positive" : "warning"}>
                  风险 {profile?.riskLevel ?? "中高"}
                </Badge>
              </div>
              {profile?.description && (
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  {profile.description}
                </p>
              )}
            </div>

            <div className="flex items-end gap-5 sm:text-right">
              <div>
                <div className="text-xs text-muted-foreground">最新点位</div>
                <div className="mt-1 text-2xl font-semibold tabular-nums">
                  {latestValue}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">日涨跌幅</div>
                <div
                  className={`mt-1 flex items-center gap-1 text-2xl font-semibold tabular-nums sm:justify-end ${
                    dailyReturn >= 0 ? "text-positive" : "text-negative"
                  }`}
                >
                  {dailyReturn >= 0 ? (
                    <TrendingUp className="h-5 w-5" />
                  ) : (
                    <TrendingDown className="h-5 w-5" />
                  )}
                  {formatOptionalPercent(dailyReturn)}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
        className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"
      >
        <MetaItem label="发布方" value={profile?.publisher ?? "公开市场"} />
        <MetaItem label="覆盖市场" value={profile?.market ?? "中国市场"} />
        <MetaItem label="行情频率" value="交易日更新" />
        <MetaItem
          label="最新交易日"
          value={analytics.latest?.date ?? marketStatus?.updateTime ?? "--"}
        />
      </motion.div>

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="近一年收益"
          value={formatOptionalPercent(analytics.returns.yearly)}
          trend={trendFor(analytics.returns.yearly)}
          subtitle="近 250 个交易日"
          icon={TrendingUp}
          delay={0.1}
        />
        <MetricCard
          title="最大回撤"
          value={formatOptionalPercent(analytics.maxDrawdown)}
          trend="down"
          subtitle="可用历史区间"
          icon={TrendingDown}
          delay={0.15}
        />
        <MetricCard
          title="年化波动率"
          value={formatOptionalPercent(analytics.volatility)}
          trend="neutral"
          subtitle="按日收益计算"
          icon={Activity}
          delay={0.2}
        />
        <MetricCard
          title="夏普比率"
          value={formatOptionalNumber(analytics.sharpe)}
          trend="neutral"
          subtitle="风险调整后收益"
          icon={Zap}
          delay={0.25}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.28, ease: [0.23, 1, 0.32, 1] }}
        className="mb-5 grid grid-cols-3 gap-3"
      >
        {[
          { label: "日收益", value: dailyReturn },
          { label: "周收益", value: analytics.returns.weekly },
          { label: "月收益", value: analytics.returns.monthly },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-border bg-background p-4">
            <div className="text-xs text-muted-foreground">{item.label}</div>
            <div
              className={`mt-1 text-xl font-semibold tabular-nums ${
                item.value >= 0 ? "text-positive" : "text-negative"
              }`}
            >
              {formatOptionalPercent(item.value)}
            </div>
          </div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.32, ease: [0.23, 1, 0.32, 1] }}
        className="mb-5 rounded-2xl border border-border bg-background p-4 sm:p-5"
      >
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-base font-semibold tracking-tight">
              {code === "h11001" ? "指数走势" : "指数 K 线走势"}
            </h2>
            <p className="text-xs text-muted-foreground">
              {code === "h11001"
                ? "收盘点位折线 · MA5 / MA10 / MA20"
                : "OHLC 蜡烛图 · 成交量 · MA5 / MA10 / MA20"}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-muted/40 p-1">
              {PERIODS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setPeriod(item.key)}
                  disabled={chartFetching}
                  className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                    period === item.key
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-muted/40 p-1">
              {RANGES.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setChartRange(item.key)}
                  disabled={chartFetching}
                  className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                    chartRange === item.key
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="h-[340px] w-full">
          {chartData.length > 0 ? (
            <KLineChart
              key={`${code}-${period}`}
              data={chartData}
              fundType="指数"
              chartMode={code === "h11001" ? "line" : "candlestick"}
              code={code}
              period={period}
              chartRange={chartRange}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              {chartFetching || dailyFetching ? "正在加载历史行情…" : "历史行情暂不可用"}
            </div>
          )}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          指数行情按交易日更新；周 K、月 K 由日线数据聚合生成。
        </p>
      </motion.div>

      <div className="mb-5 grid gap-4 lg:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h2 className="text-base font-semibold tracking-tight">历史回撤</h2>
            <p className="text-xs text-muted-foreground">相对历史高点的滚动回撤</p>
          </div>
          <div className="h-[260px]">
            {analytics.drawdown.length > 0 ? (
              <DrawdownChart data={analytics.drawdown} />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                暂无回撤数据
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
            <h2 className="text-base font-semibold tracking-tight">最新交易数据</h2>
            <p className="text-xs text-muted-foreground">最近一个交易日的行情明细</p>
          </div>
          <div className="divide-y divide-border">
            <DataRow label="开盘" value={formatIndexValue(analytics.latest?.open)} />
            <DataRow label="最高" value={formatIndexValue(analytics.latest?.high)} />
            <DataRow label="最低" value={formatIndexValue(analytics.latest?.low)} />
            <DataRow label="收盘" value={formatIndexValue(analytics.latest?.close)} />
            {code !== "h11001" && (
              <>
                <DataRow label="成交量" value={formatLargeNumber(analytics.latest?.volume)} />
                {analytics.latest?.turnover != null && (
                  <DataRow label="成交额" value={formatLargeNumber(analytics.latest.turnover)} />
                )}
              </>
            )}
          </div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.42, ease: [0.23, 1, 0.32, 1] }}
        className="flex flex-col gap-3 rounded-2xl border border-border bg-muted/40 p-4 text-sm sm:flex-row sm:items-center sm:justify-between sm:p-5"
      >
        <div className="flex items-start gap-3">
          <BarChart3 className="mt-0.5 h-4 w-4 text-muted-foreground" />
          <div>
            <div className="font-medium">数据说明</div>
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
              行情来自公开市场数据源；波动率、夏普比率和回撤由历史收盘价计算，仅供参考。
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {marketStatus ? (
            <>
              <Clock className="h-3.5 w-3.5" />
              {marketStatus.status} · {marketStatus.updateTime}
            </>
          ) : (
            <>
              <CalendarDays className="h-3.5 w-3.5" /> 交易日更新
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}

function calculateAnalytics(data: KlinePoint[]) {
  const points = [...data]
    .filter((point) => Number.isFinite(point.close) && point.close > 0)
    .sort((a, b) => a.date.localeCompare(b.date));
  const latest = points.at(-1);

  const periodReturn = (sessions: number): number => {
    if (points.length < 2) return Number.NaN;
    const startIndex = Math.max(0, points.length - 1 - sessions);
    const start = points[startIndex].close;
    return start > 0 && latest ? latest.close / start - 1 : Number.NaN;
  };

  const dailyReturns: number[] = [];
  let peak = 0;
  let maxDrawdown = 0;
  const drawdown: DrawdownPoint[] = [];

  points.forEach((point, index) => {
    peak = Math.max(peak, point.close);
    const currentDrawdown = peak > 0 ? point.close / peak - 1 : 0;
    maxDrawdown = Math.min(maxDrawdown, currentDrawdown);
    drawdown.push({ date: point.date, drawdown: currentDrawdown });

    if (index > 0 && points[index - 1].close > 0) {
      dailyReturns.push(point.close / points[index - 1].close - 1);
    }
  });

  const average = dailyReturns.length
    ? dailyReturns.reduce((sum, value) => sum + value, 0) / dailyReturns.length
    : Number.NaN;
  const variance = dailyReturns.length > 1
    ? dailyReturns.reduce((sum, value) => sum + (value - average) ** 2, 0) /
      (dailyReturns.length - 1)
    : Number.NaN;
  const volatility = Number.isFinite(variance) ? Math.sqrt(variance) * Math.sqrt(250) : Number.NaN;
  const annualizedReturn = Number.isFinite(average) ? average * 250 : Number.NaN;
  const sharpe = Number.isFinite(volatility) && volatility > 0
    ? (annualizedReturn - 0.02) / volatility
    : Number.NaN;

  return {
    latest,
    returns: {
      daily: periodReturn(1),
      weekly: periodReturn(5),
      monthly: periodReturn(22),
      yearly: periodReturn(250),
    },
    maxDrawdown: points.length ? maxDrawdown : Number.NaN,
    volatility,
    sharpe,
    drawdown,
  };
}

function trendFor(value: number): "up" | "down" | "neutral" {
  if (!Number.isFinite(value)) return "neutral";
  return value >= 0 ? "up" : "down";
}

function formatOptionalPercent(value: number): string {
  return Number.isFinite(value) ? formatPercent(value) : "--";
}

function formatOptionalNumber(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : "--";
}

function formatIndexValue(value: number | undefined): string {
  return value == null || !Number.isFinite(value)
    ? "--"
    : value.toLocaleString("zh-CN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
}

function formatLargeNumber(value: number | undefined): string {
  if (value == null || !Number.isFinite(value)) return "--";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)} 万`;
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium">{value}</div>
    </div>
  );
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}

function IndexNotFound({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-20 text-center sm:px-6">
      <AlertTriangle className="mx-auto h-12 w-12 text-warning" />
      <h1 className="mt-4 text-2xl font-semibold">{message}</h1>
      <p className="mt-2 text-muted-foreground">请返回首页重新选择市场指数。</p>
      <Link href="/" className="mt-6 inline-block">
        <Button className="h-12 rounded-2xl px-6">
          <ArrowLeft className="h-4 w-4" /> 返回首页
        </Button>
      </Link>
    </div>
  );
}
