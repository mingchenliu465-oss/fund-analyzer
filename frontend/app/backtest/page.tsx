"use client";

import { useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, History, Info, Search } from "lucide-react";
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
  BacktestCombo,
  BacktestReport,
  countConclusions,
  formatPercent,
  getBacktestReport,
  plainBacktestSummary,
} from "@/services/fund";
import { useFundSearch } from "@/hooks/use-fund-search";

/** 无正负号的百分比（波动率/最大回撤用，与引擎报告的 _pct_plain 口径一致）。 */
function pctPlain(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function conclusionVariant(conclusion: string): "positive" | "negative" | "warning" | "default" {
  if (conclusion === "成立") return "positive";
  if (conclusion === "不成立") return "negative";
  if (conclusion === "证据不足") return "warning";
  return "default";
}

function returnClass(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value) || value === 0) return "";
  return value > 0 ? "text-positive" : "text-negative";
}

/** 表头下方的白话小字注释：给第一次看的人解释术语，不改变任何数字口径。 */
function HeaderNote({ children }: { children: ReactNode }) {
  return (
    <span className="mt-0.5 block text-[11px] font-normal leading-snug text-muted-foreground/75">
      {children}
    </span>
  );
}

export default function BacktestPage() {
  const [query, setQuery] = useState("");
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<BacktestReport | null>(null);
  const [selectedCombo, setSelectedCombo] = useState(0);

  // 搜索建议走全站共享 hook（失败时返回空，绝不编造候选基金）
  const { suggestions } = useFundSearch(query);

  const runBacktest = async (rawCode: string) => {
    const code = rawCode.trim().toUpperCase();
    if (!code || loading) return;
    setLoading(true);
    setError(null);
    setReport(null);
    setSuggestOpen(false);
    try {
      const result = await getBacktestReport(code);
      setReport(result);
      setSelectedCombo(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "回测请求失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const combo: BacktestCombo | null =
    report && report.status === "ok" ? report.combos[selectedCombo] ?? null : null;

  const conclusionCounts = useMemo(
    () => (report ? countConclusions(report.combos) : {}),
    [report]
  );

  const chartData = useMemo(() => {
    if (!combo) return [];
    const { dates, strategy, benchmark } = combo.equity_monthly;
    const n = Math.min(dates.length, strategy.length, benchmark.length);
    return Array.from({ length: n }, (_, i) => ({
      date: dates[i].slice(0, 7),
      strategy: strategy[i],
      benchmark: benchmark[i],
    }));
  }, [combo]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Header */}
      <section className="mb-8">
        <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight">
          <History className="h-6 w-6" />
          诚实回测
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          验证一句话在历史上到底成不成立：「净值跌破近 250 个交易日高点达到某档阈值时触发买入、持有固定期限后卖出」。
          阈值只有 10% / 15% / 20% 三档，持有期只有 6 / 12 个月两档，共 6 种组合，全部列示、不挑最好看的。
          本页只做历史验证，不判断未来涨跌，不提供买卖意见。
        </p>
        <p className="mt-3 max-w-3xl rounded-xl bg-muted/40 px-3.5 py-2.5 text-sm leading-relaxed text-muted-foreground">
          怎么看这页：① 先看结论 ② 再看「超额」列是正是负 ③
          想核对，就翻到最下面的交易明细，抽查任意一笔。
        </p>
      </section>

      {/* 输入区 */}
      <section className="mb-8">
        <div className="relative max-w-xl">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSuggestOpen(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") runBacktest(query);
                }}
                placeholder="输入基金代码或名称，如 161725"
                className="pl-9"
              />
            </div>
            <Button onClick={() => runBacktest(query)} disabled={loading || !query.trim()}>
              {loading ? "回测中…" : "开始回测"}
            </Button>
          </div>
          {suggestOpen && suggestions.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-border/60 bg-background shadow-lg">
              {suggestions.map((fund) => (
                <button
                  key={fund.code}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted/60"
                  onClick={() => {
                    setQuery(fund.code);
                    runBacktest(fund.code);
                  }}
                >
                  <span>
                    <span className="font-medium">{fund.name}</span>
                    <span className="ml-2 text-muted-foreground">{fund.type}</span>
                  </span>
                  <span className="text-muted-foreground">{fund.code}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        {loading && (
          <div className="mt-6 flex items-center gap-3 text-sm text-muted-foreground">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-foreground/20 border-t-foreground" />
            正在拉取全程历史净值并计算 6 种组合，冷启动时可能需要几十秒…
          </div>
        )}
        {error && (
          <div className="mt-6 flex max-w-3xl items-start gap-2.5 rounded-2xl border border-negative/30 bg-negative/5 p-4 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-negative" />
            <div>
              <div className="font-medium text-negative">回测没能完成</div>
              <div className="mt-1 leading-relaxed text-muted-foreground">{error}</div>
            </div>
          </div>
        )}
      </section>

      {report && (
        <div className="space-y-8">
          {/* 基金与数据区间 */}
          <section>
            <h2 className="text-xl font-semibold tracking-tight">
              {report.name || "（名称未知）"}
              <span className="ml-2 text-base font-normal text-muted-foreground">{report.code}</span>
            </h2>
            {report.data_start && report.data_end && (
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                数据区间：{report.data_start} 至 {report.data_end}
                {report.eval_start &&
                  `；样本外评估段自 ${report.eval_start} 开始（样本外＝没有参与任何调整的历史段，只用它下结论；此前 ${report.warmup_days} 个交易日为预热段＝规则先热身看数据的一段，只用来找历史高点，不进入任何结论）`}
              </p>
            )}
          </section>

          {report.status === "refused" ? (
            <section className="flex max-w-3xl items-start gap-2.5 rounded-2xl border border-warning/40 bg-warning/5 p-4">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
              <div>
                <div className="text-base font-semibold">结论：拒绝出结论</div>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {report.refusal_reason}
                </p>
              </div>
            </section>
          ) : (
            <>
              {/* 结论总览 */}
              <section className="rounded-2xl border border-border/60 p-5">
                <h3 className="text-sm font-medium text-muted-foreground">
                  结论总览（6 种组合按同一套写死的规则各自判定，不合并、不挑最优）
                </h3>
                <p className="mt-2.5 text-base font-medium leading-relaxed">
                  {plainBacktestSummary(conclusionCounts, report.combos.length)}
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-6">
                  {(["成立", "不成立", "证据不足"] as const).map((label) => (
                    <div key={label} className="flex items-center gap-2">
                      <Badge variant={conclusionVariant(label)} className="px-3 py-1 text-sm">
                        {label}
                      </Badge>
                      <span className="text-2xl font-semibold">
                        {conclusionCounts[label] ?? 0}
                      </span>
                      <span className="text-sm text-muted-foreground">种组合</span>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                  判定规则（随报告披露）：评估段不足 3 年或完成交易不足 3 笔 → 证据不足；样本外总超额
                  &gt; 0 且跑赢年份过半 → 成立；否则 → 不成立。
                  用白话说：证据不足＝交易太少，不敢下结论；不成立＝证据够了，而且确实跑输。
                </p>
              </section>

              {/* 6 种组合完整结果 */}
              <section>
                <h3 className="mb-3 text-base font-semibold">六种预设组合结果（全部列示）</h3>
                <div className="overflow-x-auto rounded-2xl border border-border/60">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-muted-foreground">
                        <th className="px-3 py-2.5 font-medium">回撤阈值</th>
                        <th className="px-3 py-2.5 font-medium">持有期</th>
                        <th className="px-3 py-2.5 font-medium">
                          策略收益
                          <HeaderNote>按规则买卖最后赚/亏多少</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          基准收益（买入持有）
                          <HeaderNote>同一只基金买入后一直持有不动的收益</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          超额
                          <HeaderNote>策略比买入持有多赚或少赚的百分点，负数就是跑输</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          策略最大回撤
                          <HeaderNote>期间从最高点跌下来的最大幅度</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          策略波动率
                          <HeaderNote>涨跌晃动的剧烈程度，越大越颠簸</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">完成交易</th>
                        <th className="px-3 py-2.5 font-medium">结论</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.combos.map((c, i) => (
                        <tr
                          key={`${c.threshold}-${c.hold_months}`}
                          onClick={() => setSelectedCombo(i)}
                          className={`cursor-pointer border-t border-border/60 transition-colors hover:bg-muted/40 ${
                            i === selectedCombo ? "bg-muted/60" : ""
                          }`}
                        >
                          <td className="px-3 py-2.5">{pctPlain(c.threshold)}</td>
                          <td className="px-3 py-2.5">{c.hold_months} 个月</td>
                          <td className={`px-3 py-2.5 ${returnClass(c.total_return)}`}>
                            {formatPercent(c.total_return)}
                          </td>
                          <td className={`px-3 py-2.5 ${returnClass(c.benchmark_return)}`}>
                            {formatPercent(c.benchmark_return)}
                          </td>
                          <td className={`px-3 py-2.5 ${returnClass(c.excess_return)}`}>
                            {formatPercent(c.excess_return)}
                          </td>
                          <td className="px-3 py-2.5">{pctPlain(c.max_drawdown)}</td>
                          <td className="px-3 py-2.5">{pctPlain(c.volatility)}</td>
                          <td className="px-3 py-2.5">{c.completed_trades} 笔</td>
                          <td className="px-3 py-2.5">
                            <Badge variant={conclusionVariant(c.conclusion)}>{c.conclusion}</Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  点击任意一行，在下方查看该组合的逐年表现、权益曲线与交易明细。
                </p>
              </section>

              {combo && (
                <>
                  {/* 选中组合结论 */}
                  <section className="rounded-2xl border border-border/60 p-5">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="text-base font-semibold">
                        组合：回撤 {pctPlain(combo.threshold)} 触发 / 持有 {combo.hold_months} 个月
                      </h3>
                      <Badge variant={conclusionVariant(combo.conclusion)} className="px-3 py-1 text-sm">
                        {combo.conclusion}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {combo.conclusion_reason}
                    </p>
                    <p className="mt-2 text-sm text-muted-foreground">
                      失效年份（策略跑输买入持有的年份）：
                      {combo.failed_years.length > 0 ? combo.failed_years.join("、") : "无"}
                    </p>
                  </section>

                  {/* 权益曲线 */}
                  {chartData.length > 0 && (
                    <section>
                      <h3 className="mb-3 text-base font-semibold">
                        样本外权益曲线（月末值，期初归一化为 1）
                      </h3>
                      <div className="h-72 rounded-2xl border border-border/60 p-3">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3} />
                            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
                            <YAxis
                              tick={{ fontSize: 11 }}
                              tickFormatter={(v: number) => v.toFixed(2)}
                              domain={["auto", "auto"]}
                            />
                            <Tooltip
                              formatter={(value, name) => [
                                typeof value === "number" ? value.toFixed(4) : "—",
                                name === "strategy" ? "策略" : "基准（买入持有）",
                              ]}
                            />
                            <Legend
                              formatter={(value: string) =>
                                value === "strategy" ? "策略" : "基准（买入持有）"
                              }
                            />
                            <Line type="monotone" dataKey="strategy" stroke="#0071e3" dot={false} strokeWidth={1.8} />
                            <Line type="monotone" dataKey="benchmark" stroke="#ff9500" dot={false} strokeWidth={1.8} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                        两条线都是 1 元本金的走势：橙线是买入持有，蓝线是按规则买卖；蓝线在橙线下面，就是规则跑输了。
                      </p>
                    </section>
                  )}

                  {/* 逐年对比 */}
                  <section>
                    <h3 className="mb-3 text-base font-semibold">逐年对比（样本外）</h3>
                    <div className="overflow-x-auto rounded-2xl border border-border/60">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-muted-foreground">
                            <th className="px-3 py-2.5 font-medium">年份</th>
                            <th className="px-3 py-2.5 font-medium">策略收益</th>
                            <th className="px-3 py-2.5 font-medium">
                              基准收益（买入持有）
                              <HeaderNote>同一年买入持有不动的收益</HeaderNote>
                            </th>
                            <th className="px-3 py-2.5 font-medium">
                              超额
                              <HeaderNote>策略比买入持有多赚或少赚，负数就是跑输</HeaderNote>
                            </th>
                            <th className="px-3 py-2.5 font-medium">
                              策略最大回撤
                              <HeaderNote>当年从最高点跌下来的最大幅度</HeaderNote>
                            </th>
                            <th className="px-3 py-2.5 font-medium">
                              策略波动率
                              <HeaderNote>涨跌晃动的剧烈程度</HeaderNote>
                            </th>
                            <th className="px-3 py-2.5 font-medium">
                              是否跑输
                              <HeaderNote>跑输的年份就叫失效年份</HeaderNote>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {combo.yearly.map((row) => (
                            <tr key={row.year} className="border-t border-border/60">
                              <td className="px-3 py-2.5">{row.year}</td>
                              <td className={`px-3 py-2.5 ${returnClass(row.strategy_return)}`}>
                                {formatPercent(row.strategy_return)}
                              </td>
                              <td className={`px-3 py-2.5 ${returnClass(row.benchmark_return)}`}>
                                {formatPercent(row.benchmark_return)}
                              </td>
                              <td className={`px-3 py-2.5 ${returnClass(row.excess_return)}`}>
                                {formatPercent(row.excess_return)}
                              </td>
                              <td className="px-3 py-2.5">{pctPlain(row.strategy_max_drawdown)}</td>
                              <td className="px-3 py-2.5">{pctPlain(row.strategy_volatility)}</td>
                              <td className="px-3 py-2.5">
                                {row.failed ? (
                                  <span className="text-negative">是（失效年份）</span>
                                ) : (
                                  "否"
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>

                  {/* 交易明细 */}
                  <section>
                    <h3 className="mb-1.5 text-base font-semibold">交易明细</h3>
                    <p className="mb-3 text-sm leading-relaxed text-muted-foreground">
                      这是完整账本：每笔买卖的日期、价格、费用都在这里，可抽查任意一笔核对。
                    </p>
                    {combo.trades.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        样本外段内从未触发该组合的阈值，全程持有现金。
                      </p>
                    ) : (
                      <div className="overflow-x-auto rounded-2xl border border-border/60">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-left text-muted-foreground">
                              <th className="px-3 py-2.5 font-medium">触发买入日</th>
                              <th className="px-3 py-2.5 font-medium">买入净值</th>
                              <th className="px-3 py-2.5 font-medium">卖出日</th>
                              <th className="px-3 py-2.5 font-medium">卖出净值</th>
                              <th className="px-3 py-2.5 font-medium">持有天数</th>
                              <th className="px-3 py-2.5 font-medium">买入费</th>
                              <th className="px-3 py-2.5 font-medium">卖出费</th>
                              <th className="px-3 py-2.5 font-medium">本笔收益</th>
                              <th className="px-3 py-2.5 font-medium">状态</th>
                            </tr>
                          </thead>
                          <tbody>
                            {combo.trades.map((t, i) => (
                              <tr key={`${t.buy_date}-${i}`} className="border-t border-border/60">
                                <td className="px-3 py-2.5">{t.buy_date}</td>
                                <td className="px-3 py-2.5">{t.buy_nav.toFixed(4)}</td>
                                <td className="px-3 py-2.5">{t.sell_date ?? "—"}</td>
                                <td className="px-3 py-2.5">
                                  {t.sell_nav != null ? t.sell_nav.toFixed(4) : "—"}
                                </td>
                                <td className="px-3 py-2.5">{t.holding_days ?? "—"}</td>
                                <td className="px-3 py-2.5">¥{t.buy_fee.toFixed(2)}</td>
                                <td className="px-3 py-2.5">
                                  {t.sell_fee != null ? `¥${t.sell_fee.toFixed(2)}` : "—"}
                                </td>
                                <td className={`px-3 py-2.5 ${returnClass(t.return_pct)}`}>
                                  {formatPercent(t.return_pct)}
                                </td>
                                <td className="px-3 py-2.5">{t.open ? "未平仓" : "已完成"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                </>
              )}
            </>
          )}

          {/* 基准说明 */}
          <section className="flex max-w-4xl items-start gap-2.5 rounded-2xl bg-muted/40 p-4 text-sm">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <p className="leading-relaxed text-muted-foreground">
              基准说明：主基准为买入并持有同一只基金（只在买入时扣一次申购费，期末仍持有、未扣赎回费）。
              指数多为价格口径、不含分红收益，用作基准会系统性低估基准表现，因此不作为主基准，仅作背景参考。
            </p>
          </section>

          {/* 披露块（引擎原文全量列示） */}
          <section>
            <h3 className="mb-1.5 text-base font-semibold">披露与局限</h3>
            <p className="mb-3 max-w-4xl text-sm leading-relaxed text-muted-foreground">
              这是这份报告的假设与局限清单：费用是假设值、已清盘基金的数据不在内、历史不代表未来。
            </p>
            <ul className="max-w-4xl list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
              {report.disclosures.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
