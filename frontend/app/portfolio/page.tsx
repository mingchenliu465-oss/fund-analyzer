"use client";

import { useEffect, useState, useCallback } from "react";
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
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { TradeModal } from "@/components/trade-modal";
import {
  HoldingItem,
  HoldingCreate,
  SellFormData,
  RealPortfolioSummary,
  getRealPortfolio,
  getAllHoldings,
  createHolding,
  sellHolding,
  deleteHolding,
  updateHolding,
  searchFunds,
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
  const [suggestions, setSuggestions] = useState<
    { code: string; name: string; type: string }[]
  >([]);
  const [form, setForm] = useState<HoldingCreate>({
    fund_code: "",
    fund_name: "",
    fund_type: "",
    buy_date: "",
    buy_amount: 0,
    buy_nav: 0,
    shares: 0,
    fee: 0,
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const fetchPortfolio = useCallback(() => {
    Promise.all([
      getRealPortfolio().catch(() => null),
      getAllHoldings().catch(() => [] as HoldingItem[]),
    ]).then(([summary, all]) => {
      if (summary) setPortfolio(summary);
      setSoldHoldings(all.filter((h) => h.is_sold));
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    fetchPortfolio();
  }, [fetchPortfolio]);

  // Search suggestions
  useEffect(() => {
    if (!query.trim()) {
      setSuggestions([]);
      return;
    }
    const t = setTimeout(
      () =>
        searchFunds(query).then((r) =>
          setSuggestions(
            r.slice(0, 5).map((f) => ({ code: f.code, name: f.name, type: f.type }))
          )
        ),
      250
    );
    return () => clearTimeout(t);
  }, [query]);

  // Auto-fill form from search selection
  const selectFund = (s: { code: string; name: string; type: string }) => {
    setForm((f) => ({
      ...f,
      fund_code: s.code,
      fund_name: s.name,
      fund_type: s.type,
    }));
    setQuery(s.name);
    setSuggestions([]);
  };

  const handleAdd = async () => {
    if (!form.fund_code || !form.buy_date || form.buy_amount <= 0) return;
    setSubmitting(true);
    try {
      await createHolding(form);
      setShowForm(false);
      resetForm();
      fetchPortfolio();
    } catch (err) {
      console.error(err);
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
      fee: 0,
      notes: "",
    });
    setQuery("");
  };

  const handleConfirmSell = async (id: number, data: SellFormData) => {
    try {
      await sellHolding(id, data);
      setModal(null);
      fetchPortfolio();
    } catch (err) {
      console.error(err);
    }
  };

  const handleConfirmEdit = async (id: number, data: HoldingCreate) => {
    try {
      await updateHolding(id, data);
      setModal(null);
      fetchPortfolio();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确认删除此持仓记录？")) return;
    try {
      await deleteHolding(id);
      fetchPortfolio();
    } catch (err) {
      console.error(err);
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
                  setForm((f) => ({ ...f, fund_code: "" }));
                }}
                placeholder="搜索基金..."
                className="mt-1 h-10 rounded-xl"
              />
              {suggestions.length > 0 && (
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
                value={form.fee || ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, fee: +e.target.value }))
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
          </div>
          <Button
            onClick={handleAdd}
            disabled={submitting}
            className="mt-4 h-10 rounded-xl bg-foreground px-6 text-background hover:bg-foreground/90"
          >
            {submitting ? "提交中…" : "确认添加"}
          </Button>
        </motion.div>
      )}

      {/* ── Active holdings table ── */}
      {activeTab === "active" &&
        (activeHoldings.length === 0 ? (
          <div className="rounded-2xl border border-border bg-background py-16 text-center text-muted-foreground">
            <Briefcase className="mx-auto mb-3 h-8 w-8 opacity-40" />
            <p>暂无持仓</p>
            <p className="mt-1 text-xs">点击"新增持仓"添加真实交易记录</p>
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
