"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DrawdownChart } from "@/components/drawdown-chart";
import { KLineChart } from "@/components/kline-chart";
import { Button } from "@/components/ui/button";
import {
  DataState,
  KeyValueList,
  MetricStrip,
  PlainConclusion,
  ResearchSection,
  SegmentedControl,
  SourceNote,
  UnderlineNav,
  toneFor,
} from "@/components/research-ui";
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
  description: string;
}

const INDEX_PROFILES: Record<string, IndexProfile> = {
  sh000001: { code: "sh000001", name: "上证指数", category: "股票宽基指数", market: "上海证券交易所", publisher: "上交所", description: "反映上海证券交易所上市股票整体表现的综合指数。" },
  sz399001: { code: "sz399001", name: "深证成指", category: "股票宽基指数", market: "深圳证券交易所", publisher: "深交所", description: "反映深圳证券市场代表性上市公司整体表现的成份指数。" },
  sh000300: { code: "sh000300", name: "沪深300", category: "大盘宽基指数", market: "沪深市场", publisher: "中证指数", description: "由沪深市场规模大、流动性好的代表性证券组成的宽基指数。" },
  sz399006: { code: "sz399006", name: "创业板指", category: "成长宽基指数", market: "深圳证券交易所", publisher: "深交所", description: "反映创业板市场代表性成长企业整体表现的核心指数。" },
  sh000905: { code: "sh000905", name: "中证500", category: "中盘宽基指数", market: "沪深市场", publisher: "中证指数", description: "反映沪深市场中等市值上市公司整体表现的宽基指数。" },
  h11001: { code: "H11001", name: "中证全债", category: "债券宽基指数", market: "中国债券市场", publisher: "中证指数", description: "反映银行间和交易所债券市场整体价格变动趋势的债券指数。" },
};

