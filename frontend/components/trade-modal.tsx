"use client";

import { useState, useEffect } from "react";
import { Modal } from "./ui/modal";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import type { HoldingItem, HoldingCreate, SellFormData } from "@/services/fund";

interface TradeModalProps {
  open: boolean;
  mode: "sell" | "edit";
  holding: HoldingItem;
  onClose: () => void;
  onConfirmSell: (id: number, data: SellFormData) => void;
  onConfirmEdit: (id: number, data: HoldingCreate) => void;
}

export function TradeModal({
  open,
  mode,
  holding,
  onClose,
  onConfirmSell,
  onConfirmEdit,
}: TradeModalProps) {
  const today = new Date().toISOString().slice(0, 10);

  // ── Sell form state ──
  const [sellDate, setSellDate] = useState(today);
  const [sellNav, setSellNav] = useState("");
  const [sellAmount, setSellAmount] = useState("");

  // ── Edit form state ──
  const [buyDate, setBuyDate] = useState("");
  const [buyAmount, setBuyAmount] = useState("");
  const [buyNav, setBuyNav] = useState("");
  const [shares, setShares] = useState("");
  const [fee, setFee] = useState("");
  const [notes, setNotes] = useState("");

  // Reset form when holding or mode changes
  useEffect(() => {
    if (!open) return;
    if (mode === "sell") {
      setSellDate(today);
      setSellNav(holding.current_nav != null ? String(holding.current_nav) : "");
      setSellAmount("");
    } else {
      setBuyDate(holding.buy_date);
      setBuyAmount(String(holding.buy_amount));
      setBuyNav(String(holding.buy_nav));
      setShares(String(holding.shares));
      setFee(String(holding.fee ?? 0));
      setNotes(holding.notes ?? "");
    }
  }, [open, mode, holding, today]);

  // Auto-calc sell amount when sell NAV changes
  const sellNavNum = parseFloat(sellNav) || 0;
  const sharesNum = holding.shares ?? 0;
  const autoSellAmount = sellNavNum * sharesNum;

  // Preview P&L
  const cost = holding.cost ?? 0;
  const manualAmount = parseFloat(sellAmount) || 0;
  const realizedProfit = manualAmount - cost;
  const realizedProfitPct = cost > 0 ? (realizedProfit / cost) * 100 : 0;

  const handleSellNavChange = (val: string) => {
    setSellNav(val);
    const nav = parseFloat(val);
    if (!isNaN(nav) && nav > 0 && sharesNum > 0) {
      setSellAmount(String(Math.round(nav * sharesNum * 100) / 100));
    }
  };

  const handleConfirmSell = () => {
    onConfirmSell(holding.id, {
      sell_date: sellDate,
      sell_amount: manualAmount,
      sell_nav: sellNavNum,
    });
  };

  const handleConfirmEdit = () => {
    onConfirmEdit(holding.id, {
      fund_code: holding.fund_code,
      fund_name: holding.fund_name,
      fund_type: holding.fund_type,
      buy_date: buyDate,
      buy_amount: parseFloat(buyAmount) || 0,
      buy_nav: parseFloat(buyNav) || 0,
      shares: parseFloat(shares) || 0,
      fee: parseFloat(fee) || 0,
      notes,
    });
  };

  // ── Sell mode ──
  if (mode === "sell") {
    return (
      <Modal open={open} onClose={onClose} title="卖出持仓">
        {/* Holding context */}
        <div className="mb-4 rounded-xl border border-border bg-muted/30 p-3 space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">基金</span>
            <span className="font-medium">{holding.fund_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">持仓成本</span>
            <span className="font-medium">¥{cost.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">当前净值</span>
            <span className="font-medium">{holding.current_nav?.toFixed(4) ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">持仓市值</span>
            <span className="font-medium">
              ¥{(holding.current_value ?? 0).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Sell form */}
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground">卖出日期</label>
            <Input
              type="date"
              value={sellDate}
              onChange={(e) => setSellDate(e.target.value)}
              className="mt-1 h-10 rounded-xl"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">卖出净值</label>
            <Input
              type="number"
              step="0.0001"
              value={sellNav}
              onChange={(e) => handleSellNavChange(e.target.value)}
              placeholder="自动填入当前净值"
              className="mt-1 h-10 rounded-xl"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">卖出金额</label>
            <Input
              type="number"
              step="0.01"
              value={sellAmount}
              onChange={(e) => setSellAmount(e.target.value)}
              placeholder={`自动计算: ${sharesNum} 份 × ${sellNavNum} 净值`}
              className="mt-1 h-10 rounded-xl"
            />
          </div>

          {/* P&L preview */}
          {manualAmount > 0 && cost > 0 && (
            <div
              className={`rounded-xl p-3 text-center text-sm font-medium ${
                realizedProfit >= 0
                  ? "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
                  : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
              }`}
            >
              预估实现盈亏：{realizedProfit >= 0 ? "+" : ""}¥
              {realizedProfit.toLocaleString("zh-CN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}{" "}
              ({realizedProfit >= 0 ? "+" : ""}
              {realizedProfitPct.toFixed(2)}%)
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-5 flex gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            className="flex-1 h-10 rounded-xl"
          >
            取消
          </Button>
          <Button
            onClick={handleConfirmSell}
            disabled={!sellDate || !sellNav || !sellAmount}
            className="flex-1 h-10 rounded-xl bg-red-600 text-white hover:bg-red-700"
          >
            确认卖出
          </Button>
        </div>
      </Modal>
    );
  }

  // ── Edit mode ──
  return (
    <Modal open={open} onClose={onClose} title="编辑持仓">
      <div className="space-y-3">
        <div className="rounded-xl border border-border bg-muted/30 p-3 text-sm">
          <span className="text-muted-foreground">基金：</span>
          <span className="font-medium">{holding.fund_name}</span>
          <span className="ml-2 text-xs text-muted-foreground">{holding.fund_code}</span>
        </div>

        <div>
          <label className="text-xs text-muted-foreground">买入日期</label>
          <Input
            type="date"
            value={buyDate}
            onChange={(e) => setBuyDate(e.target.value)}
            className="mt-1 h-10 rounded-xl"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">买入金额 (¥)</label>
            <Input
              type="number"
              step="0.01"
              value={buyAmount}
              onChange={(e) => setBuyAmount(e.target.value)}
              className="mt-1 h-10 rounded-xl"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">买入净值</label>
            <Input
              type="number"
              step="0.0001"
              value={buyNav}
              onChange={(e) => setBuyNav(e.target.value)}
              className="mt-1 h-10 rounded-xl"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">份额</label>
            <Input
              type="number"
              step="0.01"
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              className="mt-1 h-10 rounded-xl"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">手续费</label>
            <Input
              type="number"
              step="0.01"
              value={fee}
              onChange={(e) => setFee(e.target.value)}
              className="mt-1 h-10 rounded-xl"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-muted-foreground">备注</label>
          <Input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="可选"
            className="mt-1 h-10 rounded-xl"
          />
        </div>
      </div>

      <div className="mt-5 flex gap-3">
        <Button
          variant="outline"
          onClick={onClose}
          className="flex-1 h-10 rounded-xl"
        >
          取消
        </Button>
        <Button
          onClick={handleConfirmEdit}
          disabled={!buyDate || !buyAmount || !buyNav || !shares}
          className="flex-1 h-10 rounded-xl bg-foreground text-background hover:bg-foreground/90"
        >
          保存修改
        </Button>
      </div>
    </Modal>
  );
}
