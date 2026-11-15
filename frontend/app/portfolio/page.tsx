"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import {
  Briefcase,
  Plus,
  Trash2,
  Edit3,
  History,
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { TradeModal } from "@/components/trade-modal";
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
  const [historyFailed, setHistoryFailed] = useState(false);
  const [historyView, setHistoryView] = useState<"value" | "rate">("value");

  // 今日收益归因状态
  const [attribution, setAttribution] = useState<AttributionResult | null>(null);
  const [attributionFailed, setAttributionFailed] = useState(false);
  const skippedInitialHistoryRefresh = useRef(false);
  const skippedInitialAttributionRefresh = useRef(false);

  const fetchPortfolio = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([getRealPortfolio(), getAllHoldings()])
      .then(([summary, all]) => {
        setPortfolio(summary);
        setSoldHoldings(all.filter((h) => h.is_sold));
      })
      .catch(() => {
        setError("加载持仓失败：数据暂时不可用，请重新加载。");
      })
      .finally(() => setLoading(false));
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
    getPortfolioHistory(historyPeriod)
      .then((points) => {
        setHistoryData(points);
        setHistoryFailed(false);
      })
      .catch(() => {
        setHistoryData([]);
        setHistoryFailed(true);
      });
  }, [historyPeriod, portfolio]);

  // 拉取今日收益归因（持仓变化后刷新）
  useEffect(() => {
    if (portfolio && !skippedInitialAttributionRefresh.current) {
      skippedInitialAttributionRefresh.current = true;
      return;
    }
    getPortfolioAttribution()
      .then((r) => {
        setAttribution(r);
        setAttributionFailed(false);
      })
      .catch(() => {
        setAttribution(null);
        setAttributionFailed(true);
      });
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
      setNotice({ type: "error", text: "定投失败，请稍后重试。" });
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
      setNotice({ type: "error", text: "添加失败，请稍后重试。" });
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
      setNotice({ type: "error", text: "卖出失败，请稍后重试。" });
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
      setNotice({ type: "error", text: "保存失败，请稍后重试。" });
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
      setNotice({ type: "error", text: "删除失败，请稍后重试。" });
    }
  };

  // ── Derived data ──

  const activeHoldings = (portfolio?.holdings ?? []).filter((h) => !h.is_sold);

  const totalValue = portfolio?.total_value ?? 0;
  const totalCost = portfolio?.total_cost ?? 0;
  const totalProfit = portfolio?.total_profit ?? 0;
  const portfolioConclusion = error
    ? "持仓数据暂时不可用，当前页面不会用替代数据填充。"
    : activeHoldings.length === 0
      ? "当前没有未平仓持仓。新增真实交易后，这里才会计算市值与盈亏。"
      : portfolio?.total_value == null || portfolio.total_cost == null || portfolio.total_profit == null
        ? `已记录 ${activeHoldings.length} 只未平仓基金，但估值数据不完整，缺失的市值、成本或盈亏显示为“—”。`
        : `当前 ${activeHoldings.length} 只未平仓基金合计市值 ¥${totalValue.toLocaleString()}，累计成本 ¥${totalCost.toLocaleString()}，浮动盈亏 ${totalProfit >= 0 ? "+" : ""}¥${totalProfit.toLocaleString()}。`;
  // 浮动盈亏为 null 表示估值不完整：方向与百分比都不得用 ?? 0 伪装成"+0.00% 上涨"。
  // 判断必须内联写在用到的地方，TS 无法通过中间布尔变量收窄 null 类型。

  if (loading)
    return (
      <div className="page-container">
        <PageHeader title="我的组合" description="手动录入真实交易，按现有净值计算持仓盈亏。" />
        <DataState kind="loading" title="正在加载持仓" description="正在读取交易记录、净值与资产历史，请稍候。" />
      </div>
    );

  return (
    <div className="page-container">
      {/* Error banner（后端不可达 / 加载失败） */}
      {error && (
        <div className="mb-6 flex items-center justify-between rounded-md border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
          <span>{error}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchPortfolio}
            className="ml-4 text-xs"
          >
            重试
          </Button>
        </div>
      )}
      {portfolio?.has_stale_nav && !error && (
        <div className="mb-6 rounded-md border border-border bg-muted px-4 py-3 text-sm text-foreground">
          部分持仓的最新净值暂不可用，当前市值使用最近有效净值或买入净值估算，待数据更新后会自动刷新。
        </div>
      )}

      {/* 操作反馈 */}
      {notice && (
        <div
          className={`mb-6 rounded-md border px-4 py-3 text-sm ${
            notice.type === "success"
              ? "border-positive/30 bg-positive/10 text-positive"
              : "border-negative/30 bg-negative/10 text-negative"
          }`}
        >
          {notice.text}
        </div>
      )}

      <PageHeader
        title="我的组合"
        description="手动录入真实交易，按现有净值计算持仓盈亏。"
      />

      <PlainConclusion note="仅汇总已录入交易与已记录行情，不构成买卖建议。">
        {portfolioConclusion}
      </PlainConclusion>

      <MetricStrip
        label="组合核心指标"
        items={[
          {
            label: "持仓市值",
            value: portfolio?.total_value != null ? `¥${totalValue.toLocaleString()}` : "—",
            note: portfolio?.has_stale_nav ? "部分净值待更新" : "按现有净值估值",
          },
          {
            label: "累计成本",
            value: portfolio?.total_cost != null ? `¥${totalCost.toLocaleString()}` : "—",
            note: "已录入买入成本",
          },
          {
            label: "浮动盈亏",
            value: portfolio?.total_profit != null ? `${totalProfit >= 0 ? "+" : ""}¥${totalProfit.toLocaleString()}` : "—",
            note: portfolio?.total_profit_pct != null
              ? `${portfolio.total_profit_pct >= 0 ? "+" : ""}${portfolio.total_profit_pct.toFixed(2)}%`
              : "估值不完整",
            tone: toneFor(portfolio?.total_profit),
          },
          {
            label: "持仓数量",
            value: error || !portfolio ? "—" : `${activeHoldings.length} 只`,
            note: error ? "读取失败" : "未平仓基金",
          },
        ]}
      />
      <SourceNote>持仓市值与盈亏来自现有组合接口；缺失估值以“—”表示，不按 0 计算。</SourceNote>

      {/* Asset history chart */}
      <ResearchSection
        title="资产走势"
        description={historyView === "value"
          ? "总资产变化（每日记录快照）"
          : "收益率 =（当前资产 − 累计成本）/ 累计成本"}
        action={
          <div className="flex flex-col gap-2 sm:items-end">
            <SegmentedControl
              label="资产历史区间"
              value={historyPeriod}
              onChange={setHistoryPeriod}
              items={[
                { value: "1W", label: "1周" },
                { value: "1M", label: "1月" },
                { value: "3M", label: "3月" },
                { value: "1Y", label: "1年" },
                { value: "ALL", label: "全部" },
              ]}
            />
            <SegmentedControl
              label="资产历史指标"
              value={historyView}
              onChange={setHistoryView}
              items={[
                { value: "value", label: "总资产" },
                { value: "rate", label: "收益率" },
              ]}
            />
          </div>
        }
      >
        {historyData.length > 0 ? (
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={historyData} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
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
                    borderRadius: "6px",
                    boxShadow: "none",
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
                  stroke="var(--chart-line)"
                  strokeWidth={2}
                  fill="var(--muted)"
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 0, fill: "var(--chart-line)" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <DataState
            kind={historyFailed ? "error" : "empty"}
            title={historyFailed ? "资产历史暂时不可用" : "暂无真实历史数据"}
            description={historyFailed
              ? "资产历史读取失败，未使用任何替代数据。请重新加载或稍后重试。"
              : "当前没有已记录的历史快照。"}
          />
        )}
      </ResearchSection>

      {/* 今日收益分析 */}
      <ResearchSection title="今日收益分析" description="看看今天收益来自哪里，以及每只持仓对今日波动的贡献。">
        {attribution && attribution.contributions.length > 0 ? (
          <>
            <KeyValueList
              columns={2}
              items={[
                {
                  label: "行情状态",
                  value: attribution.summary.status === "partial"
                    ? "部分可用"
                    : attribution.summary.status === "complete"
                      ? "完整"
                      : "待确认",
                },
                {
                  label: "上涨 / 下跌",
                  value: (
                    <span className="numeric">
                      <span className="text-positive">{attribution.summary.gainers_count} 只上涨</span>
                      <span className="mx-1 text-muted-foreground">·</span>
                      <span className="text-negative">{attribution.summary.losers_count} 只下跌</span>
                    </span>
                  ),
                },
                {
                  label: "今日收益",
                  value: (
                    <span className={attribution.today_return == null ? "text-muted-foreground" : attribution.today_return >= 0 ? "text-positive" : "text-negative"}>
                      {attribution.today_return == null
                        ? "—"
                        : `${attribution.today_return >= 0 ? "+" : ""}¥${attribution.today_return.toLocaleString()}`}
                    </span>
                  ),
                },
                {
                  label: "今日收益率",
                  value: (
                    <span className={attribution.today_return_pct == null ? "text-muted-foreground" : attribution.today_return_pct >= 0 ? "text-positive" : "text-negative"}>
                      {attribution.today_return_pct == null
                        ? "—"
                        : `${attribution.today_return_pct >= 0 ? "+" : ""}${attribution.today_return_pct.toFixed(2)}%`}
                    </span>
                  ),
                },
                {
                  label: "影响最大",
                  note: "按今日收益方向取贡献最大或最小的持仓",
                  value: attribution.summary.today_return != null && attribution.summary.today_return >= 0
                    ? attribution.summary.top_gainer_name ?? "—"
                    : attribution.summary.top_loser_name ?? "—",
                },
              ]}
            />
            <SourceNote>
              {attribution.summary.note}
              {attribution.summary.has_stale_nav && " 部分行情待更新，收益仅含可用行情。"}
            </SourceNote>

            <div className="mt-6 overflow-x-auto">
              <table className="data-table min-w-[720px]">
                <thead>
                  <tr>
                    <th>基金</th>
                    <th className="numeric">持有份额</th>
                    <th className="numeric">净值涨跌</th>
                    <th className="numeric">今日贡献</th>
                    <th className="numeric">对今日波动占比</th>
                  </tr>
                </thead>
                <tbody>
                  {attribution.contributions.map((c) => (
                    <tr key={c.fund_code}>
                      <td>
                        <div className="font-medium">{c.fund_name}</div>
                        <div className="text-xs text-muted-foreground">{c.fund_code}</div>
                      </td>
                      <td className="numeric">{c.shares.toLocaleString()} 份</td>
                      <td className={`numeric ${c.change_pct >= 0 ? "text-positive" : "text-negative"}`}>
                        {c.change_pct >= 0 ? "+" : ""}{c.change_pct}%
                      </td>
                      <td className={`numeric font-medium ${c.contribution >= 0 ? "text-positive" : "text-negative"}`}>
                        {c.nav_stale ? "待更新" : `${c.contribution >= 0 ? "+" : ""}¥${c.contribution.toLocaleString()}`}
                      </td>
                      <td className="numeric">{Math.abs(c.contribution_rate * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <DataState
            kind={attributionFailed ? "error" : "empty"}
            title={attributionFailed ? "今日收益数据暂时不可用" : "暂无真实持仓数据"}
            description={attributionFailed ? "请重新加载或稍后重试。" : "添加未平仓持仓后，才能分析今日收益来源。"}
          />
        )}
      </ResearchSection>

      <ResearchSection
        title="持仓记录"
        description="当前持仓与已平仓记录分开显示；所有计算均来自已录入交易。"
        action={activeTab === "active" ? (
          <Button onClick={() => setShowForm(!showForm)} className="gap-2">
            <Plus className="h-4 w-4" /> {showForm ? "取消" : "新增持仓"}
          </Button>
        ) : undefined}
      >
        <div className="mb-5 overflow-x-auto">
          <SegmentedControl
            label="持仓记录类型"
            value={activeTab}
            onChange={setActiveTab}
            items={[
              { value: "active", label: `当前持仓${activeHoldings.length > 0 ? `（${activeHoldings.length}）` : ""}` },
              { value: "sold", label: `已平仓记录${soldHoldings.length > 0 ? `（${soldHoldings.length}）` : ""}` },
            ]}
          />
        </div>

      {/* Add form */}
      {activeTab === "active" && showForm && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="mb-6 overflow-hidden rounded-md border border-border bg-background p-5"
        >
          {/* 模式切换：单笔 / 自动定投 */}
          <div className="mb-4 flex max-w-xs gap-1 rounded-md border border-border bg-muted/40 p-1">
            <button
              onClick={() => setFormMode("single")}
              className={`min-h-11 flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                formMode === "single"
                  ? "bg-background text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              单笔买入
            </button>
            <button
              onClick={() => setFormMode("drip")}
              className={`min-h-11 flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                formMode === "drip"
                  ? "bg-background text-foreground"
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
                className="mt-1"
              />
              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute z-10 mt-1 w-full rounded-md border border-border bg-background p-1">
                  {suggestions.map((s) => (
                    <button
                      key={s.code}
                      onClick={() => selectFund(s)}
                      className="w-full rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
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
                    className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">定投频率</label>
                  <div className="mt-1 flex gap-1 rounded-md border border-border bg-muted/40 p-1">
                    <button
                      onClick={() => setDrip((d) => ({ ...d, frequency: "daily" }))}
                      className={`min-h-11 flex-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                        drip.frequency === "daily"
                          ? "bg-background text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      每天
                    </button>
                    <button
                      onClick={() =>
                        setDrip((d) => ({ ...d, frequency: "weekly", day_of_week: 1 }))
                      }
                      className={`min-h-11 flex-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                        drip.frequency === "weekly"
                          ? "bg-background text-foreground"
                          : "text-muted-foreground"
                      }`}
                    >
                      每周
                    </button>
                    <button
                      onClick={() => setDrip((d) => ({ ...d, frequency: "monthly" }))}
                      className={`min-h-11 flex-1 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                        drip.frequency === "monthly"
                          ? "bg-background text-foreground"
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
                      className="mt-1 h-11 w-full rounded-md border border-border bg-background px-3 text-base sm:text-sm"
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
                      className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
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
                    className="mt-1"
                  />
                </div>
              </>
            )}
          </div>
          <Button
            onClick={formMode === "single" ? handleAdd : handleDrip}
            disabled={submitting}
            className="mt-4 px-6"
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
          error ? (
            <DataState
              kind="error"
              title="持仓记录暂时不可用"
              description="读取失败后不显示为真实空持仓，请重试或稍后再来。"
            />
          ) : (
            <div className="rounded-md border border-border bg-background py-16 text-center text-muted-foreground">
              <Briefcase className="mx-auto mb-3 h-8 w-8 opacity-40" />
              <p>暂无持仓</p>
              <p className="mt-1 text-xs">点击“新增持仓”添加真实交易记录</p>
            </div>
          )
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
          error ? (
            <DataState
              kind="error"
              title="已平仓记录暂时不可用"
              description="读取失败后不显示为真实空记录，请重试或稍后再来。"
            />
          ) : (
            <div className="rounded-md border border-border bg-background py-16 text-center text-muted-foreground">
              <History className="mx-auto mb-3 h-8 w-8 opacity-40" />
              <p>暂无已平仓记录</p>
              <p className="mt-1 text-xs">卖出持仓后将在此显示历史记录</p>
            </div>
          )
        ) : (
          <SoldTable holdings={soldHoldings} />
        ))}
      </ResearchSection>

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
    <div className="overflow-x-auto">
      <table className="data-table min-w-[880px]">
        <thead>
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
                {h.cost != null ? `¥${h.cost.toLocaleString()}` : "—"}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {h.shares.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {h.current_nav?.toFixed(4) ?? "—"}
              </td>
              <td className="px-4 py-3 text-right tabular-nums font-medium">
                {h.current_value != null ? `¥${h.current_value.toLocaleString()}` : "—"}
              </td>
              <td
                className={`px-4 py-3 text-right tabular-nums font-medium ${
                  h.profit == null ? "" : h.profit >= 0 ? "text-positive" : "text-negative"
                }`}
              >
                {h.profit != null ? (
                  <>
                    {h.profit >= 0 ? "+" : ""}¥{h.profit.toLocaleString()}
                    <br />
                    <span className="text-xs">
                      {h.profit_pct != null
                        ? `(${h.profit_pct >= 0 ? "+" : ""}${h.profit_pct.toFixed(2)}%)`
                        : "收益率 —"}
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
                    aria-label={`编辑 ${h.fund_name}`}
                    className="h-11 rounded-md px-3 text-xs"
                  >
                    <Edit3 className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onSell(h)}
                    className="h-11 rounded-md text-xs"
                  >
                    卖出
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onDelete(h.id)}
                    aria-label={`删除 ${h.fund_name}`}
                    className="h-11 rounded-md px-3 text-xs text-negative"
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
    <div className="overflow-x-auto">
      <table className="data-table min-w-[880px]">
        <thead>
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
            const cost = h.cost;
            const sellAmt = h.sell_amount;
            const realizedProfit = cost != null && sellAmt != null ? sellAmt - cost : null;
            const realizedPct = realizedProfit != null && cost != null && cost > 0
              ? (realizedProfit / cost) * 100
              : null;
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
                  {cost != null ? `¥${cost.toLocaleString()}` : "—"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {sellAmt != null ? `¥${sellAmt.toLocaleString()}` : "—"}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums font-medium ${
                    realizedProfit == null
                      ? "text-muted-foreground"
                      : realizedProfit >= 0
                        ? "text-positive"
                        : "text-negative"
                  }`}
                >
                  {realizedProfit != null ? (
                    <>
                      {realizedProfit >= 0 ? "+" : ""}¥{realizedProfit.toLocaleString()}
                      <br />
                      <span className="text-xs">
                        {realizedPct != null
                          ? `(${realizedPct >= 0 ? "+" : ""}${realizedPct.toFixed(2)}%)`
                          : "收益率 —"}
                      </span>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
