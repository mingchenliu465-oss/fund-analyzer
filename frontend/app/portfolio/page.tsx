"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import {
  Briefcase,
  TrendingUp,
  Plus,
  Trash2,
  DollarSign,
  Edit3,
  History,
  Layers,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { TradeModal } from "@/components/trade-modal";
import { useFundSearch } from "@/hooks/use-fund-search";
import {
  HoldingItem,
  HoldingCreate,
  SellFormData,
  RealPortfolioSummary,
  PortfolioHistoryPoint,
  PortfolioHistoryPeriod,
  AttributionResult,
  getRealPortfolio,
  getAllHoldings,
  getPortfolioHistory,
  getPortfolioAttribution,
  autoDrip,
  createHolding,
  sellHolding,
  deleteHolding,
  updateHolding,
} from "@/services/fund";

type Tab = "active" | "sold";

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<RealPortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("active");
  const [soldHoldings, setSoldHoldings] = useState<HoldingItem[]>([]);

  // Modal state
  const [modal, setModal] = useState<{
    type: "sell" | "edit";
    holding: HoldingItem;
  } | null>(null);

  // Form state
  const [query, setQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const { suggestions: fundSuggestions } = useFundSearch(query, 5);
  const suggestions = fundSuggestions.map(({ code, name, type }) => ({ code, name, type }));
  const [form, setForm] = useState<HoldingCreate>({
    fund_code: "",
    fund_name: "",
    fund_type: "",
    buy_date: "",
    buy_amount: 0,
    buy_nav: 0,
    shares: 0,
    fee: undefined,
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);

  // 添加模式：单笔 / 自动定投
  const [formMode, setFormMode] = useState<"single" | "drip">("single");
  const [drip, setDrip] = useState({
    amount: 1000,
    frequency: "monthly" as "daily" | "weekly" | "monthly",
    start_date: "",
    end_date: "",
    day_of_week: 1,
    fee: 0,
  });

  // 页面级错误（区分“加载失败”与“暂无持仓”）与操作反馈
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // 资产历史走势状态
  const [historyPeriod, setHistoryPeriod] = useState<PortfolioHistoryPeriod>("1M");
  const [historyData, setHistoryData] = useState<PortfolioHistoryPoint[]>([]);
  const [historyView, setHistoryView] = useState<"value" | "rate">("value");

  // 今日收益归因状态
  const [attribution, setAttribution] = useState<AttributionResult | null>(null);
  const skippedInitialHistoryRefresh = useRef(false);
  const skippedInitialAttributionRefresh = useRef(false);

  const fetchPortfolio = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getRealPortfolio().catch(() => null),
      getAllHoldings().catch(() => [] as HoldingItem[]),
    ]).then(([summary, all]) => {
      if (summary) {
        setPortfolio(summary);
      } else {
        setError("加载持仓失败：请确认后端服务已启动（默认 http://localhost:8000）。");
      }
      setSoldHoldings(all.filter((h) => h.is_sold));
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(fetchPortfolio, 0);
    return () => window.clearTimeout(timer);
  }, [fetchPortfolio]);

  // 拉取资产历史走势（周期切换或持仓变化后刷新）
  useEffect(() => {
    // The initial request already starts on mount. Do not repeat it when the
    // portfolio summary arrives a moment later.
    if (portfolio && !skippedInitialHistoryRefresh.current) {
      skippedInitialHistoryRefresh.current = true;
      return;
    }
    getPortfolioHistory(historyPeriod).then(setHistoryData);
  }, [historyPeriod, portfolio]);

  // 拉取今日收益归因（持仓变化后刷新）
  useEffect(() => {
    if (portfolio && !skippedInitialAttributionRefresh.current) {
      skippedInitialAttributionRefresh.current = true;
      return;
    }
    getPortfolioAttribution().then((r) => setAttribution(r));
  }, [portfolio]);

  // 操作反馈自动消失
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  // Auto-fill form from search selection
  const selectFund = (s: { code: string; name: string; type: string }) => {
    setForm((f) => ({
      ...f,
      fund_code: s.code,
      fund_name: s.name,
      fund_type: s.type,
    }));
    setQuery(s.name);
    setShowSuggestions(false);
  };

  // 自动定投提交
  const handleDrip = async () => {
    if (!form.fund_code || !drip.start_date || !drip.end_date || drip.amount <= 0) {
      setNotice({ type: "error", text: "请选择基金并填写定投金额、起止日期" });
      return;
    }
    if (drip.start_date > drip.end_date) {
      setNotice({ type: "error", text: "起始日期不能晚于截止日期" });
      return;
    }
    if (drip.frequency === "weekly" && (drip.day_of_week < 1 || drip.day_of_week > 7)) {
      setNotice({ type: "error", text: "每周定投请选择周一至周日（1–7）" });
      return;
    }
    if (drip.frequency === "monthly" && (drip.day_of_week < 1 || drip.day_of_week > 31)) {
      setNotice({ type: "error", text: "每月定投日期必须在 1–31 之间" });
      return;
    }
    setSubmitting(true);
    setNotice(null);
    try {
      const res = await autoDrip({
        fund_code: form.fund_code,
        fund_name: form.fund_name,
        fund_type: form.fund_type,
        amount: drip.amount,
        frequency: drip.frequency,
        start_date: drip.start_date,
        end_date: drip.end_date,
        day_of_week: drip.day_of_week,
        fee: drip.fee,
        notes: `自动定投 ${
          drip.frequency === "monthly" ? "月" : drip.frequency === "weekly" ? "周" : "日"
        }`,
      });
      if (res.created > 0) {
        setNotice({
          type: "success",
          text: `定投已生成 ${res.created} 条持仓记录`,
        });
      } else {
        setNotice({
          type: "error",
          text: res.skipped?.[0]?.reason ?? "定投未能生成记录，请检查日期范围",
        });
      }
      resetForm();
      fetchPortfolio();
    } catch (err) {
      console.error(err);
      setNotice({
        type: "error",
        text: err instanceof Error ? `定投失败：${err.message}` : "定投失败，请稍后重试",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleAdd = async () => {
    const invalid = validateForm(form);
    if (invalid) {
      setNotice({ type: "error", text: invalid });
      return;
    }
    setSubmitting(true);
    setNotice(null);
    try {
      await createHolding(form);
      setNotice({ type: "success", text: "持仓已添加成功" });
      setShowForm(false);
      resetForm();
      fetchPortfolio();
    } catch (err) {
      console.error(err);
      setNotice({
        type: "error",
        text: err instanceof Error ? `添加失败：${err.message}` : "添加失败，请稍后重试",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setForm({
      fund_code: "",
      fund_name: "",
      fund_type: "",
      buy_date: "",
      buy_amount: 0,
      buy_nav: 0,
      shares: 0,
      fee: undefined,
      notes: "",
    });
    setQuery("");
  };

  // 新增持仓前的本地校验，与后端 HoldingCreate 校验保持一致
  const validateForm = (f: HoldingCreate): string | null => {
    if (!f.fund_code.trim()) return "请先搜索并选择基金";
    if (!f.buy_date) return "请选择买入日期";
    if (f.buy_amount <= 0) return "买入金额必须大于 0";
    if (f.buy_nav <= 0) return "买入净值必须大于 0";
    if (f.shares <= 0) return "买入份额必须大于 0";
    return null;
  };

  const handleConfirmSell = async (id: number, data: SellFormData) => {
    setNotice(null);
    try {
      await sellHolding(id, data);
      setNotice({ type: "success", text: "已卖出持仓" });
      setModal(null);
      fetchPortfolio();
    } catch (err) {
      console.error(err);
      setNotice({
        type: "error",
        text: err instanceof Error ? `卖出失败：${err.message}` : "卖出失败，请稍后重试",
      });
    }
  };

  const handleConfirmEdit = async (id: number, data: HoldingCreate) => {
    setNotice(null);
    try {
      await updateHolding(id, data);
      setNotice({ type: "success", text: "持仓已更新" });
      setModal(null);
      fetchPortfolio();
    } catch (err) {
      console.error(err);
      setNotice({
        type: "error",
        text: err instanceof Error ? `保存失败：${err.message}` : "保存失败，请稍后重试",
      });
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确认删除此持仓记录？")) return;
    setNotice(null);
    try {
      await deleteHolding(id);
      setNotice({ type: "success", text: "持仓已删除" });
      fetchPortfolio();
    } catch (err) {
      console.error(err);
      setNotice({
        type: "error",
        text: err instanceof Error ? `删除失败：${err.message}` : "删除失败，请稍后重试",
      });
    }
  };

  // ── Derived data ──

  const activeHoldings = (portfolio?.holdings ?? []).filter((h) => !h.is_sold);

  const totalValue = portfolio?.total_value ?? 0;
  const totalCost = portfolio?.total_cost ?? 0;
  const totalProfit = portfolio?.total_profit ?? 0;
  const isUp = totalProfit >= 0;

  if (loading)
    return (
      <div className="mx-auto max-w-6xl px-6 py-20 text-center text-muted-foreground">
        加载中…
      </div>
    );

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Error banner（后端不可达 / 加载失败） */}
      {error && (
        <div className="mb-6 flex items-center justify-between rounded-2xl border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
          <span>{error}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchPortfolio}
            className="ml-4 h-8 rounded-lg text-xs"
          >
            重试
          </Button>
        </div>
      )}
      {portfolio?.has_stale_nav && !error && (
        <div className="mb-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-300">
          部分持仓的最新净值暂不可用，当前市值使用最近有效净值或买入净值估算，待数据更新后会自动刷新。
        </div>
      )}

      {/* 操作反馈 */}
      {notice && (
        <div
          className={`mb-6 rounded-2xl border px-4 py-3 text-sm ${
            notice.type === "success"
              ? "border-positive/30 bg-positive/10 text-positive"
              : "border-negative/30 bg-negative/10 text-negative"
          }`}
        >
          {notice.text}
        </div>
      )}

      {/* Header */}
      <section className="mb-8">
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="text-3xl font-semibold tracking-tight sm:text-4xl"
        >
          我的持仓
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="mt-2 text-muted-foreground"
        >
          手动录入真实交易，实时计算持仓盈亏
        </motion.p>
      </section>

      {/* Asset history chart */}
      <section className="mb-8">
        <div className="rounded-2xl border border-border bg-background p-4 sm:p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold tracking-tight">资产走势</h2>
              <p className="text-xs text-muted-foreground">
                {historyView === "value"
                  ? "总资产变化（每日记录快照）"
                  : "收益率 =（当前资产 − 累计成本）/ 累计成本"}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex gap-1 rounded-xl border border-border bg-muted/40 p-1">
                {(
                  [
                    ["1W", "1周"],
                    ["1M", "1月"],
                    ["3M", "3月"],
                    ["1Y", "1年"],
                    ["ALL", "全部"],
                  ] as [PortfolioHistoryPeriod, string][]
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setHistoryPeriod(key)}
                    className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                      historyPeriod === key
                        ? "bg-background shadow-sm text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div className="flex gap-1 rounded-xl border border-border bg-muted/40 p-1">
                <button
                  onClick={() => setHistoryView("value")}
                  className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                    historyView === "value"
                      ? "bg-background shadow-sm text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  总资产
                </button>
                <button
                  onClick={() => setHistoryView("rate")}
                  className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                    historyView === "rate"
                      ? "bg-background shadow-sm text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  收益率
                </button>
              </div>
            </div>
          </div>

          {historyData.length > 0 ? (
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={historyData} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
                  <defs>
                    <linearGradient id="portfolioValueFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0071e3" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="#0071e3" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                    minTickGap={24}
                    dy={8}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                    tickFormatter={(v) =>
                      historyView === "value"
                        ? `¥${Number(v).toLocaleString()}`
                        : `${Number(v).toFixed(1)}%`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--background)",
                      border: "1px solid var(--border)",
                      borderRadius: "12px",
                      boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                    }}
                    labelStyle={{ color: "var(--muted-foreground)", fontSize: 12 }}
                    itemStyle={{ fontSize: 13 }}
                    formatter={(value) =>
                      historyView === "value"
                        ? [`¥${Number(value).toLocaleString()}`, "总资产"]
                        : [`${Number(value).toFixed(2)}%`, "收益率"]
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey={historyView === "value" ? "total_value" : "profit_rate"}
                    stroke="#0071e3"
                    strokeWidth={2}
                    fill="url(#portfolioValueFill)"
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0, fill: "#0071e3" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex h-[240px] flex-col items-center justify-center text-center text-sm text-muted-foreground">
              <p>暂无历史数据</p>
              <p className="mt-1 text-xs">历史自今日开始记录，明天起这里会展示你的资产变化曲线。</p>
            </div>
          )}
        </div>
      </section>

      {/* Summary cards — only show active holdings */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="持仓市值"
          value={`¥${totalValue.toLocaleString()}`}
          icon={Briefcase}
          delay={0.1}
        />
        <MetricCard
          title="累计成本"
          value={`¥${totalCost.toLocaleString()}`}
          icon={DollarSign}
          delay={0.15}
        />
        <MetricCard
          title="浮动盈亏"
          value={`¥${totalProfit.toLocaleString()}`}
          trend={isUp ? "up" : "down"}
          trendValue={`${isUp ? "+" : ""}${(portfolio?.total_profit_pct ?? 0).toFixed(2)}%`}
          icon={TrendingUp}
          delay={0.2}
        />
        <MetricCard
          title="持仓数量"
          value={`${activeHoldings.length} 只`}
          icon={Layers}
          delay={0.25}
        />
      </div>

      {/* 今日收益分析 */}
      <section className="mb-8">
        <div className="rounded-2xl border border-border bg-background p-4 sm:p-5">
          <div className="mb-4">
            <h2 className="text-base font-semibold tracking-tight">今日收益分析</h2>
            <p className="text-xs text-muted-foreground">看看今天收益来自哪里</p>
          </div>

          {attribution && attribution.contributions.length > 0 ? (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-4 rounded-xl border border-border bg-muted/30 p-4">
                <div>
                  <div className="text-xs text-muted-foreground">今日收益</div>
                  <div
                    className={`text-2xl font-semibold tabular-nums ${
                      attribution.today_return >= 0 ? "text-positive" : "text-negative"
                    }`}
                  >
                    {attribution.today_return >= 0 ? "+" : ""}¥
                    {attribution.today_return.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">今日收益率</div>
                  <div
                    className={`text-2xl font-semibold tabular-nums ${
                      attribution.today_return_pct >= 0 ? "text-positive" : "text-negative"
                    }`}
                  >
                    {attribution.today_return_pct >= 0 ? "+" : ""}
                    {attribution.today_return_pct.toFixed(2)}%
                  </div>
                </div>
                <div className="ml-auto max-w-[200px] text-right text-[11px] text-muted-foreground">
                  {attribution.summary.note}
                  {attribution.summary.has_stale_nav && <div>部分行情待更新，收益仅含可用行情</div>}
                </div>
              </div>

              <div className="space-y-2">
                {attribution.contributions.map((c, i) => {
                  const isTop = c.contribution > 0 && i === 0;
                  const isBottom =
                    c.contribution < 0 && i === attribution.contributions.length - 1;
                  return (
                    <div
                      key={c.fund_code}
                      className={`flex items-center justify-between rounded-xl border p-3 ${
                        isTop
                          ? "border-positive/40 bg-positive/5"
                          : isBottom
                            ? "border-negative/40 bg-negative/5"
                            : "border-border"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">{c.fund_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {c.fund_code} · {c.shares.toLocaleString()} 份 · 涨跌{" "}
                          {c.change_pct >= 0 ? "+" : ""}
                          {c.change_pct}%
                        </div>
                      </div>
                      <div
                        className={`text-right text-sm font-semibold tabular-nums ${
                          c.contribution >= 0 ? "text-positive" : "text-negative"
                        }`}
                      >
                        {c.nav_stale ? "待更新" : `${c.contribution >= 0 ? "+" : ""}¥${c.contribution.toLocaleString()}`}
                        <div className="text-xs font-normal text-muted-foreground">
                          占比 {Math.abs(c.contribution_rate * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
              暂无持仓，无法分析今日收益
            </div>
          )}
        </div>
      </section>

      {/* Action bar */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-1 rounded-xl border border-border bg-muted/40 p-1">
          <button
            onClick={() => setActiveTab("active")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === "active"
                ? "bg-background shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Briefcase className="h-3.5 w-3.5" />
            当前持仓
            {activeHoldings.length > 0 && (
              <span className="ml-0.5 rounded-md bg-muted px-1.5 py-0.5 text-[11px]">
                {activeHoldings.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab("sold")}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              activeTab === "sold"
                ? "bg-background shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <History className="h-3.5 w-3.5" />
            已平仓记录
            {soldHoldings.length > 0 && (
              <span className="ml-0.5 rounded-md bg-muted px-1.5 py-0.5 text-[11px]">
                {soldHoldings.length}
              </span>
            )}
          </button>
        </div>

        {activeTab === "active" && (
          <Button
            onClick={() => setShowForm(!showForm)}
            className="h-10 rounded-xl gap-2"
          >
            <Plus className="h-4 w-4" /> {showForm ? "取消" : "新增持仓"}
          </Button>
        )}
      </div>

      {/* Add form */}
      {activeTab === "active" && showForm && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="mb-6 overflow-hidden rounded-2xl border border-border bg-background p-5"
        >
          {/* 模式切换：单笔 / 自动定投 */}
          <div className="mb-4 flex max-w-xs gap-1 rounded-xl border border-border bg-muted/40 p-1">
            <button
              onClick={() => setFormMode("single")}
              className={`flex-1 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                formMode === "single"
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              单笔买入
            </button>
            <button
              onClick={() => setFormMode("drip")}
              className={`flex-1 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                formMode === "drip"
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              自动定投
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Fund search */}
            <div className="relative sm:col-span-2">
              <label className="text-xs text-muted-foreground">
                基金代码/名称
              </label>
              <Input
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShowSuggestions(true);
                  setForm((f) => ({ ...f, fund_code: "" }));
                }}
                placeholder="搜索基金..."
                className="mt-1 h-10 rounded-xl"
              />
              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute z-10 mt-1 w-full rounded-xl border border-border bg-background p-1 shadow-lg">
                  {suggestions.map((s) => (
                    <button
                      key={s.code}
                      onClick={() => selectFund(s)}
                      className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-muted"
                    >
                      <span className="font-medium">{s.name}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {s.code}
                      </span>
                      {s.type && (
                        <Badge variant="outline" className="ml-2 text-[10px]">
                          {s.type}
                        </Badge>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 单笔买入字段（formMode=single） */}
            {formMode === "single" && (
              <>
                <div>
                  <label className="text-xs text-muted-foreground">买入日期</label>
                  <Input
                    type="date"
                    value={form.buy_date}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, buy_date: e.target.value }))
                    }
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">买入金额 (¥)</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.buy_amount || ""}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        buy_amount: +e.target.value,
                      }))
                    }
                    placeholder="0.00"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">买入净值</label>
                  <Input
                    type="number"
                    step="0.0001"
                    value={form.buy_nav || ""}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, buy_nav: +e.target.value }))
                    }
                    placeholder="1.0000"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">买入份额</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.shares || ""}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, shares: +e.target.value }))
                    }
                    placeholder="0.00"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">手续费</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={form.fee ?? ""}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        fee: e.target.value === "" ? 0 : +e.target.value,
                      }))
                    }
                    placeholder="0.00"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-xs text-muted-foreground">备注</label>
                  <Input
                    value={form.notes}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, notes: e.target.value }))
                    }
                    placeholder="可选"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
              </>
            )}

            {/* 自动定投字段（formMode=drip） */}
            {formMode === "drip" && (
              <>
                <div>
                  <label className="text-xs text-muted-foreground">每次定投金额 (¥)</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={drip.amount || ""}
                    onChange={(e) =>
                      setDrip((d) => ({ ...d, amount: +e.target.value }))
                    }
                    placeholder="1000.00"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">定投频率</label>
                  <div className="mt-1 flex gap-1 rounded-xl border border-border bg-muted/40 p-1">
                    <button
                      onClick={() => setDrip((d) => ({ ...d, frequency: "daily" }))}
                      className={`flex-1 rounded-lg px-2 py-1 text-xs font-medium transition-colors ${
                        drip.frequency === "daily"
                          ? "bg-background shadow-sm text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      每天
                    </button>
                    <button
                      onClick={() =>
                        setDrip((d) => ({ ...d, frequency: "weekly", day_of_week: 1 }))
                      }
                      className={`flex-1 rounded-lg px-2 py-1 text-xs font-medium transition-colors ${
                        drip.frequency === "weekly"
                          ? "bg-background shadow-sm text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      每周
                    </button>
                    <button
                      onClick={() => setDrip((d) => ({ ...d, frequency: "monthly" }))}
                      className={`flex-1 rounded-lg px-2 py-1 text-xs font-medium transition-colors ${
                        drip.frequency === "monthly"
                          ? "bg-background shadow-sm text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      每月
                    </button>
                  </div>
                </div>
                {drip.frequency === "weekly" && (
                  <div>
                    <label className="text-xs text-muted-foreground">定投星期</label>
                    <select
                      value={drip.day_of_week}
                      onChange={(e) =>
                        setDrip((d) => ({ ...d, day_of_week: Number(e.target.value) }))
                      }
                      className="mt-1 h-10 w-full rounded-xl border border-border bg-background px-3 text-sm"
                    >
                      {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map(
                        (label, index) => (
                          <option key={label} value={index + 1}>
                            {label}（{index + 1}）
                          </option>
                        )
                      )}
                    </select>
                  </div>
                )}
                {drip.frequency === "monthly" && (
                  <div>
                    <label className="text-xs text-muted-foreground">每月几号（1–31）</label>
                    <Input
                      type="number"
                      min={1}
                      max={31}
                      value={drip.day_of_week}
                      onChange={(e) =>
                        setDrip((d) => ({
                          ...d,
                          day_of_week: +e.target.value || 1,
                        }))
                      }
                      className="mt-1 h-10 rounded-xl"
                    />
                  </div>
                )}
                <div>
                  <label className="text-xs text-muted-foreground">开始日期</label>
                  <Input
                    type="date"
                    value={drip.start_date}
                    onChange={(e) =>
                      setDrip((d) => ({ ...d, start_date: e.target.value }))
                    }
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">截止日期</label>
                  <Input
                    type="date"
                    value={drip.end_date}
                    onChange={(e) =>
                      setDrip((d) => ({ ...d, end_date: e.target.value }))
                    }
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">手续费/期</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={drip.fee || ""}
                    onChange={(e) =>
                      setDrip((d) => ({ ...d, fee: +e.target.value || 0 }))
                    }
                    placeholder="0.00"
                    className="mt-1 h-10 rounded-xl"
                  />
                </div>
              </>
            )}
          </div>
          <Button
            onClick={formMode === "single" ? handleAdd : handleDrip}
            disabled={submitting}
            className="mt-4 h-10 rounded-xl bg-foreground px-6 text-background hover:bg-foreground/90"
          >
            {submitting
              ? "提交中…"
              : formMode === "single"
                ? "确认添加"
                : "生成定投"}
          </Button>
          {formMode === "drip" && (
            <p className="mt-2 text-xs text-muted-foreground">
              定投将按日期自动查询历史净值、计算份额并生成多条持仓记录。
            </p>
          )}
        </motion.div>
      )}

      {/* ── Active holdings table ── */}
      {activeTab === "active" &&
        (activeHoldings.length === 0 ? (
          <div className="rounded-2xl border border-border bg-background py-16 text-center text-muted-foreground">
            <Briefcase className="mx-auto mb-3 h-8 w-8 opacity-40" />
            <p>暂无持仓</p>
            <p className="mt-1 text-xs">点击“新增持仓”添加真实交易记录</p>
          </div>
        ) : (
          <HoldingsTable
            holdings={activeHoldings}
            onSell={(h) => setModal({ type: "sell", holding: h })}
            onEdit={(h) => setModal({ type: "edit", holding: h })}
            onDelete={handleDelete}
          />
        ))}

      {/* ── Sold holdings table ── */}
      {activeTab === "sold" &&
        (soldHoldings.length === 0 ? (
          <div className="rounded-2xl border border-border bg-background py-16 text-center text-muted-foreground">
            <History className="mx-auto mb-3 h-8 w-8 opacity-40" />
            <p>暂无已平仓记录</p>
            <p className="mt-1 text-xs">卖出持仓后将在此显示历史记录</p>
          </div>
        ) : (
          <SoldTable holdings={soldHoldings} />
        ))}

      {/* Trade modal (sell / edit) */}
      {modal && (
        <TradeModal
          open
          mode={modal.type}
          holding={modal.holding}
          onClose={() => setModal(null)}
          onConfirmSell={handleConfirmSell}
          onConfirmEdit={handleConfirmEdit}
        />
      )}
    </div>
  );
}

// ── Shared table component: active holdings ──

function HoldingsTable({
  holdings,
  onSell,
  onEdit,
  onDelete,
}: {
  holdings: HoldingItem[];
  onSell: (h: HoldingItem) => void;
  onEdit: (h: HoldingItem) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-background">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/40 text-left">
          <tr>
            <th className="px-4 py-3 font-medium">基金</th>
            <th className="px-4 py-3 font-medium">买入日期</th>
            <th className="px-4 py-3 font-medium text-right">成本</th>
            <th className="px-4 py-3 font-medium text-right">份额</th>
            <th className="px-4 py-3 font-medium text-right">当前净值</th>
            <th className="px-4 py-3 font-medium text-right">市值</th>
            <th className="px-4 py-3 font-medium text-right">盈亏</th>
            <th className="px-4 py-3 font-medium text-center">操作</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <motion.tr
              key={h.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.02 * i }}
              className="border-b border-border last:border-0 hover:bg-muted/20"
            >
              <td className="px-4 py-3">
                <div className="font-medium">{h.fund_name}</div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {h.fund_code}
                  {h.fund_type && (
                    <Badge variant="outline" className="text-[10px]">
                      {h.fund_type}
                    </Badge>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-muted-foreground">{h.buy_date}</td>
              <td className="px-4 py-3 text-right tabular-nums">
                ¥{(h.cost ?? 0).toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {h.shares.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {h.current_nav?.toFixed(4) ?? "—"}
              </td>
              <td className="px-4 py-3 text-right tabular-nums font-medium">
                ¥{(h.current_value ?? 0).toLocaleString()}
              </td>
              <td
                className={`px-4 py-3 text-right tabular-nums font-medium ${
                  (h.profit ?? 0) >= 0 ? "text-positive" : "text-negative"
                }`}
              >
                {h.profit != null ? (
                  <>
                    {h.profit >= 0 ? "+" : ""}¥{h.profit.toLocaleString()}
                    <br />
                    <span className="text-xs">
                      ({h.profit >= 0 ? "+" : ""}
                      {h.profit_pct?.toFixed(2)}%)
                    </span>
                  </>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit(h)}
                    className="h-7 rounded-lg text-xs"
                  >
                    <Edit3 className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onSell(h)}
                    className="h-7 rounded-lg text-xs"
                  >
                    卖出
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onDelete(h.id)}
                    className="h-7 rounded-lg text-xs text-negative"
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Sold holdings table ──

function SoldTable({ holdings }: { holdings: HoldingItem[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-border bg-background">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/40 text-left">
          <tr>
            <th className="px-4 py-3 font-medium">基金</th>
            <th className="px-4 py-3 font-medium">买入日期</th>
            <th className="px-4 py-3 font-medium">卖出日期</th>
            <th className="px-4 py-3 font-medium text-right">成本</th>
            <th className="px-4 py-3 font-medium text-right">卖出金额</th>
            <th className="px-4 py-3 font-medium text-right">实现盈亏</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => {
            const cost = h.cost ?? 0;
            const sellAmt = h.sell_amount ?? 0;
            const realizedProfit = sellAmt - cost;
            const realizedPct =
              cost > 0 ? (realizedProfit / cost) * 100 : 0;
            return (
              <motion.tr
                key={h.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.02 * i }}
                className="border-b border-border last:border-0 hover:bg-muted/20"
              >
                <td className="px-4 py-3">
                  <div className="font-medium">{h.fund_name}</div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {h.fund_code}
                    {h.fund_type && (
                      <Badge variant="outline" className="text-[10px]">
                        {h.fund_type}
                      </Badge>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {h.buy_date}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {h.sell_date ?? "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  ¥{cost.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  ¥{sellAmt.toLocaleString()}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums font-medium ${
                    realizedProfit >= 0 ? "text-positive" : "text-negative"
                  }`}
                >
                  {realizedProfit >= 0 ? "+" : ""}¥
                  {realizedProfit.toLocaleString()}
                  <br />
                  <span className="text-xs">
                    ({realizedProfit >= 0 ? "+" : ""}
                    {realizedPct.toFixed(2)}%)
                  </span>
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
