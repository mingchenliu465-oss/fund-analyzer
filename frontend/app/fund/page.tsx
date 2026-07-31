"use client";

import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Calendar,
  Percent,
  Search,
  TrendingDown,
  TrendingUp,
  Zap,
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

const chartData = [
  { date: "1月", value: 1.0 },
  { date: "2月", value: 1.03 },
  { date: "3月", value: 0.98 },
  { date: "4月", value: 1.05 },
  { date: "5月", value: 1.09 },
  { date: "6月", value: 1.12 },
  { date: "7月", value: 1.18 },
  { date: "8月", value: 1.15 },
  { date: "9月", value: 1.21 },
  { date: "10月", value: 1.25 },
  { date: "11月", value: 1.22 },
  { date: "12月", value: 1.28 },
];

export default function FundPage() {
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
          基金分析
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="mt-3 max-w-2xl text-lg text-muted-foreground"
        >
          输入基金代码或名称，快速了解业绩表现、风险特征与适合人群。
        </motion.p>
      </section>

      {/* Search */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
        className="mb-12 flex flex-col gap-3 sm:flex-row"
      >
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="输入基金代码 / 名称，例如 000001 或 华夏成长"
            className="h-12 rounded-2xl border-border bg-background pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
          />
        </div>
        <Button className="h-12 rounded-2xl bg-foreground px-8 text-base font-medium text-background hover:bg-foreground/90">
          分析
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </motion.div>

      {/* Fund Overview */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.15, ease: [0.23, 1, 0.32, 1] }}
        className="mb-8 rounded-3xl border border-border bg-background p-6 sm:p-8"
      >
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-medium text-muted-foreground">
              示例基金
            </div>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">
              沪深300指数基金
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              000300 · 股票型 · 中高风险
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm text-muted-foreground">最新净值</div>
              <div className="text-2xl font-semibold">¥1.2842</div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">近一年收益</div>
              <div className="flex items-center justify-end gap-1 text-2xl font-semibold text-positive">
                <TrendingUp className="h-5 w-5" />
                +12.84%
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Metrics */}
      <div className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="成立以来年化"
          value="8.6%"
          trend="up"
          trendValue="+2.1%"
          subtitle="跑赢通胀"
          icon={Calendar}
          delay={0.2}
        />
        <MetricCard
          title="最大回撤"
          value="-18.2%"
          trend="down"
          trendValue="需承受波动"
          subtitle="历史极端情况"
          icon={TrendingDown}
          delay={0.25}
        />
        <MetricCard
          title="夏普比率"
          value="0.72"
          trend="neutral"
          subtitle="风险调整后收益"
          icon={Zap}
          delay={0.3}
        />
        <MetricCard
          title="波动率"
          value="16.4%"
          trend="neutral"
          subtitle="年度波动幅度"
          icon={Percent}
          delay={0.35}
        />
      </div>

      {/* Chart */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4, ease: [0.23, 1, 0.32, 1] }}
        className="rounded-3xl border border-border bg-background p-6 sm:p-8"
      >
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold tracking-tight">
              近一年业绩走势
            </h3>
            <p className="text-sm text-muted-foreground">
              净值归一化走势，便于观察真实表现
            </p>
          </div>
          <div className="flex gap-2">
            {["1月", "3月", "6月", "1年", "3年"].map((period) => (
              <button
                key={period}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  period === "1年"
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                {period}
              </button>
            ))}
          </div>
        </div>
        <div className="h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0071e3" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#0071e3" stopOpacity={0} />
                </linearGradient>
              </defs>
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
                domain={[0.9, 1.35]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--background)",
                  border: "1px solid var(--border)",
                  borderRadius: "12px",
                  boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                }}
                labelStyle={{ color: "var(--muted-foreground)", fontSize: 12 }}
                itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
                formatter={(value) => [`${(typeof value === "number" ? value * 100 : 0).toFixed(2)}%`, "净值"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#0071e3"
                strokeWidth={2}
                fill="url(#colorValue)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 0, fill: "#0071e3" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </motion.div>

      {/* Analysis Notes */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.5, ease: [0.23, 1, 0.32, 1] }}
        className="mt-8 grid gap-6 sm:grid-cols-3"
      >
        <div className="rounded-2xl border border-border bg-muted/40 p-6">
          <h4 className="mb-2 font-semibold">适合谁</h4>
          <p className="text-sm leading-relaxed text-muted-foreground">
            能承受中等波动、希望长期分享中国经济增长的普通家庭投资者。
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-muted/40 p-6">
          <h4 className="mb-2 font-semibold">配置建议</h4>
          <p className="text-sm leading-relaxed text-muted-foreground">
            作为组合中的核心宽基仓位，建议搭配债券基金平滑波动。
          </p>
        </div>
        <div className="rounded-2xl border border-border bg-muted/40 p-6">
          <h4 className="mb-2 font-semibold">注意事项</h4>
          <p className="text-sm leading-relaxed text-muted-foreground">
            短期可能出现 15%-20% 回撤，建议持有周期不少于 3 年。
          </p>
        </div>
      </motion.div>
    </div>
  );
}
