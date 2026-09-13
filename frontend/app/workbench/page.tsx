"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowUpRight, ChartNoAxesCombined, CircleHelp, Maximize2, Minimize2, RefreshCw, Search, Star } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { analyze, demoPoints, normalizePoints } from "./analytics";
import styles from "./workbench.module.css";

type Fund = { code: string; name: string; type: string };
const initialFunds: Fund[] = [
  { code: "510300", name: "沪深300 ETF", type: "ETF" },
  { code: "510500", name: "中证500 ETF", type: "ETF" },
  { code: "159915", name: "创业板 ETF", type: "ETF" },
  { code: "000001", name: "华夏成长混合", type: "混合型" },
];
const ranges = [{ label: "1个月", months: 1 }, { label: "3个月", months: 3 }, { label: "6个月", months: 6 }, { label: "1年", months: 12 }];
const percent = (n: number | null) => n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

async function request(path: string, signal: AbortSignal): Promise<unknown> {
  const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "";
  const response = await fetch(`${base}${path}`, { signal: AbortSignal.any([signal, AbortSignal.timeout(25000)]) });
  if (!response.ok) throw new Error(`接口暂时不可用（${response.status}），请稍后重试。`);
  return response.json();
}

export default function WorkbenchPage() {
  const [mode, setMode] = useState<"demo" | "api">("demo");
  const [funds, setFunds] = useState(initialFunds);
  const [selected, setSelected] = useState(initialFunds[0]);
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [months, setMonths] = useState(12);
  const [view, setView] = useState<"change" | "drawdown">("change");
  const [expanded, setExpanded] = useState(false);
  const [starred, setStarred] = useState<string[]>([]);
  const [onlyStarred, setOnlyStarred] = useState(false);
  const history = useQuery({
    queryKey: ["workbench-history", mode, selected.code],
    queryFn: async ({ signal }) => mode === "demo"
      ? demoPoints(Math.max(0, initialFunds.findIndex((f) => f.code === selected.code)))
      : normalizePoints(await request(`/api/market/kline?code=${encodeURIComponent(selected.code)}&period=${encodeURIComponent("日K")}&range=1Y`, signal)),
    staleTime: 5 * 60 * 1000, retry: false,
  });
  const search = useQuery({
    queryKey: ["workbench-search", searchTerm],
    queryFn: async ({ signal }) => {
      const value = await request(`/api/funds?q=${encodeURIComponent(searchTerm)}&limit=12`, signal);
      if (!Array.isArray(value)) throw new Error("搜索结果格式异常。");
      return value.filter((f): f is Fund => f && typeof f.code === "string" && typeof f.name === "string" && typeof f.type === "string");
    },
    enabled: mode === "api" && !!searchTerm, retry: false,
  });
  const stats = useMemo(() => analyze(history.data ?? [], months), [history.data, months]);
  const latest = stats.rows.at(-1);
  const searchActive = mode === "api" && !!searchTerm && query.trim() === searchTerm;
  const candidates = searchActive ? search.data ?? [] : mode === "demo" ? initialFunds : funds;
  const visibleFunds = candidates.filter((f) => (!onlyStarred || starred.includes(f.code)) && (searchActive || `${f.name}${f.code}`.toLowerCase().includes(query.trim().toLowerCase())));
  const toggleStar = () => setStarred((old) => old.includes(selected.code) ? old.filter((code) => code !== selected.code) : [...old, selected.code]);
  const choose = (fund: Fund) => {
    setSelected(fund);
    setFunds((old) => old.some((f) => f.code === fund.code) ? old : [...old, fund]);
  };
  const switchMode = (next: "demo" | "api") => {
    setMode(next); setSelected(initialFunds[0]); setQuery(""); setSearchTerm("");
  };

  return (
    <div className={styles.workbench}>
      <header className={styles.header}>
        <div className={styles.heading}><div className={styles.logo}><ChartNoAxesCombined size={22} /></div><div><h1>分析工作台 <span className={styles.badge}>体验版</span></h1><p>把走势、收益和风险放在一起看</p></div></div>
        <Link className={styles.back} href="/"><ArrowLeft size={15} /> 返回首页</Link>
      </header>
      <div className={styles.notice} role="status">
        <span><span className={styles.dot} />{mode === "demo" ? "演示体验 · 所有曲线和数字均为示例，不代表实际表现" : "接口数据 · 按返回的历史价格／净值计算，不代表实时行情"}</span>
        <div className={styles.segment}><button aria-pressed={mode === "demo"} onClick={() => switchMode("demo")}>演示体验</button><button aria-pressed={mode === "api"} onClick={() => switchMode("api")}>接口数据</button></div>
      </div>
      <div className={`${styles.workspace} ${expanded ? styles.expanded : ""}`}>
        <aside className={styles.listPanel}>
          <div className={styles.panelTitle}><h2>关注列表</h2><span>{visibleFunds.length} 只</span></div>
          <form className={styles.search} onSubmit={(e) => { e.preventDefault(); setSearchTerm(query.trim()); }}>
            <input aria-label="搜索基金名称或代码" placeholder="搜索名称 / 代码" value={query} onChange={(e) => { setQuery(e.target.value); setSearchTerm(""); }} />
            <button aria-label="搜索基金" type="submit"><Search size={16} /></button>
          </form>
          <div className={styles.listTabs}><button aria-pressed={!onlyStarred} onClick={() => setOnlyStarred(false)}>全部</button><button aria-pressed={onlyStarred} onClick={() => setOnlyStarred(true)}>已标星</button></div>
          {mode === "api" && <p className={styles.hint}>输入名称或代码后，按回车搜索。</p>}
          {searchActive && search.isFetching && <p className={styles.hint} role="status">正在搜索…</p>}
          {searchActive && search.isError && <p className={styles.error} role="alert">搜索失败，请按搜索按钮重试。<button onClick={() => void search.refetch()}>重试</button></p>}
          <div className={styles.fundList}>{visibleFunds.map((fund) => <button className={styles.fund} key={fund.code} aria-pressed={selected.code === fund.code} onClick={() => choose(fund)}><span className={styles.fundIcon}>{fund.type === "ETF" ? "E" : "F"}</span><span><strong>{fund.name}</strong><small>{fund.code} · {fund.type}</small></span>{starred.includes(fund.code) && <Star size={12} fill="currentColor" />}</button>)}</div>
          {!visibleFunds.length && !search.isFetching && <p className={styles.hint}>{onlyStarred ? "还没有匹配的标星基金。点击基金标题旁的星号即可添加。" : "没有匹配的基金。试试其他名称或代码。"}</p>}
          <div className={styles.listFooter}><CircleHelp size={15} /><p>{mode === "demo" ? "先用 4 只示例基金体验布局。标星仅在本次页面停留期间保留。" : "搜索结果沿用现有数据源，名称可能来自缓存；标星仅本次有效。"}</p></div>
        </aside>
        <section className={styles.chartPanel} aria-label="基金走势分析">
          <div className={styles.fundHeader}><div><div className={styles.eyebrow}>{selected.code} / {selected.type} {mode === "demo" && " / 示例"}</div><h2>{selected.name}<button aria-label={starred.includes(selected.code) ? "取消标星" : "标星基金"} aria-pressed={starred.includes(selected.code)} onClick={toggleStar}><Star size={19} fill={starred.includes(selected.code) ? "currentColor" : "none"} /></button></h2></div><button className={styles.iconButton} aria-label={expanded ? "收起图表" : "展开图表"} onClick={() => setExpanded(!expanded)}>{expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}</button></div>
          <div className={styles.quote}><strong>{latest ? latest.close.toFixed(4) : "—"}</strong><span>价格 / 净值</span><b className={(stats.change ?? 0) >= 0 ? styles.up : styles.down}>{percent(stats.change)}<small>所选区间涨跌</small></b></div>
          <div className={styles.toolbar}><div className={styles.segment}><button aria-pressed={view === "change"} onClick={() => setView("change")}>区间走势</button><button aria-pressed={view === "drawdown"} onClick={() => setView("drawdown")}>回撤走势</button></div><div className={styles.ranges}>{ranges.map((range) => <button key={range.months} aria-pressed={months === range.months} onClick={() => setMonths(range.months)}>{range.label}</button>)}</div></div>
          <div className={styles.chart}>
            {history.isPending ? <div className={styles.empty} role="status">正在读取历史数据…</div> : history.isError ? <div className={styles.empty} role="alert"><strong>暂时无法加载走势</strong><p>请检查后端服务或稍后重试。这里不会自动替换成演示数据。</p><button onClick={() => void history.refetch()}><RefreshCw size={14} /> 重新加载</button></div> : stats.rows.length < 2 ? <div className={styles.empty}>当前区间数据不足，试试更长的时间范围。</div> : <ResponsiveContainer width="100%" height="100%"><AreaChart data={stats.rows} margin={{ top: 24, right: 12, left: 0, bottom: 8 }}><defs><linearGradient id="workbench-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={view === "change" ? "#5a9dff" : "#35c6a2"} stopOpacity={0.26} /><stop offset="100%" stopColor="#5a9dff" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid stroke="#263143" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" tickFormatter={(date: string) => date.slice(2)} minTickGap={50} stroke="#8998b0" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} /><YAxis orientation="right" tickFormatter={(n: number) => `${n.toFixed(0)}%`} stroke="#8998b0" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} width={52} domain={["auto", "auto"]} /><Tooltip contentStyle={{ background: "#172133", border: "1px solid #34445e", borderRadius: 8, color: "#eef3fa" }} labelStyle={{ color: "#a9b8ce" }} formatter={(value) => [`${Number(value).toFixed(2)}%`, view === "change" ? "区间涨跌" : "距区间内前高"]} /><ReferenceLine y={0} stroke="#42516b" /><Area type="linear" dataKey={view} stroke={view === "change" ? "#6da8ff" : "#35c6a2"} strokeWidth={2} fill="url(#workbench-fill)" isAnimationActive={false} /></AreaChart></ResponsiveContainer>}
          </div>
          <div className={styles.chartCaption}><span>{stats.rows.length ? `${stats.rows[0].date} — ${latest!.date}` : "等待数据"} · {stats.rows.length} 个数据点</span><button disabled={history.isFetching} onClick={() => void history.refetch()}><RefreshCw size={13} />{history.isFetching ? "加载中" : "刷新"}</button></div>
          <div className={styles.explainer}><CircleHelp size={16} /><p>{view === "change" ? "把所选区间的第一天设为 0%，看价格或净值之后涨跌了多少。该变化不等同于包含分红的总收益。" : "回撤就是从此前的高点跌下来了多少。这里从所选区间开始计算，更换时间范围，结果也会变化。"}</p></div>
        </section>
        <aside className={styles.summary}>
          <div className={styles.panelTitle}><h2>一眼看懂</h2><span>同一区间</span></div>
          <div className={styles.metric}><span>这段时间涨跌多少</span><strong className={(stats.change ?? 0) >= 0 ? styles.up : styles.down}>{percent(stats.change)}</strong><p>从区间第一天到最后一天</p></div>
          <div className={styles.metric}><span>中途最多跌了多少</span><strong className={styles.down}>{percent(stats.drawdown)}</strong><p>所选区间内最大回撤</p></div>
          <div className={styles.reading}><h3>怎么看这两个数字？</h3><p>涨跌告诉你起点到终点的变化；回撤告诉你，这一路上经历了多大的下跌。</p><p>把两者放在一起看，更容易理解持有过程。</p></div>
          <Link className={styles.detailLink} href={`/fund/${encodeURIComponent(selected.code)}`}>打开现有基金详情 <ArrowUpRight size={16} /></Link>
          <p className={styles.hint}>详情页沿用原有数据设置，与本页演示模式独立。</p>
        </aside>
      </div>
      <footer className={styles.footer}><span>分析工作台 / 独立体验入口</span><span>{mode === "demo" ? "示例数据仅用于体验界面" : "数据截止日期见图表 · 红涨绿跌"}</span></footer>
    </div>
  );
}
