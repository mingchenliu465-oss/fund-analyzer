"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CircleHelp,
  Maximize2,
  Minimize2,
  RefreshCw,
  Search,
  Star,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { analyze, demoPoints, normalizePoints } from "./analytics";
import styles from "./workbench.module.css";

type Fund = { code: string; name: string; type: string };
type WorkbenchMode = "demo" | "api";
type ChartView = "change" | "drawdown";

const initialFunds: Fund[] = [
  { code: "510300", name: "沪深300 ETF", type: "ETF" },
  { code: "510500", name: "中证500 ETF", type: "ETF" },
  { code: "159915", name: "创业板 ETF", type: "ETF" },
  { code: "000001", name: "华夏成长混合", type: "混合型" },
];
const ranges = [
  { label: "1个月", months: 1 },
  { label: "3个月", months: 3 },
  { label: "6个月", months: 6 },
  { label: "1年", months: 12 },
];
const percent = (n: number | null) =>
  n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

async function request(path: string, signal: AbortSignal): Promise<unknown> {
  const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "";
  const response = await fetch(`${base}${path}`, {
    signal: AbortSignal.any([signal, AbortSignal.timeout(25000)]),
  });
  if (!response.ok) {
    throw new Error(`接口暂时不可用（${response.status}），请稍后重试。`);
  }
  return response.json();
}

