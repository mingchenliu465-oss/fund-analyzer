"use client";

import { MetricCard } from "@/components/metric-card";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Lightbulb,
  Target,
  TrendingUp,
  Trophy,
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

const returnData = [
  { month: "1月", return: 1.0, cumulative: 1.0 },
  { month: "2月", return: 1.02, cumulative: 1.02 },
  { month: "3月", return: 0.98, cumulative: 1.0 },
  { month: "4月", return: 1.04, cumulative: 1.04 },
  { month: "5月", return: 1.01, cumulative: 1.05 },
  { month: "6月", return: 1.03, cumulative: 1.08 },
  { month: "7月", return: 1.05, cumulative: 1.13 },
  { month: "8月", return: 0.97, cumulative: 1.1 },
  { month: "9月", return: 1.06, cumulative: 1.16 },
  { month: "10月", return: 1.02, cumulative: 1.19 },
  { month: "11月", return: 0.99, cumulative: 1.17 },
  { month: "12月", return: 1.04, cumulative: 1.22 },
];

const attributionData = [
  { name: "选股贡献", value: 45, color: "#171717" },
  { name: "择时贡献", value: 20, color: "#0071e3" },
  { name: "行业配置", value: 25, color: "#6e6e73" },
  { name: "交易成本", value: -10, color: "#ff3b30" },
];

const trades = [
  { date: "2024-12-15", fund: "沪深300指数基金", action: "买入", amount: "¥5,000", status: "up" },
  { date: "2024-11-28", fund: "易方达消费行业", action: "卖出", amount: "¥3,200", status: "down" },
  { date: "2024-10-10", fund: "易方达裕丰回报", action: "买入", amount: "¥10,000", status: "up" },
  { date: "2024-09-05", fund: "南方天天利货币", action: "转入", amount: "¥2,000", status: "up" },
  { date: "2024-08-20", fund: "沪深300指数基金", action: "定投", amount: "¥2,000", status: "up" },
];

const insights = [
  {
    icon: Trophy,
    title: "亮点",
    content: "7-9 月把握住了成长反弹，选股贡献主要来自于科技与消费板块的超配。",
  },
  {
    icon: Target,
    title: "偏差",
    content: "8 月市场调整时仓位偏重，导致当月回撤较大，需加强纪律性再平衡。",
  },
  {
    icon: Lightbulb,
    title: "建议",
    content: "继续坚持定投宽基，降低单笔择时权重；债券基金比例可适度提升至 35%。",
  },
];

