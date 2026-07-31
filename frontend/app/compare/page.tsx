"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { motion } from "framer-motion";
import { Plus, Search, X } from "lucide-react";
import { useState } from "react";
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

const chartData = [
  { date: "1月", a: 1.0, b: 1.0, c: 1.0 },
  { date: "2月", a: 1.03, b: 1.01, c: 1.015 },
  { date: "3月", a: 0.98, b: 1.0, c: 1.005 },
  { date: "4月", a: 1.05, b: 1.03, c: 1.02 },
  { date: "5月", a: 1.09, b: 1.04, c: 1.025 },
  { date: "6月", a: 1.12, b: 1.055, c: 1.03 },
  { date: "7月", a: 1.18, b: 1.06, c: 1.035 },
  { date: "8月", a: 1.15, b: 1.055, c: 1.04 },
  { date: "9月", a: 1.21, b: 1.07, c: 1.038 },
  { date: "10月", a: 1.25, b: 1.075, c: 1.045 },
  { date: "11月", a: 1.22, b: 1.07, c: 1.05 },
  { date: "12月", a: 1.28, b: 1.08, c: 1.055 },
];

const comparisonFunds = [
  {
    id: "a",
    name: "沪深300指数基金",
    code: "000300",
    type: "股票型",
    oneYear: "+12.84%",
    drawdown: "-18.2%",
    sharpe: "0.72",
    volatility: "16.4%",
    color: "#171717",
  },
  {
    id: "b",
    name: "中证500指数基金",
    code: "000905",
    type: "股票型",
    oneYear: "+8.05%",
    drawdown: "-21.5%",
    sharpe: "0.58",
    volatility: "18.7%",
    color: "#0071e3",
  },
  {
    id: "c",
    name: "稳健债券基金",
    code: "000171",
    type: "债券型",
    oneYear: "+4.52%",
    drawdown: "-2.1%",
    sharpe: "1.25",
    volatility: "3.2%",
    color: "#6e6e73",
  },
];

const metrics = [
  { key: "oneYear", label: "近一年收益" },
  { key: "drawdown", label: "最大回撤" },
  { key: "sharpe", label: "夏普比率" },
  { key: "volatility", label: "波动率" },
];

export default function ComparePage() {
  const [funds, setFunds] = useState(comparisonFunds);

  const removeFund = (id: string) => {
    setFunds((prev) => prev.filter((f) => f.id !== id));
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Header */}
      <section className="mb-12">
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="text-3xl font-semibold tracking-tight sm:text-4xl"
        >
          基金对比
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="mt-3 max-w-2xl text-lg text-muted-foreground"
        >
          同时比较多只基金，从收益、风险与性价比中做出更理性的选择。
        </motion.p>
      </section>

      {/* Add Fund */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
        className="mb-10 flex flex-col gap-3 sm:flex-row"
      >
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="输入基金代码 / 名称加入对比"
            className="h-12 rounded-2xl border-border bg-background pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
          />
        </div>
        <Button className="h-12 rounded-2xl bg-foreground px-8 text-base font-medium text-background hover:bg-foreground/90">
          <Plus className="mr-2 h-4 w-4" />
          添加
        </Button>
      </motion.div>

      {/* Chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15, ease: [0.23, 1, 0.32, 1] }}
        className="mb-10 rounded-3xl border border-border bg-background p-6 sm:p-8"
      >
        <div className="mb-6">
          <h3 className="text-lg font-semibold tracking-tight">收益走势对比</h3>
          <p className="text-sm text-muted-foreground">近一年净值归一化走势</p>
        </div>
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                dy={8}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                domain={[0.95, 1.35]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--background)",
                  border: "1px solid var(--border)",
                  borderRadius: "12px",
                  boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                }}
                itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
                formatter={(value, name) => [
                  `${(typeof value === "number" ? value * 100 : 0).toFixed(2)}%`,
                  funds.find((f) => f.id === name)?.name ?? String(name),
                ]}
              />
              <Legend
                verticalAlign="top"
                height={36}
                iconType="circle"
                formatter={(value: string) => (
                  <span className="text-sm text-muted-foreground">
                    {funds.find((f) => f.id === value)?.name ?? value}
                  </span>
                )}
              />
              {funds.map((fund) => (
                <Line
                  key={fund.id}
                  type="monotone"
                  dataKey={fund.id}
                  stroke={fund.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 0, fill: fund.color }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Comparison Table */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.25, ease: [0.23, 1, 0.32, 1] }}
        className="rounded-3xl border border-border bg-background p-2"
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border text-left text-sm text-muted-foreground">
                <th className="px-4 py-3 font-medium">基金</th>
                {metrics.map((m) => (
                  <th key={m.key} className="px-4 py-3 font-medium">{m.label}</th>
                ))}
                <th className="px-4 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {funds.map((fund) => (
                <tr
                  key={fund.id}
                  className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
                >
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-3">
                      <span
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: fund.color }}
                      />
                      <div>
                        <div className="font-medium">{fund.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {fund.code} · {fund.type}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 font-medium text-positive">{fund.oneYear}</td>
                  <td className="px-4 py-4 text-negative">{fund.drawdown}</td>
                  <td className="px-4 py-4">{fund.sharpe}</td>
                  <td className="px-4 py-4">{fund.volatility}</td>
                  <td className="px-4 py-4 text-right">
                    <button
                      onClick={() => removeFund(fund.id)}
                      className="inline-flex items-center justify-center rounded-full p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-negative"
                      aria-label={`移除 ${fund.name}`}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Empty CTA */}
      {funds.length < 2 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="mt-6 rounded-2xl border border-dashed border-border bg-muted/40 p-6 text-center"
        >
          <p className="text-sm text-muted-foreground">至少添加两只基金才能进行有效对比</p>
        </motion.div>
      )}
    </div>
  );
}