export default function WorkbenchPage() {
  const [mode, setMode] = useState<WorkbenchMode>("demo");
  const [funds, setFunds] = useState(initialFunds);
  const [selected, setSelected] = useState(initialFunds[0]);
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [months, setMonths] = useState(12);
  const [view, setView] = useState<ChartView>("change");
  const [expanded, setExpanded] = useState(false);
  const [starred, setStarred] = useState<string[]>([]);
  const [onlyStarred, setOnlyStarred] = useState(false);

  const history = useQuery({
    queryKey: ["workbench-history", mode, selected.code],
    queryFn: async ({ signal }) =>
      mode === "demo"
        ? demoPoints(Math.max(0, initialFunds.findIndex((f) => f.code === selected.code)))
        : normalizePoints(
            await request(
              `/api/market/kline?code=${encodeURIComponent(selected.code)}&period=${encodeURIComponent("日K")}&range=1Y`,
              signal,
            ),
          ),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const search = useQuery({
    queryKey: ["workbench-search", searchTerm],
    queryFn: async ({ signal }) => {
      const value = await request(
        `/api/funds?q=${encodeURIComponent(searchTerm)}&limit=12`,
        signal,
      );
      if (!Array.isArray(value)) throw new Error("搜索结果格式异常。");
      return value.filter(
        (f): f is Fund =>
          f &&
          typeof f.code === "string" &&
          typeof f.name === "string" &&
          typeof f.type === "string",
      );
    },
    enabled: mode === "api" && !!searchTerm,
    retry: false,
  });

  const stats = useMemo(() => analyze(history.data ?? [], months), [history.data, months]);
  const latest = stats.rows.at(-1);
  const searchActive = mode === "api" && !!searchTerm && query.trim() === searchTerm;
  const candidates = searchActive ? search.data ?? [] : mode === "demo" ? initialFunds : funds;
  const visibleFunds = candidates.filter(
    (f) =>
      (!onlyStarred || starred.includes(f.code)) &&
      (searchActive || `${f.name}${f.code}`.toLowerCase().includes(query.trim().toLowerCase())),
  );
  const conclusion = history.isPending
    ? `正在读取${selected.name}的历史数据，读取完成后再计算区间表现。`
    : history.isError
      ? `${selected.name}的历史数据暂时不可用，本页不会自动替换成另一组数据。`
      : stats.rows.length < 2
        ? `${selected.name}在当前区间的数据不足，请尝试更长时间范围。`
        : `${mode === "demo" ? "示例数据中，" : ""}${selected.name}在 ${stats.rows[0].date} 至 ${latest?.date} 的区间涨跌为 ${percent(stats.change)}，最大回撤为 ${percent(stats.drawdown)}。`;

  const toggleStar = () =>
    setStarred((old) =>
      old.includes(selected.code)
        ? old.filter((code) => code !== selected.code)
        : [...old, selected.code],
    );
  const choose = (fund: Fund) => {
    setSelected(fund);
    setFunds((old) => (old.some((f) => f.code === fund.code) ? old : [...old, fund]));
  };
  const switchMode = (next: WorkbenchMode) => {
    setMode(next);
    setSelected(initialFunds[0]);
    setQuery("");
    setSearchTerm("");
  };

  return (
    <div className="page-container">
      <PageHeader
        title="分析工作台"
        description="把走势、区间收益和回撤放在同一口径下查看。"
        action={
          <SegmentedControl
            label="工作台数据模式"
            value={mode}
            onChange={switchMode}
            items={[
              { value: "demo", label: "演示体验" },
              { value: "api", label: "接口数据" },
            ]}
          />
        }
      />

      <div className={styles.notice} role="status">
        <strong>{mode === "demo" ? "演示体验" : "接口数据"}</strong>
        <span>
          · {mode === "demo"
            ? "所有曲线和数字均为示例，不代表实际表现"
            : "按返回的历史价格／净值计算，不代表实时行情"}
        </span>
      </div>

      <section className={styles.quoteHeader} aria-labelledby="workbench-fund-name">
        <div>
          <p>
            {selected.code} / {selected.type} {mode === "demo" && "/ 示例"}
          </p>
          <h2 id="workbench-fund-name">{selected.name}</h2>
        </div>
        <Button
          variant="outline"
          size="icon"
          aria-label={starred.includes(selected.code) ? "取消标星" : "标星基金"}
          aria-pressed={starred.includes(selected.code)}
          onClick={toggleStar}
          className={starred.includes(selected.code) ? styles.starred : undefined}
        >
          <Star size={18} fill={starred.includes(selected.code) ? "currentColor" : "none"} />
        </Button>
      </section>

      <PlainConclusion
        note={mode === "demo"
          ? "本结论仅解释示例曲线，不是真实基金表现，也不构成买卖建议。"
          : "根据接口返回的历史数据生成，仅帮助理解，不构成买卖建议。"}
      >
        {conclusion}
      </PlainConclusion>

      <MetricStrip
        label="工作台核心指标"
        items={[
          {
            label: "最新价格 / 净值",
            value: latest ? latest.close.toFixed(4) : "—",
            note: latest?.date ?? "暂无可用日期",
          },
          {
            label: "所选区间涨跌",
            value: percent(stats.change),
            note: "从区间第一天到最后一天",
            tone: toneFor(stats.change),
          },
          {
            label: "最大回撤",
            value: percent(stats.drawdown),
            note: "距所选区间内前高",
            tone: stats.drawdown == null ? "neutral" : "down",
          },
          {
            label: "数据点",
            value: `${stats.rows.length} 个`,
            note: "当前区间实际数据量",
          },
        ]}
      />
      <SourceNote>
        缺失数据显示为“—”。最大回撤与区间涨跌均使用当前时间范围，不跨区间补数。
      </SourceNote>

      {!expanded && (
        <ResearchSection
          title="选择基金"
          description={`${visibleFunds.length} 只可选基金；标星只在本次页面停留期间保留。`}
          action={
            <SegmentedControl
              label="基金标星筛选"
              value={onlyStarred ? "starred" : "all"}
              onChange={(value) => setOnlyStarred(value === "starred")}
              items={[
                { value: "all", label: "全部" },
                { value: "starred", label: "已标星" },
              ]}
            />
          }
        >
          <form
            className={styles.search}
            onSubmit={(e) => {
              e.preventDefault();
              setSearchTerm(query.trim());
            }}
          >
            <Input
              aria-label="搜索基金名称或代码"
              placeholder="搜索名称 / 代码"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSearchTerm("");
              }}
            />
            <Button type="submit" variant="outline" className="gap-2">
              <Search size={16} /> 搜索
            </Button>
          </form>
          {mode === "api" && <p className={styles.hint}>输入名称或代码后，按回车搜索。</p>}
          {searchActive && search.isFetching && (
            <p className={styles.hint} role="status">正在搜索…</p>
          )}
          {searchActive && search.isError && (
            <div className={styles.error} role="alert">
              <span>搜索失败，请按搜索按钮重试。</span>
              <Button variant="outline" size="sm" onClick={() => void search.refetch()}>
                重试
              </Button>
            </div>
          )}
          {visibleFunds.length > 0 ? (
            <div className={styles.fundList}>
              {visibleFunds.map((fund) => (
                <button
                  type="button"
                  className={styles.fund}
                  key={fund.code}
                  aria-pressed={selected.code === fund.code}
                  onClick={() => choose(fund)}
                >
                  <span>
                    <strong>{fund.name}</strong>
                    <small>{fund.code} · {fund.type}</small>
                  </span>
                  {starred.includes(fund.code) && <Star size={14} fill="currentColor" />}
                </button>
              ))}
            </div>
          ) : (
            !search.isFetching && (
              <DataState
                kind="empty"
                title={onlyStarred ? "没有匹配的标星基金" : "没有匹配的基金"}
                description={onlyStarred
                  ? "点击基金标题旁的星号即可添加。"
                  : "试试其他名称或代码。"}
              />
            )
          )}
          <div className={styles.listFooter}>
            <CircleHelp size={15} />
            <p>
              {mode === "demo"
                ? "先用 4 只示例基金体验布局。标星仅在本次页面停留期间保留。"
                : "搜索结果沿用现有数据源，名称可能来自缓存；标星仅本次有效。"}
            </p>
          </div>
        </ResearchSection>
      )}

      <ResearchSection
        title={view === "change" ? "区间走势" : "回撤走势"}
        description={view === "change"
          ? "把所选区间第一天设为 0%，观察之后的价格或净值变化。"
          : "从所选区间内此前高点计算回撤；更换范围会改变结果。"}
        action={
          <Button
            variant="outline"
            size="icon"
            aria-label={expanded ? "收起图表" : "展开图表"}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
          </Button>
        }
      >
        <div className={styles.toolbar}>
          <SegmentedControl
            label="工作台图表类型"
            value={view}
            onChange={setView}
            items={[
              { value: "change", label: "区间走势" },
              { value: "drawdown", label: "回撤走势" },
            ]}
          />
          <SegmentedControl
            label="工作台图表区间"
            value={months}
            onChange={setMonths}
            items={ranges.map((range) => ({ value: range.months, label: range.label }))}
          />
        </div>
        <div className={`${styles.chart} ${expanded ? styles.expandedChart : ""}`}>
          {history.isPending ? (
            <DataState kind="loading" title="正在读取历史数据" description="请稍候，图表会在数据返回后显示。" />
          ) : history.isError ? (
            <DataState
              kind="error"
              title="暂时无法加载走势"
              description="请检查后端服务或稍后重试。这里不会自动替换成演示数据。"
              action={
                <Button variant="outline" onClick={() => void history.refetch()} className="gap-2">
                  <RefreshCw size={14} /> 重新加载
                </Button>
              }
            />
          ) : stats.rows.length < 2 ? (
            <DataState
              kind="empty"
              title="当前区间数据不足"
              description="试试更长的时间范围。缺失数据不会用 0 或示例值填充。"
            />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.rows} margin={{ top: 24, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 5" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(date: string) => date.slice(2)}
                  minTickGap={50}
                  stroke="var(--muted-foreground)"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 11 }}
                />
                <YAxis
                  orientation="right"
                  tickFormatter={(n: number) => `${n.toFixed(0)}%`}
                  stroke="var(--muted-foreground)"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 11 }}
                  width={52}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--background)",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    color: "var(--foreground)",
                    boxShadow: "none",
                  }}
                  labelStyle={{ color: "var(--muted-foreground)" }}
                  formatter={(value) => [
                    `${Number(value).toFixed(2)}%`,
                    view === "change" ? "区间涨跌" : "距区间内前高",
                  ]}
                />
                <ReferenceLine y={0} stroke="var(--border)" />
                <Area
                  type="linear"
                  dataKey={view}
                  stroke={view === "change" ? "var(--chart-line)" : "var(--negative)"}
                  strokeWidth={2}
                  fill="var(--muted)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className={styles.chartCaption}>
          <span>
            {stats.rows.length ? `${stats.rows[0].date} — ${latest?.date}` : "等待数据"}
            {" · "}{stats.rows.length} 个数据点
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={history.isFetching}
            onClick={() => void history.refetch()}
            className="gap-2"
          >
            <RefreshCw size={13} />{history.isFetching ? "加载中" : "刷新"}
          </Button>
        </div>
        <SourceNote>
          {view === "change"
            ? "区间变化不等同于包含分红的总收益。"
            : "回撤就是从此前的高点跌下来了多少；这里只使用当前所选区间。"}
        </SourceNote>
      </ResearchSection>

      {!expanded && (
        <ResearchSection title="指标口径与阅读方法" description="先理解口径，再比较不同基金或不同时间范围。">
          <KeyValueList
            columns={2}
            items={[
              {
                label: "这段时间涨跌多少",
                note: "从区间第一天到最后一天",
                value: <span className={stats.change == null ? "text-muted-foreground" : stats.change >= 0 ? "text-positive" : "text-negative"}>{percent(stats.change)}</span>,
              },
              {
                label: "中途最多跌了多少",
                note: "所选区间内最大回撤",
                value: <span className={stats.drawdown == null ? "text-muted-foreground" : "text-negative"}>{percent(stats.drawdown)}</span>,
              },
            ]}
          />
          <div className="disclosure mt-5">
            <p>涨跌告诉你起点到终点的变化；回撤告诉你，这一路上经历了多大的下跌。</p>
            <p>把两者放在一起看，更容易理解持有过程。</p>
          </div>
          <Link className="text-link mt-5 inline-flex min-h-11 items-center gap-2" href={`/fund/${encodeURIComponent(selected.code)}`}>
            打开现有基金详情 <ArrowUpRight size={16} />
          </Link>
          <p className={styles.hint}>详情页沿用原有数据设置，与本页演示模式独立。</p>
        </ResearchSection>
      )}

      <footer className={styles.footer}>
        <span>分析工作台 / 独立体验入口</span>
        <span>{mode === "demo" ? "示例数据仅用于体验界面" : "数据截止日期见图表 · 红涨绿跌"}</span>
      </footer>
    </div>
  );
}