export default function ReviewPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Header */}
      <section className="mb-12">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              投资复盘
            </h1>
            <p className="mt-3 max-w-2xl text-lg text-muted-foreground">
              回顾过去一年的投资表现，识别收益来源与改进空间。
            </p>
          </div>
          <span className="inline-flex w-fit items-center rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-sm font-medium text-warning">
            模拟数据 · 仅供演示
          </span>
        </motion.div>
      </section>

      {/* Metrics */}
      <div className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="年度收益（模拟）"
          value="+21.7%"
          trend="up"
          trendValue="示例"
          subtitle="非真实账户"
          icon={TrendingUp}
          delay={0.1}
        />
        <MetricCard
          title="最大单笔亏损（模拟）"
          value="-8.4%"
          trend="down"
          trendValue="示例"
          subtitle="非真实账户"
          icon={ArrowDownRight}
          delay={0.15}
        />
        <MetricCard
          title="胜率（模拟）"
          value="62%"
          trend="neutral"
          subtitle="示例统计"
          icon={Target}
          delay={0.2}
        />
        <MetricCard
          title="交易次数（模拟）"
          value="18 笔"
          trend="neutral"
          subtitle="示例记录"
          icon={Activity}
          delay={0.25}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.28, ease: [0.23, 1, 0.32, 1] }}
        className="mb-10 rounded-2xl border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground"
      >
        当前页面展示的是<strong className="text-foreground">模拟复盘数据</strong>，用于演示功能布局。
        后续接入真实交易账户或持仓数据后，这里的收益、交易记录与归因分析将自动替换为你的实际投资数据。
      </motion.div>

      {/* Charts Grid */}
      <div className="mb-10 grid gap-6 lg:grid-cols-2">
        {/* Return Curve */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-3xl border border-border bg-background p-6 sm:p-8"
        >
          <div className="mb-4">
            <h3 className="text-lg font-semibold tracking-tight">累计收益走势（模拟）</h3>
            <p className="text-sm text-muted-foreground">演示用净值变化，不代表真实账户</p>
          </div>
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={returnData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <defs>
                  <linearGradient id="colorCumulative" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0071e3" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#0071e3" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="month"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                  dy={8}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                  domain={[0.95, 1.25]}
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
                  formatter={(value) => [
                    `${(typeof value === "number" ? value * 100 : 0).toFixed(2)}%`,
                    "累计净值",
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="cumulative"
                  stroke="#0071e3"
                  strokeWidth={2}
                  fill="url(#colorCumulative)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Attribution */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-3xl border border-border bg-background p-6 sm:p-8"
        >
          <div className="mb-4">
            <h3 className="text-lg font-semibold tracking-tight">收益归因（模拟）</h3>
            <p className="text-sm text-muted-foreground">超额收益来源拆解示例</p>
          </div>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={attributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {attributionData.map((entry, index) => (
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
          <div className="mt-2 grid grid-cols-2 gap-3">
            {attributionData.map((item) => (
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
                <span className={`text-sm font-medium ${item.value >= 0 ? "text-positive" : "text-negative"}`}>
                  {item.value > 0 ? "+" : ""}
                  {item.value}%
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Trade History */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.45, ease: [0.23, 1, 0.32, 1] }}
        className="mb-10 rounded-3xl border border-border bg-background p-2"
      >
        <div className="flex items-center justify-between px-6 py-5">
          <div>
            <h3 className="text-lg font-semibold tracking-tight">近期交易（模拟）</h3>
            <p className="text-sm text-muted-foreground">示例交易记录，非真实流水</p>
          </div>
          <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
            DEMO
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border text-left text-sm text-muted-foreground">
                <th className="px-4 py-3 font-medium">日期</th>
                <th className="px-4 py-3 font-medium">基金</th>
                <th className="px-4 py-3 font-medium">操作</th>
                <th className="px-4 py-3 text-right font-medium">金额</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr
                  key={`${trade.date}-${trade.fund}`}
                  className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
                >
                  <td className="px-4 py-4 text-sm text-muted-foreground">{trade.date}</td>
                  <td className="px-4 py-4 font-medium">{trade.fund}</td>
                  <td className="px-4 py-4">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                        trade.action === "卖出"
                          ? "bg-negative/10 text-negative"
                          : "bg-positive/10 text-positive"
                      }`}
                    >
                      {trade.action === "卖出" ? (
                        <ArrowDownRight className="h-3 w-3" />
                      ) : (
                        <ArrowUpRight className="h-3 w-3" />
                      )}
                      {trade.action}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-right font-medium">{trade.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>

      {/* Insights */}
      <section>
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.55, ease: [0.23, 1, 0.32, 1] }}
          className="mb-6 text-xl font-semibold tracking-tight"
        >
          复盘建议（示例）
        </motion.h2>
        <div className="grid gap-6 sm:grid-cols-3">
          {insights.map((item, index) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.5,
                delay: 0.6 + index * 0.05,
                ease: [0.23, 1, 0.32, 1],
              }}
              className="rounded-3xl border border-border bg-muted/40 p-6"
            >
              <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-2xl bg-background"
              >
                <item.icon className="h-4 w-4 text-foreground" />
              </div>
              <h4 className="mb-2 font-semibold">{item.title}</h4>
              <p className="text-sm leading-relaxed text-muted-foreground">{item.content}</p>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
