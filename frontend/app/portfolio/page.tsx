"use client";

import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Briefcase,
  PieChart as PieChartIcon,
  Target,
  TrendingUp,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const allocationData = [
  { name: "股票基金", value: 45, color: "#171717" },
  { name: "债券基金", value: 30, color: "#0071e3" },
  { name: "货币基金", value: 15, color: "#6e6e73" },
  { name: "黄金 / 商品", value: 10, color: "#d1d1d6" },
];

const returnData = [
  { date: "1月", portfolio: 1.0, benchmark: 1.0 },
  { date: "2月", portfolio: 1.02, benchmark: 1.015 },
  { date: "3月", portfolio: 0.99, benchmark: 1.0 },
  { date: "4月", portfolio: 1.06, benchmark: 1.03 },
  { date: "5月", portfolio: 1.08, benchmark: 1.045 },
  { date: "6月", portfolio: 1.12, benchmark: 1.055 },
  { date: "7月", portfolio: 1.15, benchmark: 1.06 },
  { date: "8月", portfolio: 1.13, benchmark: 1.055 },
  { date: "9月", portfolio: 1.18, benchmark: 1.07 },
  { date: "10月", portfolio: 1.21, benchmark: 1.075 },
  { date: "11月", portfolio: 1.19, benchmark: 1.07 },
  { date: "12月", portfolio: 1.24, benchmark: 1.08 },
];

export default function PortfolioPage() {
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
          投资组合
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
          className="mt-3 max-w-2xl text-lg text-muted-foreground"
        >
          基于风险承受力，生成并跟踪一个简单、透明的资产配置方案。
        </motion.p>
      </section>

      {/* Metrics */}
      <div className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="组合总市值"
          value="¥128,420"
          subtitle="示例账户"
          icon={Briefcase}
          delay={0.1}
        />
        <MetricCard
          title="累计收益"
          value="¥14,420"
          trend="up"
          trendValue="+12.6%"
          subtitle="成立以来"
          icon={TrendingUp}
          delay={0.15}
        />
        <MetricCard
          title="目标年化"
          value="7.0%"
          trend="neutral"
          subtitle="稳健增长型"
          icon={Target}
          delay={0.2}
        />
        <MetricCard
          title="风险等级"
          value="中等"
          trend="neutral"
          subtitle="建议持有 ≥3 年"
          icon={AlertTriangle}
          delay={0.25}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Allocation */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-3xl border border-border bg-background p-6 sm:p-8"
        >
          <div className="mb-4">
            <h3 className="text-lg font-semibold tracking-tight">
              资产配置
            </h3>
            <p className="text-sm text-muted-foreground">
              按资产类别划分的当前仓位
            </p>
          </div>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={allocationData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={110}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {allocationData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--background)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
                  }}
                  itemStyle={{ color: "var(--foreground)", fontSize: 13 }}
                  formatter={(value, name) => [`${value}%`, name]}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  iconType="circle"
                  formatter={(value: string) => (
                    <span className="text-sm text-muted-foreground">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {allocationData.map((item) => (
              <div
                key={item.name}
                className="flex items-center justify-between rounded-xl border border-border p-3"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm">{item.name}</span>
                </div>
                <span className="text-sm font-medium">{item.value}%</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Performance */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-3xl border border-border bg-background p-6 sm:p-8"
        >
          <div className="mb-4">
            <h3 className="text-lg font-semibold tracking-tight">
              组合 vs 基准
            </h3>
            <p className="text-sm text-muted-foreground">
              与沪深300指数走势对比
            </p>
          </div>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={returnData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <defs>
                  <linearGradient id="colorPortfolio" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#171717" stopOpacity={0.12} />
                    <stop offset="95%" stopColor="#171717" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorBenchmark" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0071e3" stopOpacity={0.12} />
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
                  domain={[0.95, 1.28]}
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
                    name === "portfolio" ? "我的组合" : "沪深300",
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="portfolio"
                  stroke="#171717"
                  strokeWidth={2}
                  fill="url(#colorPortfolio)"
                  dot={false}
                />
                <Area
                  type="monotone"
                  dataKey="benchmark"
                  stroke="#0071e3"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  fill="url(#colorBenchmark)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
      </div>

      {/* Action */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.45, ease: [0.23, 1, 0.32, 1] }}
        className="mt-8 flex flex-col items-start justify-between gap-4 rounded-3xl border border-border bg-muted/40 p-6 sm:flex-row sm:items-center sm:p-8"
      >
        <div>
          <h4 className="text-lg font-semibold">想要一份新的配置方案？</h4>
          <p className="mt-1 text-sm text-muted-foreground">
            回答几个简单问题，我们会根据你的目标和风险偏好重新建议。
          </p>
        </div>
        <Button className="h-12 rounded-2xl bg-foreground px-6 text-base font-medium text-background hover:bg-foreground/90">
          <PieChartIcon className="mr-2 h-4 w-4" />
          重新评估
        </Button>
      </motion.div>
    </div>
  );
}
