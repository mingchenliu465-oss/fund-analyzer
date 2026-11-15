"use client";

import { useMemo, useState } from "react";
import { Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataState, PageHeader, PlainConclusion, ResearchSection, SourceNote } from "@/components/research-ui";
import { useFundSearch } from "@/hooks/use-fund-search";
import {
  FundDetail,
  KlinePoint,
  getFundDetail,
  getFundKlineHistory,
  formatPercent,
} from "@/services/fund";

const COLORS = ["#1f5fbf", "#d13c3c", "#16865c", "#6b7280", "#7a9cc6", "#343a40"];

function keepLatestYear(points: KlinePoint[]): KlinePoint[] {
  if (points.length === 0) return points;
  const timestamp = (date: string) => {
    const value = /^\d{4}-\d{2}$/.test(date) ? `${date}-01` : date;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : NaN;
  };
  const latest = Math.max(...points.map((point) => timestamp(point.date)));
  if (!Number.isFinite(latest)) return points;
  const cutoff = new Date(latest);
  cutoff.setFullYear(cutoff.getFullYear() - 1);
  return points.filter((point) => timestamp(point.date) >= cutoff.getTime());
}

interface CompareFund {
  id: string;
  code: string;
  detail: FundDetail | null;
  kline: KlinePoint[];
  loading: boolean;
  error: string | null;
}

