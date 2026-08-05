"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Plus, Search, X, TrendingDown, TrendingUp, BarChart3 } from "lucide-react";
import Link from "next/link";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  FundDetail,
  FundSummary,
  KlinePoint,
  getFundDetail,
  getFundKlineHistory,
  searchFunds,
  formatPercent,
} from "@/services/fund";

const COLORS = ["#0071e3", "#ff3b30", "#00a550", "#ff9500", "#af52de", "#5856d6"];

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
  const [suggestions, setSuggestions] = useState<FundSummary[]>([]);
  const [funds, setFunds] = useState<CompareFund[]>([]);
  const [adding, setAdding] = useState(false);

  // Search suggestions
  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    const t = setTimeout(() => {
      searchFunds(query).then((r) => setSuggestions(r.slice(0, 6)));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  const addFund = async (code: string) => {
    const upper = code.trim().toUpperCase();
    if (funds.find((f) => f.code === upper)) return;

    const id = `f${Date.now()}`;
    setFunds((prev) => [...prev, { id, code: upper, detail: null, kline: [], loading: true, error: null }]);
    setQuery("");
    setSuggestions([]);
    setAdding(true);

    try {
      const [detail, kline] = await Promise.all([
        getFundDetail(upper),
        getFundKlineHistory(upper, "1Y"),
      ]);
      setFunds((prev) =>
        prev.map((f) =>
          f.id === id
            ? { ...f, detail, kline, loading: false, error: null }
            : f
        )
      );
    } catch (err) {
      setFunds((prev) =>
        prev.map((f) =>
          f.id === id
            ? { ...f, loading: false, error: `加载失败: ${err instanceof Error ? err.message : "未知错误"}` }
            : f
        )
      );
    } finally {
      setAdding(false);
    }
  };

  const removeFund = (id: string) => {
    setFunds((prev) => prev.filter((f) => f.id !== id));
  };

  // Build comparison chart data from kline points
  const chartData = useMemo(() => {
    if (funds.length === 0 || funds.every((f) => f.kline.length === 0)) return [];

    // Find the fund with the most data points
    const maxLen = Math.max(...funds.map((f) => f.kline.length));
    const primary = funds.find((f) => f.kline.length === maxLen) || funds[0];

    return primary.kline.map((point, i) => {
      const entry: Record<string, string | number> = { date: point.date };
      for (const fund of funds) {
        if (fund.kline.length === 0) {
          entry[fund.id] = 1;
          continue;
        }
        if (fund.kline[i] !== undefined) {
          // Normalize: all start at 1.0
          const firstClose = fund.kline[0]?.close || 1;
          entry[fund.id] = fund.kline[i].close / firstClose;
        } else {
          entry[fund.id] = null as unknown as number; // gap
        }
      }
      return entry;
    });
  }, [funds]);

  const metrics = [
    { key: "oneYearReturn" as const, label: "近一年收益", format: (v: number) => formatPercent(v) },
    { key: "maxDrawdown" as const, label: "最大回撤", format: (v: number) => formatPercent(v) },
    { key: "sharpe" as const, label: "夏普比率", format: (v: number) => v.toFixed(2) },
    { key: "volatility" as const, label: "波动率", format: (v: number) => formatPercent(v) },
  ];

  const hasData = funds.some((f) => f.detail !== null);

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
          基金对比
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="mt-2 text-muted-foreground"
        >
          同时比较多只基金，从收益、风险与性价比中做出更理性的选择
        </motion.p>
      </section>

      {/* Search & Add */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
        className="mb-6 flex flex-col gap-3 sm:flex-row"
      >
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入基金代码 / 名称加入对比"
            className="h-11 rounded-2xl border-border bg-background pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
          />
          {suggestions.length > 0 && (
            <div className="absolute z-20 mt-2 w-full rounded-2xl border border-border bg-background p-2 shadow-lg">
              {suggestions.map((s) => (
                <button
                  key={s.code}
                  onClick={() => addFund(s.code)}
                  className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm hover:bg-muted"
                >
                  <span className="font-medium">{s.name}</span>
                  <span className="text-xs text-muted-foreground">{s.code}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <Button
          onClick={() => query.trim() && addFund(query.trim())}
          disabled={!query.trim() || adding}
          className="h-11 rounded-2xl px-6"
        >
          <Plus className="mr-2 h-4 w-4" />
          添加
        </Button>
      </motion.div>

      {/* Chart */}
      {chartData.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15, ease: [0.23, 1, 0.32, 1] }}
          className="mb-6 rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-4">
            <h3 className="text-base font-semibold tracking-tight">收益走势对比</h3>
            <p className="text-xs text-muted-foreground">净值归一化走势（全部从 1.0 开始）</p>
          </div>
          <div className="h-[360px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                  dy={8}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                  domain={["auto", "auto"]}
                  tickFormatter={(v) => `${((v - 1) * 100).toFixed(0)}%`}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--background)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                  }}
                  itemStyle={{ fontSize: 13 }}
                  formatter={(value) => [
                    `${((Number(value) - 1) * 100).toFixed(2)}%`,
                    undefined,
                  ]}
                />
                <Legend
                  verticalAlign="top"
                  height={36}
                  iconType="circle"
                  formatter={(value: string) => {
                    const fund = funds.find((f) => f.id === value);
                    return <span className="text-xs">{fund?.detail?.name ?? value}</span>;
                  }}
                />
                {funds
                  .filter((f) => f.kline.length > 0)
                  .map((fund, i) => (
                    <Line
                      key={fund.id}
                      type="monotone"
                      dataKey={fund.id}
                      stroke={COLORS[i % COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0, fill: COLORS[i % COLORS.length] }}
                      connectNulls={false}
                    />
                  ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      )}

      {/* Fund cards + comparison table */}
      {funds.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-2"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">基金</th>
                  <th className="px-4 py-3 font-medium">类型</th>
                  <th className="px-4 py-3 text-right font-medium">净值</th>
                  <th className="px-4 py-3 text-right font-medium">日涨跌</th>
                  {metrics.map((m) => (
                    <th key={m.key} className="px-4 py-3 text-right font-medium">
                      {m.label}
                    </th>
                  ))}
                  <th className="px-4 py-3 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {funds.map((fund, i) => (
                  <tr
                    key={fund.id}
                    className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          className="h-3 w-3 rounded-full flex-shrink-0"
                          style={{ backgroundColor: COLORS[i % COLORS.length] }}
                        />
                        <div>
                          {fund.loading ? (
                            <span className="text-muted-foreground">加载中…</span>
                          ) : fund.error ? (
                            <span className="text-negative text-xs">{fund.error}</span>
                          ) : fund.detail ? (
                            <>
                              <Link
                                href={`/fund/${fund.code}`}
                                className="font-medium hover:text-accent"
                              >
                                {fund.detail.name}
                              </Link>
                              <div className="text-xs text-muted-foreground">{fund.code}</div>
                            </>
                          ) : (
                            <span className="text-muted-foreground">{fund.code}</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {fund.detail && <Badge variant="outline">{fund.detail.type}</Badge>}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {fund.detail?.nav?.toFixed(4) ?? "—"}
                    </td>
                    <td
                      className={`px-4 py-3 text-right tabular-nums font-medium ${
                        (fund.detail?.changePct ?? 0) >= 0 ? "text-positive" : "text-negative"
                      }`}
                    >
                      {fund.detail ? (
                        <span className="inline-flex items-center gap-1">
                          {(fund.detail.changePct ?? 0) >= 0 ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : (
                            <TrendingDown className="h-3 w-3" />
                          )}
                          {formatPercent((fund.detail.changePct ?? 0) * 0.01)}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    {metrics.map((m) => {
                      let value: number | undefined;
                      if (fund.detail) {
                        if (m.key === "oneYearReturn") value = fund.detail.returns.yearly;
                        else if (m.key === "maxDrawdown") value = fund.detail.metrics.maxDrawdown;
                        else if (m.key === "sharpe") value = fund.detail.metrics.sharpe;
                        else if (m.key === "volatility") value = fund.detail.metrics.volatility;
                      }
                      return (
                        <td
                          key={m.key}
                          className={`px-4 py-3 text-right tabular-nums font-medium ${
                            value !== undefined
                              ? value >= 0
                                ? "text-positive"
                                : "text-negative"
                              : ""
                          }`}
                        >
                          {value !== undefined ? m.format(value) : "—"}
                        </td>
                      );
                    })}
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {fund.detail && (
                          <Link href={`/fund/${fund.code}`}>
                            <Button variant="outline" size="sm" className="h-7 rounded-lg text-xs">
                              <BarChart3 className="mr-1 h-3 w-3" />
                              详情
                            </Button>
                          </Link>
                        )}
                        <button
                          onClick={() => removeFund(fund.id)}
                          className="inline-flex items-center justify-center rounded-full p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-negative"
                          aria-label="移除"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Empty state */}
      {funds.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.25, ease: [0.23, 1, 0.32, 1] }}
          className="mt-6 rounded-2xl border border-dashed border-border bg-muted/40 p-12 text-center"
        >
          <BarChart3 className="mx-auto mb-3 h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            搜索并添加基金，至少添加两只基金进行对比分析
          </p>
        </motion.div>
      )}

      {/* Loading state for individual fund */}
      {funds.some((f) => f.loading) && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-6 rounded-2xl border border-border bg-background p-4 text-center text-sm text-muted-foreground"
        >
          正在加载基金数据...
        </motion.div>
      )}
    </div>
  );
}