export default function MarketIndexDetailPage() {
  const params = useParams();
  const rawCode = params?.code;
  const code = typeof rawCode === "string" ? rawCode.trim().toLowerCase() : "";
  const profile = INDEX_PROFILES[code];
  const [period, setPeriod] = useState<NavPeriod>("日K");
  const [chartRange, setChartRange] = useState<ChartRange>("1Y");

  const { data: indices = [], isLoading: indicesLoading } = useQuery({
    queryKey: ["marketIndices"], queryFn: getMarketIndices, staleTime: 2 * 60 * 1000,
  });
  const snapshot = indices.find((item) => (item.code ?? "").toLowerCase() === code);
  const isKnownIndex = Boolean(profile || snapshot);

  const { data: dailyData = [], isFetching: dailyFetching, isError: dailyError } = useQuery({
    queryKey: ["indexKline", code, "日K"],
    queryFn: () => getMarketIndexKlineHistory(profile?.code ?? code, "日K"),
    enabled: Boolean(code && isKnownIndex), staleTime: 5 * 60 * 1000, retry: 0,
  });
  const { data: chartData = [], isFetching: chartFetching, isError: chartError } = useQuery({
    queryKey: ["indexKline", code, period],
    queryFn: () => getMarketIndexKlineHistory(profile?.code ?? code, period),
    enabled: Boolean(code && isKnownIndex), staleTime: 5 * 60 * 1000, retry: 0,
    placeholderData: keepPreviousData,
  });
  const { data: marketStatus = null } = useQuery({
    queryKey: ["marketStatus"], queryFn: getMarketStatus, staleTime: 5 * 60 * 1000,
  });

  const analytics = useMemo(() => calculateAnalytics(dailyData), [dailyData]);
  const displayName = profile?.name ?? snapshot?.name ?? code;
  const latestValue = snapshot?.value ?? formatIndexValue(analytics.latest?.close);
  const dailyReturn = snapshot ? snapshot.change * 0.01 : analytics.returns.daily;

  if (!code) return <IndexNotFound message="缺少指数代码" />;
  if (!indicesLoading && !isKnownIndex) return <IndexNotFound message={`未找到指数 ${code}`} />;

  const hasAnalytics = dailyData.length > 0;

  return (
    <div className="page-container">
      <Link href="/" className="mb-5 inline-flex min-h-11 items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> 返回首页
      </Link>
      <header className="border-t border-foreground pt-5">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{displayName}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{profile?.code ?? code} · {profile?.category ?? "市场指数"}</p>
            {profile?.description && <p className="mt-3 max-w-2xl text-sm text-muted-foreground">{profile.description}</p>}
          </div>
          <div className="flex items-end gap-6 md:text-right">
            <div><span className="block text-xs text-muted-foreground">最新点位</span><strong className="block text-4xl font-semibold leading-tight tabular-nums">{latestValue}</strong></div>
            <div><span className="block text-xs text-muted-foreground">日涨跌</span><strong className={`block text-2xl font-semibold tabular-nums ${!Number.isFinite(dailyReturn) ? "text-muted-foreground" : dailyReturn >= 0 ? "text-positive" : "text-negative"}`}>{formatOptionalPercent(dailyReturn)}</strong></div>
          </div>
        </div>
        <SourceNote>最新交易日：{analytics.latest?.date ?? marketStatus?.updateTime ?? "—"} · 来源：akshare 公开市场数据接口 · 交易日更新。</SourceNote>
      </header>

      <div className="mt-5">
        <PlainConclusion>
          {dailyError
            ? "历史行情暂时不可用，当前点位与涨跌缺少完整数据背景；页面不会使用替代行情。"
            : hasAnalytics
              ? `可用历史区间内，近一年收益为 ${formatOptionalPercent(analytics.returns.yearly)}，最大回撤为 ${formatOptionalPercent(analytics.maxDrawdown)}。两者分别描述区间变化和持有过程中的极端下跌。`
              : "正在等待历史行情。数据返回后，这里会同时说明区间收益与最大回撤。"}
        </PlainConclusion>
      </div>

      <MetricStrip items={[
        { label: "近一年收益", value: formatOptionalPercent(analytics.returns.yearly), note: "近 250 个交易日", tone: toneFor(analytics.returns.yearly) },
        { label: "最大回撤", value: formatOptionalPercent(analytics.maxDrawdown), note: "可用历史区间" },
        { label: "年化波动率", value: formatOptionalPercent(analytics.volatility), note: "按日收益计算" },
        { label: "夏普比率", value: formatOptionalNumber(analytics.sharpe), note: "风险调整后收益" },
      ]} />

      <UnderlineNav label="指数详情页内导航" items={[
        { href: "#index-overview", label: "概览" },
        { href: "#index-chart", label: "走势" },
        { href: "#index-risk", label: "回撤与交易数据" },
        { href: "#index-disclosure", label: "数据说明" },
      ]} />

      <ResearchSection id="index-overview" title="指数概览" description="多期收益与基本信息并列，避免只看单日涨跌。">
        <div className="grid gap-x-12 lg:grid-cols-2">
          <KeyValueList items={[
            { label: "发布方", value: profile?.publisher ?? "公开市场" },
            { label: "覆盖市场", value: profile?.market ?? "中国市场" },
            { label: "行情频率", value: "交易日更新" },
            { label: "最新交易日", value: analytics.latest?.date ?? marketStatus?.updateTime ?? "—" },
          ]} />
          <KeyValueList items={[
            { label: "日收益", value: formatOptionalPercent(dailyReturn) },
            { label: "周收益", note: "近 5 个交易日", value: formatOptionalPercent(analytics.returns.weekly) },
            { label: "月收益", note: "近 22 个交易日", value: formatOptionalPercent(analytics.returns.monthly) },
            { label: "近一年收益", note: "近 250 个交易日", value: formatOptionalPercent(analytics.returns.yearly) },
          ]} />
        </div>
      </ResearchSection>

      <ResearchSection id="index-chart" title={code === "h11001" ? "指数走势" : "指数 K 线走势"} description={code === "h11001" ? "收盘点位折线 · MA5 / MA10 / MA20" : "OHLC 蜡烛图 · 成交量 · MA5 / MA10 / MA20"}>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-between">
          <SegmentedControl label="指数 K 线周期" value={period} onChange={setPeriod} disabled={chartFetching} items={PERIODS.map((item) => ({ value: item.key, label: item.label }))} />
          <SegmentedControl label="指数图表范围" value={chartRange} onChange={setChartRange} disabled={chartFetching} items={RANGES.map((item) => ({ value: item.key, label: item.label }))} />
        </div>
        <div className="chart-frame">
          {chartData.length > 0 ? (
            <KLineChart key={`${code}-${period}`} data={chartData} fundType="指数" chartMode={code === "h11001" ? "line" : "candlestick"} code={code} period={period} chartRange={chartRange} />
          ) : (
            <DataState kind={chartError ? "error" : "loading"} title={chartError ? "历史行情暂不可用" : chartFetching || dailyFetching ? "正在加载历史行情" : "暂无历史行情"} description={chartError ? "请稍后重试，未使用替代行情。" : undefined} />
          )}
        </div>
        <SourceNote>指数行情按交易日更新；周 K、月 K 由日线数据聚合生成。</SourceNote>
      </ResearchSection>

      <ResearchSection id="index-risk" title="历史回撤" description="相对历史高点的滚动回撤；用于理解持有过程中的下跌幅度。">
        <div className="chart-frame h-[260px]">
          {analytics.drawdown.length > 0 ? <DrawdownChart data={analytics.drawdown} /> : <DataState kind="empty" title="暂无回撤数据" description="至少需要可用的历史收盘点位。" />}
        </div>
      </ResearchSection>

      <ResearchSection title="最新交易数据" description="最近一个交易日的行情明细；缺失数据显示为“—”。">
        <KeyValueList columns={2} items={[
          { label: "开盘", value: formatIndexValue(analytics.latest?.open) },
          { label: "最高", value: formatIndexValue(analytics.latest?.high) },
          { label: "最低", value: formatIndexValue(analytics.latest?.low) },
          { label: "收盘", value: formatIndexValue(analytics.latest?.close) },
          ...(code !== "h11001" ? [
            { label: "成交量", value: formatLargeNumber(analytics.latest?.volume) },
            { label: "成交额", value: formatLargeNumber(analytics.latest?.turnover) },
          ] : []),
        ]} />
      </ResearchSection>

      <ResearchSection id="index-disclosure" title="数据说明" description="指标由现有历史行情计算，计算口径不随页面设计改变。">
        <div className="disclosure">
          <p>行情来自公开市场数据源；波动率、夏普比率和回撤由历史收盘价计算，仅供参考。</p>
          <p>夏普比率沿用 2% 无风险利率和 250 个交易日年化口径；没有足够数据时显示“—”，不填充 0。</p>
          <p>{marketStatus ? `${marketStatus.status} · ${marketStatus.session} · ${marketStatus.updateTime}` : "市场状态暂不可用；指数仍按交易日更新。"}</p>
        </div>
      </ResearchSection>
    </div>
  );
}