export default function ComparePage() {
  const [query, setQuery] = useState("");
  const [funds, setFunds] = useState<CompareFund[]>([]);
  const [adding, setAdding] = useState(false);
  const { suggestions, isSearching, isError } = useFundSearch(query, 6);

  const addFund = async (code: string) => {
    const upper = code.trim().toUpperCase();
    if (funds.find((fund) => fund.code === upper)) return;
    const id = `f${upper}`;
    setFunds((previous) => [...previous, { id, code: upper, detail: null, kline: [], loading: true, error: null }]);
    setQuery("");
    setAdding(true);
    try {
      const [detail, kline] = await Promise.all([getFundDetail(upper), getFundKlineHistory(upper, "1Y")]);
      const recentKline = keepLatestYear(kline);
      setFunds((previous) => previous.map((fund) => fund.id === id ? { ...fund, detail, kline: recentKline, loading: false, error: null } : fund));
    } catch (error) {
      console.error(`Compare request failed for ${upper}`, error);
      setFunds((previous) => previous.map((fund) => fund.id === id ? { ...fund, loading: false, error: "该基金数据暂时不可用，请稍后重试。" } : fund));
    } finally {
      setAdding(false);
    }
  };

  const chartData = useMemo(() => {
    if (funds.length === 0 || funds.every((fund) => fund.kline.length === 0)) return [];
    const series = funds.map((fund) => {
      const byDate = new Map<string, number>();
      let firstClose: number | null = null;
      for (const point of fund.kline) {
        if (!point.date || !Number.isFinite(point.close)) continue;
        byDate.set(point.date, point.close);
        if (firstClose === null && point.close !== 0) firstClose = point.close;
      }
      return { fund, byDate, firstClose };
    });
    const dates = Array.from(new Set(series.flatMap(({ byDate }) => Array.from(byDate.keys())))).sort();
    return dates.map((date) => {
      const entry: Record<string, string | number | null> = { date };
      for (const { fund, byDate, firstClose } of series) {
        const close = byDate.get(date);
        entry[fund.id] = close !== undefined && firstClose !== null ? close / firstClose : null;
      }
      return entry;
    });
  }, [funds]);

  const loadedFunds = funds.filter((fund) => fund.detail);
  const metrics = [
    { key: "oneYearReturn" as const, label: "近一年收益", note: "近 12 个月", format: (value: number) => formatPercent(value) },
    { key: "maxDrawdown" as const, label: "最大回撤", note: "历史极端下跌", format: (value: number) => formatPercent(value) },
    { key: "sharpe" as const, label: "夏普比率", note: "风险调整后收益", format: (value: number) => value.toFixed(2) },
    { key: "volatility" as const, label: "波动率", note: "年化历史波动", format: (value: number) => formatPercent(value) },
  ];

  return (
    <div className="page-container">
      <PageHeader title="基金对比" description="把多只基金放在同一页，比较归一化走势、历史收益与风险；不生成买卖结论。" />
      <PlainConclusion>
        {funds.length === 0
          ? "先添加至少两只基金。走势以各自首个有效净值为 1.0，只比较所选历史区间，不代表未来表现。"
          : funds.length === 1
            ? "已添加 1 只基金，再添加一只即可横向比较。当前数据仍可用于检查单只基金的收益与风险。"
            : `已添加 ${funds.length} 只基金，其中 ${loadedFunds.length} 只已返回详情。请同时看收益、最大回撤和波动率，不要只按涨幅排序。`}
      </PlainConclusion>

      <ResearchSection title="添加基金" description="可输入完整代码直接添加，也可以从名称搜索结果中选择。">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入基金代码 / 名称加入对比" className="pl-10" aria-label="搜索并添加对比基金" />
            {query.trim() && (
              <div className="absolute z-20 mt-1 w-full border border-border bg-background py-2">
                {suggestions.length > 0 ? suggestions.map((fund) => (
                  <button key={fund.code} onClick={() => addFund(fund.code)} className="flex min-h-11 w-full items-center justify-between gap-4 px-4 py-2 text-left text-sm hover:bg-muted">
                    <span className="truncate font-medium">{fund.name}</span><span className="numeric text-xs text-muted-foreground">{fund.code}</span>
                  </button>
                )) : (
                  <p className="px-4 py-3 text-xs text-muted-foreground">
                    {isSearching
                      ? "正在搜索…"
                      : isError
                        ? "搜索暂时不可用；可按“添加”直接查询完整代码。"
                        : "没有搜索建议；可按“添加”直接查询完整代码。"}
                  </p>
                )}
              </div>
            )}
          </div>
          <Button onClick={() => query.trim() && addFund(query.trim())} disabled={!query.trim() || adding}><Plus className="h-4 w-4" /> 添加</Button>
        </div>
      </ResearchSection>

      {funds.length === 0 ? (
        <DataState kind="empty" title="还没有对比基金" description="从上方搜索并添加基金，至少两只时可进行横向比较。" />
      ) : (
        <>
          <ResearchSection title="近一年归一化走势" description="每条曲线从各自首个有效净值的 1.0 开始；不同成立日期和缺失交易日按真实日期对齐。">
            {chartData.length > 0 ? (
              <div className="chart-frame h-[340px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                    <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} dy={8} minTickGap={28} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(value) => `${((value - 1) * 100).toFixed(0)}%`} />
                    <Tooltip contentStyle={{ background: "var(--background)", border: "1px solid var(--border)", borderRadius: 6 }} formatter={(value) => [`${((Number(value) - 1) * 100).toFixed(2)}%`, undefined]} />
                    <Legend verticalAlign="top" height={36} iconType="plainline" formatter={(value: string) => <span className="text-xs">{funds.find((fund) => fund.id === value)?.detail?.name ?? value}</span>} />
                    {funds.filter((fund) => fund.kline.length > 0).map((fund, index) => (
                      <Line key={fund.id} type="monotone" dataKey={fund.id} stroke={COLORS[index % COLORS.length]} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} connectNulls={false} isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <DataState kind={funds.some((fund) => fund.loading) ? "loading" : "error"} title={funds.some((fund) => fund.loading) ? "正在加载基金走势" : "暂时没有可比较的走势"} description="请检查单只基金的错误信息；不会用演示曲线替代。" />
            )}
            <SourceNote>归一化变化不包含分红再投资口径，不等同于基金总收益；数据截止日期以图表最后一个真实交易日为准。</SourceNote>
          </ResearchSection>

          <ResearchSection title="关键指标对比" description="红涨绿跌；“—”表示接口未提供或指标无法计算，不代表 0。">
            <div className="overflow-x-auto">
              <table className="data-table min-w-[760px]">
                <thead><tr><th>基金</th><th>类型</th><th className="numeric">净值</th><th className="numeric">日涨跌</th>{metrics.map((metric) => <th className="numeric" key={metric.key}>{metric.label}</th>)}<th className="numeric">操作</th></tr></thead>
                <tbody>
                  {funds.map((fund, index) => (
                    <tr key={fund.id}>
                      <td>
                        <div className="flex items-start gap-2">
                          <span className="mt-2 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                          <div>
                            {fund.loading ? <span className="text-muted-foreground">正在加载 {fund.code}</span> : fund.error ? <span className="text-negative text-xs">{fund.error}</span> : fund.detail ? <><Link href={`/fund/${fund.code}`} className="font-medium hover:text-accent">{fund.detail.name}</Link><div className="text-xs text-muted-foreground">{fund.code} · {fund.detail.navDate ?? "日期缺失"}</div></> : fund.code}
                          </div>
                        </div>
                      </td>
                      <td>{fund.detail?.type ?? "—"}</td>
                      <td className="numeric">{fund.detail?.nav?.toFixed(4) ?? "—"}</td>
                      <td className={`numeric font-semibold ${fund.detail?.changePct == null ? "text-muted-foreground" : fund.detail.changePct >= 0 ? "text-positive" : "text-negative"}`}>{fund.detail?.changePct == null ? "—" : formatPercent(fund.detail.changePct * 0.01)}</td>
                      {metrics.map((metric) => {
                        let value: number | null | undefined;
                        if (fund.detail) {
                          if (metric.key === "oneYearReturn") value = fund.detail.returns.yearly;
                          else if (metric.key === "maxDrawdown") value = fund.detail.metrics.maxDrawdown;
                          else if (metric.key === "sharpe") value = fund.detail.metrics.sharpe;
                          else value = fund.detail.metrics.volatility;
                        }
                        return <td key={metric.key} className={`numeric font-medium ${value == null ? "text-muted-foreground" : metric.key !== "sharpe" && metric.key !== "volatility" ? value >= 0 ? "text-positive" : "text-negative" : ""}`}>{value == null ? "—" : metric.format(value)}</td>;
                      })}
                      <td className="numeric whitespace-nowrap">
                        {fund.detail && <Link href={`/fund/${fund.code}`} className="text-link mr-3">详情</Link>}
                        <button onClick={() => setFunds((previous) => previous.filter((item) => item.id !== fund.id))} className="inline-flex min-h-11 items-center gap-1 text-muted-foreground hover:text-foreground" aria-label={`移除 ${fund.detail?.name ?? fund.code}`}><X className="h-4 w-4" /> 移除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <SourceNote>来源：akshare 公开接口，各基金数据日期见基金名称下方。历史指标仅用于理解，不构成买卖建议。</SourceNote>
          </ResearchSection>
        </>
      )}
    </div>
  );
}
