"use client";

import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { KLineChart } from "@/components/kline-chart";
import { DrawdownChart } from "@/components/drawdown-chart";
import { RiskIndicatorTable } from "@/components/risk-indicator-table";
import { TopHoldingsTable } from "@/components/top-holdings-table";
import { PeerComparison } from "@/components/peer-comparison";
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
  HoldStructure,
  NavPeriod,
  formatCurrency,
  formatPercent,
  formatRatio,
  getFundDetail,
  getFundDrawdownHistory,
  getFundKlineHistory,
  getFundStatisticsAudit,
  getHoldStructure,
  getPeerComparison,
  getReturnRanking,
  recordBrowsedFund,
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

export default function FundDetailPage() {
  const params = useParams();
  const rawId = params?.id;
  const code = typeof rawId === "string" ? rawId.toUpperCase() : "";
  const [period, setPeriod] = useState<NavPeriod>("日K");
  const [chartRange, setChartRange] = useState<ChartRange>("1Y");
  const [analysisEnabled, setAnalysisEnabled] = useState(false);

  const { data: fund, isLoading: fundLoading, isError: fundError } = useQuery({
    queryKey: ["fundDetail", code],
    queryFn: () => getFundDetail(code),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });

  useEffect(() => {
    if (fund) recordBrowsedFund(fund);
  }, [fund]);

  const { data: klineData = [], isFetching: klineFetching, isError: klineError } = useQuery({
    queryKey: ["kline", code, period],
    queryFn: () => getFundKlineHistory(code, period),
    enabled: !!fund && fund.code === code,
    staleTime: 5 * 60 * 1000,
    retry: 0,
    placeholderData: keepPreviousData,
  });

  const { data: drawdownData = [], isFetching: drawdownFetching } = useQuery({
    queryKey: ["drawdown", code, period],
    queryFn: () => getFundDrawdownHistory(code, period),
    enabled: analysisEnabled && !!code,
    staleTime: 5 * 60 * 1000,
    retry: 0,
    placeholderData: keepPreviousData,
  });

  const { data: statisticsAudit = null } = useQuery({
    queryKey: ["statisticsAudit", code, period],
    queryFn: () => getFundStatisticsAudit(code, period),
    enabled: analysisEnabled && !!code,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });

  const { data: peers = [] } = useQuery({
    queryKey: ["peers", code],
    queryFn: () => getPeerComparison(code),
    enabled: analysisEnabled && !!code,
    staleTime: 30 * 60 * 1000,
    retry: 0,
  });

  const { data: ranking = null } = useQuery({
    queryKey: ["ranking", code],
    queryFn: () => getReturnRanking(code),
    enabled: analysisEnabled && !!code,
    staleTime: 30 * 60 * 1000,
    retry: 0,
  });

  const { data: holdStructure = null } = useQuery<HoldStructure | null>({
    queryKey: ["holdStructure"],
    queryFn: getHoldStructure,
    enabled: analysisEnabled && !!code,
    staleTime: 2 * 60 * 60 * 1000,
    retry: 0,
  });

  if (!code) {
    return (
      <div className="page-container">
        <DataState kind="error" title="缺少基金代码" description="请在地址中输入基金代码，例如 /fund/000300。" action={<Link href="/fund"><Button>返回基金列表</Button></Link>} />
      </div>
    );
  }

  if (!fund && (fundError || fund === null)) {
    return (
      <div className="page-container">
        <DataState kind="error" title={`基金 ${code} 的详情暂时不可用`} description="接口未能返回基金资料，请稍后重试或返回列表重新搜索；未使用替代数据。" action={<Link href="/fund"><Button>返回基金列表</Button></Link>} />
      </div>
    );
  }

  if (!fund || fundLoading) {
    return <div className="page-container"><DataState kind="loading" title="正在加载基金详情" description="先读取最新净值和基本资料，历史图表随后加载。" /></div>;
  }

  const changePct = fund.changePct;
  const hasChange = changePct != null;
  const latestDrawdown = drawdownData.length ? drawdownData[drawdownData.length - 1].drawdown : fund.metrics.maxDrawdown;
  const recoveryStatus = latestDrawdown >= -0.005 ? "已修复" : latestDrawdown > fund.metrics.maxDrawdown + 0.01 ? "正在修复中" : "回撤中";
  const conclusion = fund.metrics.maxDrawdown <= -0.2
    ? "历史最大回撤超过 20%，持有过程中出现过明显下跌。除了收益，还需要重点看回撤和波动。"
    : fund.metrics.maxDrawdown <= -0.1
      ? "历史最大回撤在 10%—20% 之间。收益需要与这段波动放在一起看，不能只看涨幅。"
      : "历史最大回撤相对温和，但历史表现不代表未来，仍需结合收益和数据区间判断。";

  const returnRows = [
    { label: "日收益", value: fund.returns.daily, note: "最近一个净值观测周期" },
    { label: "周收益", value: fund.returns.weekly, note: "近一周" },
    { label: "月收益", value: fund.returns.monthly, note: "近一月" },
    { label: "近一年收益", value: fund.returns.yearly, note: "近 12 个月" },
  ];

  return (
    <div className="page-container">
      <Link href="/fund" className="mb-5 inline-flex min-h-11 items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> 返回基金列表
      </Link>

      <header className="border-t border-foreground pt-5">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{fund.name}</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {fund.code} · {fund.type} · {fund.company} · 基金经理 {fund.manager || "—"}
            </p>
            {fund.tags.length > 0 && <p className="mt-1 text-xs text-muted-foreground">{fund.tags.join(" / ")}</p>}
          </div>
          <div className="flex items-end gap-6 md:text-right">
            <div>
              <span className="block text-xs text-muted-foreground">最新净值</span>
              <strong className="block text-4xl font-semibold leading-tight tabular-nums">{formatCurrency(fund.nav, 4)}</strong>
            </div>
            <div>
              <span className="block text-xs text-muted-foreground">日涨跌</span>
              <strong className={`block text-2xl font-semibold tabular-nums ${!hasChange ? "text-muted-foreground" : changePct >= 0 ? "text-positive" : "text-negative"}`}>
                {hasChange ? formatPercent(changePct * 0.01) : "—"}
              </strong>
            </div>
          </div>
        </div>
        <SourceNote>
          数据日期：{fund.navDate ?? "未提供"} · 数据状态：{fund.navStatus ?? "未知"} · 来源：akshare 公开接口。场外基金通常为 T-1 净值。
        </SourceNote>
      </header>

      <div className="mt-5">
        <PlainConclusion>{conclusion}</PlainConclusion>
      </div>

      <MetricStrip items={[
        { label: "近一年收益", value: formatPercent(fund.returns.yearly), note: "近 12 个月", tone: toneFor(fund.returns.yearly) },
        { label: "最大回撤", value: formatPercent(fund.metrics.maxDrawdown), note: "历史极端情况", tone: "neutral" },
        { label: "年化波动率", value: formatPercent(fund.metrics.volatility), note: "按历史收益计算" },
        { label: "夏普比率", value: formatRatio(fund.metrics.sharpe), note: "风险调整后收益" },
        { label: "基金规模", value: fund.size || "—", note: fund.inceptionDate ? `成立于 ${fund.inceptionDate}` : "成立日期未提供" },
      ]} />

      <UnderlineNav label="基金详情页内导航" items={[
        { href: "#overview", label: "概览" },
        { href: "#performance", label: "走势与回撤" },
        { href: "#holdings", label: "持仓与同类" },
        { href: "#disclosure", label: "数据说明" },
      ]} />

      <ResearchSection id="overview" title="基金概览" description="先解释指标含义，再看数值；没有来源的数据不做估算。">
        <div className="grid gap-x-12 lg:grid-cols-2">
          <KeyValueList items={[
            { label: "基金类型", value: fund.type || "—" },
            { label: "成立时间", value: fund.inceptionDate || "—" },
            { label: "基金经理", value: typeof fund.managerDays === "number" ? `${fund.manager} · 从业 ${fund.managerDays.toLocaleString()} 天` : fund.manager || "—", note: "任职天数未提供时不按成立日期估算" },
            { label: "投资风格", value: fund.investmentStyle ?? "—" },
            { label: "基金评级", value: fund.rating == null ? "—" : `${fund.rating} 星` },
            { label: "回撤修复", value: recoveryStatus, note: "根据最新净值相对历史高点判断" },
          ]} />
          <div>
            <h3 className="mb-2 text-sm font-semibold">多期收益</h3>
            <KeyValueList items={returnRows.map((item) => ({
              label: item.label,
              note: item.note,
              value: <span className={item.value == null ? "text-muted-foreground" : item.value >= 0 ? "text-positive" : "text-negative"}>{formatPercent(item.value)}</span>,
            }))} />
          </div>
        </div>
        {ranking && ranking.rank > 0 && (
          <div className="mt-6 border-t border-border pt-4">
            <span className="text-xs text-muted-foreground">近一年同类收益排名</span>
            <div className="mt-1 text-2xl font-semibold tabular-nums">{ranking.rank} <span className="text-sm text-muted-foreground">｜ {ranking.total}</span></div>
            <p className="text-xs text-muted-foreground">位于前 {ranking.percentile ?? "—"}%；名次越小，历史区间收益排名越靠前。</p>
          </div>
        )}
      </ResearchSection>

      <ResearchSection id="performance" title={fund.type === "ETF" ? "K 线走势" : "净值走势"} description={fund.type === "ETF" ? "红涨绿跌 · OHLC 蜡烛图 · 成交量与均线" : "净值折线 · 日/周/月度净值点 · 交易日盘后更新"}>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-between">
          <SegmentedControl label="K 线周期" value={period} onChange={setPeriod} disabled={klineFetching} items={PERIODS.map((item) => ({ value: item.key, label: item.label }))} />
          <SegmentedControl label="图表时间范围" value={chartRange} onChange={setChartRange} disabled={klineFetching} items={RANGES.map((item) => ({ value: item.key, label: item.label }))} />
        </div>
        <div className="chart-frame">
          {klineData.length > 0 ? (
            <KLineChart key={`${code}-${period}`} data={klineData} fundType={fund.type} code={code} period={period} chartRange={chartRange} />
          ) : (
            <DataState kind={klineError ? "error" : "loading"} title={klineError ? "走势数据暂时不可用" : "正在读取历史走势"} description={klineError ? "未使用替代数据，请稍后重试。" : undefined} />
          )}
        </div>
        <SourceNote>
          {fund.type === "ETF"
            ? "ETF 为场内行情（含开/高/低/收与成交量），盘中更新；周 K、月 K 由日线聚合。"
            : "场外基金每个交易日仅一个单位净值，此处展示净值走势（非 K 线）；净值为 T-1，交易日盘后更新。数据源不可用时不会显示替代数据。"}
        </SourceNote>
      </ResearchSection>

      <ResearchSection title="风险指标" description="最大回撤看极端下跌，波动率看日常波动，夏普比率看风险调整后收益。">
        <RiskIndicatorTable metrics={fund.metrics} />
      </ResearchSection>

      <ResearchSection
        title="历史回撤与数据质量"
        description="深度分析需要额外读取回撤、统计和同类数据，仍沿用现有接口。"
        action={!analysisEnabled ? <Button onClick={() => setAnalysisEnabled(true)}>加载深度分析 <ArrowRight className="h-4 w-4" /></Button> : undefined}
      >
        {!analysisEnabled ? (
          <DataState kind="empty" title="核心行情已加载" description="点击“加载深度分析”后读取回撤曲线、同类对比和持有人结构。" />
        ) : (
          <>
            <div className="chart-frame h-[260px]">
              {drawdownData.length > 0 ? <DrawdownChart data={drawdownData} /> : <DataState kind="loading" title={drawdownFetching ? "正在计算历史回撤" : "暂无回撤数据"} />}
            </div>
            <SourceNote>回撤表示从历史高点下跌的百分比，越接近 0 表示越接近此前高点。</SourceNote>
            {statisticsAudit && (
              <div className="mt-6 grid gap-x-12 lg:grid-cols-2">
                <KeyValueList items={[
                  { label: "数据状态", value: statisticsAudit.status === "review" ? "需要复核" : statisticsAudit.status === "available" ? "数据可用" : "数据不足" },
                  { label: "净值观测", value: statisticsAudit.observations },
                  { label: "有效日收益", value: statisticsAudit.validReturns },
                  { label: "极端日收益", value: statisticsAudit.outliers.length },
                  { label: "重复日期", value: statisticsAudit.duplicateDates },
                  { label: "统计区间", value: `${statisticsAudit.dataStart ?? "—"} 至 ${statisticsAudit.dataEnd ?? "—"}` },
                ]} />
                <div className="disclosure mt-5 lg:mt-0">
                  <p>基于累计净值；极端收益只提示复核，不会修改历史数据。</p>
                  <p>{statisticsAudit.volatilityCi ? `年化波动率 95% 区间：${formatPercent(statisticsAudit.volatilityCi.lower)} ～ ${formatPercent(statisticsAudit.volatilityCi.upper)}` : "有效日收益不足，暂无法估计波动率区间。"}</p>
                  {statisticsAudit.notes.map((note) => <p key={note}>{note}</p>)}
                </div>
              </div>
            )}
          </>
        )}
      </ResearchSection>

      <ResearchSection id="holdings" title="行业与资产配置" description={`按行业/资产类别划分的披露持仓占比${fund.sectorsAsOf ? `；截至 ${fund.sectorsAsOf}` : ""}。未披露部分不补成“其他”。`}>
        {fund.sectors.length > 0 ? fund.sectors.map((item) => (
          <div className="allocation-row" key={item.name}>
            <span>{item.name}</span>
            <div className="allocation-track" aria-hidden="true"><div className="allocation-fill" style={{ width: `${Math.min(100, item.weight)}%` }} /></div>
            <span className="numeric font-semibold">{item.weight}%</span>
          </div>
        )) : <DataState kind="empty" title="暂无行业分布数据" description="数据源未提供时不生成配置比例。" />}
      </ResearchSection>

      <ResearchSection title="重仓方向" description={`前十大持仓 / 股票、债券及基金资产${fund.holdingsAsOf ? `；截至 ${fund.holdingsAsOf}` : ""}。`}>
        <TopHoldingsTable holdings={fund.topHoldings} />
      </ResearchSection>

      {analysisEnabled && (
        <ResearchSection title="同类基金对比" description="与相同类型基金比较近一年收益、波动率与夏普比率。">
          <PeerComparison data={peers} targetCode={fund.code} />
        </ResearchSection>
      )}

      {holdStructure && holdStructure.points.length > 0 && (
        <ResearchSection title="持有人结构" description={holdStructure.note}>
          <div className="chart-frame h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={holdStructure.points.map((point) => ({ date: point.date.slice(0, 7), 机构持有: point.institutionPct, 个人持有: point.individualPct, 内部持有: point.internalPct }))} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} dy={8} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} domain={[0, 100]} tickFormatter={(value) => `${value}%`} />
                <Tooltip contentStyle={{ background: "var(--background)", border: "1px solid var(--border)", borderRadius: 6 }} formatter={(value) => [`${Number(value).toFixed(1)}%`, undefined]} />
                <Legend verticalAlign="top" height={30} iconType="plainline" />
                <Area type="monotone" dataKey="机构持有" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.08} strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="个人持有" stroke="#6b7280" fill="#6b7280" fillOpacity={0.05} strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="内部持有" stroke="#9ca3af" fill="#9ca3af" fillOpacity={0.04} strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ResearchSection>
      )}

      <ResearchSection id="disclosure" title="数据说明与披露" description="保留数据口径、更新时间与使用边界。">
        <div className="disclosure">
          {fund.description && <p>{fund.description}</p>}
          <p>基金资料、净值、行情与持仓来自 akshare 公开接口。净值日期为 {fund.navDate ?? "未提供"}；持仓与行业日期分别见各分区标注。</p>
          <p>收益、回撤、波动率和夏普比率均按现有后端接口返回口径展示；缺失数据显示为“—”，不以 0 或示例数据代替。</p>
          <p>根据历史数据生成，仅帮助理解，不构成买卖建议。历史表现不代表未来结果。</p>
        </div>
        <Link href="/compare" className="text-link mt-5 inline-flex min-h-11 items-center gap-1">将 {fund.name} 加入基金对比 <ArrowRight className="h-4 w-4" /></Link>
      </ResearchSection>
    </div>
  );
}