function calculateAnalytics(data: KlinePoint[]) {
  const points = [...data].filter((point) => Number.isFinite(point.close) && point.close > 0).sort((a, b) => a.date.localeCompare(b.date));
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
    if (index > 0 && points[index - 1].close > 0) dailyReturns.push(point.close / points[index - 1].close - 1);
  });
  const average = dailyReturns.length ? dailyReturns.reduce((sum, value) => sum + value, 0) / dailyReturns.length : Number.NaN;
  const variance = dailyReturns.length > 1 ? dailyReturns.reduce((sum, value) => sum + (value - average) ** 2, 0) / (dailyReturns.length - 1) : Number.NaN;
  const volatility = Number.isFinite(variance) ? Math.sqrt(variance) * Math.sqrt(250) : Number.NaN;
  const annualizedReturn = Number.isFinite(average) ? average * 250 : Number.NaN;
  const sharpe = Number.isFinite(volatility) && volatility > 0 ? (annualizedReturn - 0.02) / volatility : Number.NaN;
  return { latest, returns: { daily: periodReturn(1), weekly: periodReturn(5), monthly: periodReturn(22), yearly: periodReturn(250) }, maxDrawdown: points.length ? maxDrawdown : Number.NaN, volatility, sharpe, drawdown };
}

function formatOptionalPercent(value: number): string {
  return Number.isFinite(value) ? formatPercent(value) : "—";
}
function formatOptionalNumber(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : "—";
}
function formatIndexValue(value: number | undefined): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function formatLargeNumber(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)} 万`;
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}
function IndexNotFound({ message }: { message: string }) {
  return <div className="page-container"><DataState kind="error" title={message} description="请返回首页重新选择市场指数。" action={<Link href="/"><Button><ArrowLeft className="h-4 w-4" /> 返回首页</Button></Link>} /></div>;
}
