"use client";

import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, ChevronDown, History, Search } from "lucide-react";
import {
  FrequencyStat,
  HistoryFrequencyReport,
  getHistoryFrequencyReport,
  plainHistoryFrequencySummary,
} from "@/services/fund";
import { YearlyFrequencyChart } from "@/components/yearly-frequency-chart";
import { useFundSearch } from "@/hooks/use-fund-search";

/**
 * 披露分层（只改呈现，不删改任何一条原文）：正文只留会改变决定的 3 条——
 * 历史≠未来、净值不含费、重叠起点不算独立样本；其余折叠进“完整披露”展开区，
 * 展开后连同正文 3 条共 N 条全量可达。按关键词识别，识别不到的一律进展开区。
 */
const KEY_DISCLOSURE_PATTERNS: RegExp[] = [/不代表未来/, /不含申购/, /重叠起点/];

function splitDisclosures(disclosures: string[]): { key: string[]; rest: string[] } {
  const key: string[] = [];
  const rest: string[] = [];
  for (const d of disclosures) {
    if (KEY_DISCLOSURE_PATTERNS.some((p) => p.test(d))) key.push(d);
    else rest.push(d);
  }
  return { key, rest };
}

/** 无正负号的百分比（频率用，与后端小数口径一致）。 */
function pctPlain(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

/** 表头下方的白话小字注释：给第一次看的人解释术语，不改变任何数字口径。 */
function HeaderNote({ children }: { children: ReactNode }) {
  return (
    <span className="mt-0.5 block text-[11px] font-normal leading-snug text-muted-foreground/75">
      {children}
    </span>
  );
}

function freqCell(stat: FrequencyStat | null | undefined): string {
  if (!stat || stat.freq == null) return "—";
  return pctPlain(stat.freq);
}

export default function HistoryFrequencyPage() {
  const [query, setQuery] = useState("");
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<HistoryFrequencyReport | null>(null);
  const [showAllDisclosures, setShowAllDisclosures] = useState(false);

  // 搜索建议走全站共享 hook（失败时返回空，绝不编造候选基金）
  const { suggestions } = useFundSearch(query);

  const runQuery = async (rawCode: string) => {
    const code = rawCode.trim().toUpperCase();
    if (!code || loading) return;
    setLoading(true);
    setError(null);
    setReport(null);
    setSuggestOpen(false);
    try {
      const result = await getHistoryFrequencyReport(code);
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "历史频率请求失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const payback = report?.payback_5pct ?? null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Header */}
      <section className="mb-8">
        <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight">
          <History className="h-6 w-6" />
          历史频率
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          这只基金过去的日子是怎么过的？本页的做法是：把过去每一个交易日都假装成
          “就在那天买入”，然后数之后 6 个月、12 个月里发生了什么——赚钱的占多少，
          一年内跌超 5% / 10% / 15% 的占多少，跌破 5% 后多久能回本。
          所有数字都是对已经发生过的历史的计数，只描述过去，
          不对未来做任何判断，不提供买卖意见。
        </p>
        <p className="mt-3 max-w-3xl rounded-xl bg-muted/40 px-3.5 py-2.5 text-sm leading-relaxed text-muted-foreground">
          怎么看这页：① 先看白话结论 ② 再看「12 个月内跌超 10%」那一行，对照自己的承受线
          ③ 想看年份差别，先看逐年柱状图再对逐年表——好年景和坏年景差别很大，别只看总数。
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
                  if (e.key === "Enter") runQuery(query);
                }}
                placeholder="输入基金代码或名称，如 161725"
                className="pl-9"
              />
            </div>
            <Button onClick={() => runQuery(query)} disabled={loading || !query.trim()}>
              {loading ? "统计中…" : "查看历史频率"}
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
                    runQuery(fund.code);
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
            正在拉取全程历史净值并统计，冷启动时可能需要几十秒…
          </div>
        )}
        {error && (
          <div className="mt-6 flex max-w-3xl items-start gap-2.5 rounded-2xl border border-negative/30 bg-negative/5 p-4 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-negative" />
            <div>
              <div className="font-medium text-negative">历史频率没能完成</div>
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
                ；起点数：6 个月统计 {report.origins_6m} 个、12 个月统计 {report.origins_12m} 个
                {report.dropped_rows > 0 &&
                  `；已剔除 ${report.dropped_rows} 条无效净值记录（缺失或非正），未做任何插值或替代`}
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
              {report.evidence === "不足" && (
                <section className="flex max-w-3xl items-start gap-2.5 rounded-2xl border border-warning/40 bg-warning/5 p-4">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                  <div>
                    <div className="text-base font-semibold">证据不足</div>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                      {report.evidence_reason}
                    </p>
                  </div>
                </section>
              )}

              {/* 白话结论 */}
              <section className="rounded-2xl border border-border/60 p-5">
                <h3 className="text-sm font-medium text-muted-foreground">
                  白话结论（只复述数字，不加判断）
                </h3>
                <p className="mt-2.5 text-base font-medium leading-relaxed">
                  {plainHistoryFrequencySummary(report)}
                </p>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                  读法提醒：频率是“过去这么多起点里占多少”，不是“接下来会怎样的把握”。
                  同一个数字，对能承受 10% 跌幅的人和不能承受的人，含义完全不同。
                </p>
              </section>

              {/* 全程频率表 */}
              <section>
                <h3 className="mb-3 text-base font-semibold">全程频率（全部起点）</h3>
                <div className="overflow-x-auto rounded-2xl border border-border/60">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-muted-foreground">
                        <th className="px-3 py-2.5 font-medium">统计项</th>
                        <th className="px-3 py-2.5 font-medium">
                          频率
                          <HeaderNote>符合条件的起点占全部起点的比例</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          起点数
                          <HeaderNote>符合条件的起点数 / 全部起点数</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">白话解释</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-border/60">
                        <td className="px-3 py-2.5">之后 6 个月赚钱</td>
                        <td className="px-3 py-2.5">{freqCell(report.positive_6m)}</td>
                        <td className="px-3 py-2.5">
                          {report.positive_6m ? `${report.positive_6m.count} / ${report.positive_6m.n}` : "—"}
                        </td>
                        <td className="px-3 py-2.5 text-muted-foreground">
                          持有 6 个月后净值高于起点的起点占比
                        </td>
                      </tr>
                      <tr className="border-t border-border/60">
                        <td className="px-3 py-2.5">之后 12 个月赚钱</td>
                        <td className="px-3 py-2.5">{freqCell(report.positive_12m)}</td>
                        <td className="px-3 py-2.5">
                          {report.positive_12m ? `${report.positive_12m.count} / ${report.positive_12m.n}` : "—"}
                        </td>
                        <td className="px-3 py-2.5 text-muted-foreground">
                          持有 12 个月后净值高于起点的起点占比
                        </td>
                      </tr>
                      {(["5", "10", "15"] as const).map((key) => (
                        <tr key={key} className="border-t border-border/60">
                          <td className="px-3 py-2.5">12 个月内跌超 {key}%</td>
                          <td className="px-3 py-2.5">
                            {freqCell(report.drawdown_exceed_12m[key])}
                          </td>
                          <td className="px-3 py-2.5">
                            {report.drawdown_exceed_12m[key]
                              ? `${report.drawdown_exceed_12m[key].count} / ${report.drawdown_exceed_12m[key].n}`
                              : "—"}
                          </td>
                          <td className="px-3 py-2.5 text-muted-foreground">
                            一年里至少有一次从高点跌超 {key}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {report.drawdown_exceed_12m["5"]?.freq === 1 && (
                  <p className="mt-3 max-w-4xl rounded-xl bg-muted/40 px-3.5 py-2.5 text-sm leading-relaxed">
                    为什么「12 个月内跌超 5%」是 100.00%？不是算错：这只基金波动较大，
                    过去每一个能看满一年的起点，之后一年里都至少有一次跌超 5%——
                    这是数出来的结果，不表示未来一年也一定会跌。
                  </p>
                )}
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  起点说明：起点是每个交易日（12 个月统计共 {report.origins_12m} 个），
                  相邻窗口高度重叠，n 不是独立样本数；不重叠的 12 个月段只有{" "}
                  {report.non_overlapping_blocks_12m} 段。别把 n 当成独立证据的多少。
                </p>
              </section>

              {/* 回本分布 */}
              {payback && (
                <section className="rounded-2xl border border-border/60 p-5">
                  <h3 className="text-base font-semibold">跌破 5% 后回本要多久</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    先对一下总数：这一段的起点和上面频率表不是同一批——回本要往后看两年，
                    所以这里用全部 {payback.origins} 个交易日当起点；上面的表只数能看满
                    12 个月的 {report.origins_12m} 个起点。两个总数不一样，是数的范围不同，
                    不是算错。
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    跌破 5% 指净值首次跌到决策日净值的 95% 以下；回本天数从决策日那天起算
                    （含跌下去的过程），不是从跌破那天起算。在全部 {payback.origins} 个起点里，
                    跌破 5% 的共 {payback.events} 个，其中 {payback.recovered} 个在两年内回本，
                    {payback.unrecovered} 个两年内没回本。
                  </p>
                  {payback.evidence === "不足" ? (
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      跌破 5% 的事件只有 {payback.events} 个，不足 30 个，不报回本中位数——
                      样本太少，报了会误导。
                    </p>
                  ) : (
                    <div className="mt-4 flex flex-wrap gap-6">
                      <div>
                        <div className="text-sm text-muted-foreground">回本中位数（交易日）</div>
                        <div className="mt-1 text-2xl font-semibold">
                          {payback.median_days != null ? `${Math.round(payback.median_days)} 天` : "—"}
                        </div>
                        {payback.median_days != null && (
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            交易日，约合 {Math.max(1, Math.round(payback.median_days / 21))} 个月
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">
                          跌破 5% 后两年内没回本的起点
                        </div>
                        <div className="mt-1 text-2xl font-semibold">
                          {pctPlain(payback.unrecovered_share)}
                        </div>
                        <div className="mt-0.5 text-xs text-muted-foreground">
                          {payback.unrecovered} / {payback.events} 个跌破事件
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">75% 的起点在几天内回本</div>
                        <div className="mt-1 text-2xl font-semibold">
                          {payback.p75_days != null ? `${Math.round(payback.p75_days)} 天` : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-muted-foreground">90% 的起点在几天内回本</div>
                        <div className="mt-1 text-2xl font-semibold">
                          {payback.p90_days != null ? `${Math.round(payback.p90_days)} 天` : "—"}
                        </div>
                      </div>
                    </div>
                  )}
                  <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                    天数是交易日，不是自然日；“两年内没回本”含窗口被数据末尾截断的起点。
                  </p>
                </section>
              )}

              {/* 逐年表 */}
              <section>
                <h3 className="mb-3 text-base font-semibold">逐年表（按起点年份分组）</h3>
                <p className="mb-2 max-w-4xl text-sm leading-relaxed text-muted-foreground">
                  先看图：每一根柱子是「那一年买入、拿满 12 个月后赚钱」的起点占比。
                  年份之间差这么多——只看全程总数，会把好年景和坏年景混在一起。
                </p>
                <div className="mb-4 h-56 rounded-2xl border border-border/60 p-3">
                  <YearlyFrequencyChart data={report.yearly} />
                </div>
                <div className="overflow-x-auto rounded-2xl border border-border/60">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-muted-foreground">
                        <th className="px-3 py-2.5 font-medium">年份</th>
                        <th className="px-3 py-2.5 font-medium">起点数</th>
                        <th className="px-3 py-2.5 font-medium">
                          12 个月赚钱
                          <HeaderNote>该年起点里持有 12 个月后赚钱的占比</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          一年内跌超 10%
                          <HeaderNote>该年起点里一年内至少跌超 10% 的占比</HeaderNote>
                        </th>
                        <th className="px-3 py-2.5 font-medium">
                          这一年的数据够不够
                          <HeaderNote>该年起点不足 30 个时，数字只能参考，不能下结论</HeaderNote>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.yearly.map((row) => (
                        <tr key={row.year} className="border-t border-border/60">
                          <td className="px-3 py-2.5">{row.year}</td>
                          <td className="px-3 py-2.5">{row.n}</td>
                          <td className="px-3 py-2.5">{freqCell(row.positive_12m)}</td>
                          <td className="px-3 py-2.5">{freqCell(row.drawdown_gt_10pct)}</td>
                          <td className="px-3 py-2.5">
                            {row.evidence === "足" ? (
                              "够用"
                            ) : (
                              <Badge variant="warning">太少，只能参考</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  总频率会掩盖年份差别：有的年份几乎全赚，有的年份几乎全亏。只看总数，等于把好年景和坏年景混在一起算平均。
                </p>
              </section>
            </>
          )}

          {/* 披露块：正文只留会改变决定的 3 条，其余折叠进“完整披露”，原文一条不删 */}
          {(() => {
            const { key: keyDisclosures, rest: restDisclosures } = splitDisclosures(
              report.disclosures
            );
            return (
              <section>
                <h3 className="mb-1.5 text-base font-semibold">披露与局限</h3>
                <p className="mb-3 max-w-4xl text-sm leading-relaxed text-muted-foreground">
                  先看最重要的 3 条：历史不代表未来、净值口径不含费、已清盘基金的数据不在内。
                </p>
                <ul className="max-w-4xl list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
                  {keyDisclosures.map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
                {restDisclosures.length > 0 && (
                  <div className="mt-4 max-w-4xl">
                    <button
                      type="button"
                      onClick={() => setShowAllDisclosures((v) => !v)}
                      aria-expanded={showAllDisclosures}
                      className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground"
                    >
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${showAllDisclosures ? "rotate-180" : ""}`}
                      />
                      完整披露（其余 {restDisclosures.length} 条，
                      {showAllDisclosures ? "收起" : "展开看"}；连同上面 {keyDisclosures.length}{" "}
                      条共 {report.disclosures.length} 条，一条不少）
                    </button>
                    {showAllDisclosures && (
                      <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
                        {restDisclosures.map((d, i) => (
                          <li key={i}>{d}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </section>
            );
          })()}
        </div>
      )}
    </div>
  );
}
