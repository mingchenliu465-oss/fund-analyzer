"use client";

import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BarChart3,
  FileText,
  PieChart,
  Search,
  Scale,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";

const quickLinks = [
  {
    href: "/fund",
    title: "基金分析",
    desc: "查询单只基金业绩与风险",
    icon: BarChart3,
    color: "bg-accent",
  },
  {
    href: "/portfolio",
    title: "投资组合",
    desc: "生成并跟踪资产配置",
    icon: PieChart,
    color: "bg-foreground",
  },
  {
    href: "/review",
    title: "投资复盘",
    desc: "回顾收益与优化建议",
    icon: FileText,
    color: "bg-muted",
  },
  {
    href: "/compare",
    title: "基金对比",
    desc: "多只基金横向比较",
    icon: Scale,
    color: "bg-accent",
  },
];

const marketIndices = [
  { name: "沪深300", value: "3,842.15", change: "+1.24%", up: true },
  { name: "中证500", value: "5,621.38", change: "+0.86%", up: true },
  { name: "创业板指", value: "2,018.72", change: "-0.34%", up: false },
  { name: "中证全债", value: "245.18", change: "+0.05%", up: true },
];

const recentFunds = [
  { code: "000300", name: "沪深300指数基金", type: "股票型", return: "+12.84%", up: true },
  { code: "110022", name: "易方达消费行业", type: "股票型", return: "+8.72%", up: true },
  { code: "000171", name: "易方达裕丰回报", type: "债券型", return: "+4.15%", up: true },
  { code: "003474", name: "南方天天利货币", type: "货币型", return: "+1.92%", up: true },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      {/* Hero */}
      <section className="mb-16">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-3xl border border-border bg-background p-8 sm:p-12"
        >
          <div className="max-w-2xl">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">
              AI 基金投资分析助手
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
              专业、克制、优雅地理解基金表现。输入代码，快速获得业绩、风险与配置建议。
            </p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
            className="mt-8 flex flex-col gap-3 sm:flex-row"
          >
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="输入基金代码 / 名称，例如 000001 或 华夏成长"
                className="h-12 rounded-2xl border-border bg-muted/40 pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
              />
            </div>
            <Link href="/fund">
              <Button className="h-12 rounded-2xl bg-foreground px-8 text-base font-medium text-background hover:bg-foreground/90">
                分析
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </motion.div>
        </motion.div>
      </section>

      {/* Quick Links */}
      <section className="mb-16">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15, ease: [0.23, 1, 0.32, 1] }}
          className="mb-6 text-xl font-semibold tracking-tight"
        >
          快速入口
        </motion.h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {quickLinks.map((item, index) => (
            <motion.div
              key={item.href}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.5,
                delay: 0.2 + index * 0.05,
                ease: [0.23, 1, 0.32, 1],
              }}
            >
              <Link
                href={item.href}
                className="group block rounded-3xl border border-border bg-background p-6 transition-shadow hover:shadow-lg"
              >
                <div
                  className={`mb-4 flex h-10 w-10 items-center justify-center rounded-2xl ${item.color} ${
                    item.color === "bg-muted" ? "text-foreground" : "text-white"
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                </div>
                <h3 className="font-semibold">{item.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{item.desc}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Market Overview */}
      <section className="mb-16">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="mb-6 text-xl font-semibold tracking-tight"
        >
          市场概览
        </motion.h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {marketIndices.map((item, index) => (
            <MetricCard
              key={item.name}
              title={item.name}
              value={item.value}
              trend={item.up ? "up" : "down"}
              trendValue={item.change}
              subtitle="今日收盘"
              icon={item.up ? TrendingUp : TrendingDown}
              delay={0.4 + index * 0.05}
            />
          ))}
        </div>
      </section>

      {/* Recent Funds */}
      <section>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.55, ease: [0.23, 1, 0.32, 1] }}
          className="mb-6 flex items-center justify-between"
        >
          <h2 className="text-xl font-semibold tracking-tight">热门基金</h2>
          <Link
            href="/fund"
            className="flex items-center text-sm font-medium text-accent hover:underline"
          >
            查看全部
            <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-3xl border border-border bg-background p-2"
        >
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border text-left text-sm text-muted-foreground">
                  <th className="px-4 py-3 font-medium">基金名称</th>
                  <th className="px-4 py-3 font-medium">代码</th>
                  <th className="px-4 py-3 font-medium">类型</th>
                  <th className="px-4 py-3 text-right font-medium">近一年收益</th>
                </tr>
              </thead>
              <tbody>
                {recentFunds.map((fund) => (
                  <tr
                    key={fund.code}
                    className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
                  >
                    <td className="px-4 py-4">
                      <Link
                        href="/fund"
                        className="font-medium hover:text-accent"
                      >
                        {fund.name}
                      </Link>
                    </td>
                    <td className="px-4 py-4 text-sm text-muted-foreground">
                      {fund.code}
                    </td>
                    <td className="px-4 py-4 text-sm text-muted-foreground">
                      {fund.type}
                    </td>
                    <td
                      className={`px-4 py-4 text-right font-medium ${
                        fund.up ? "text-positive" : "text-negative"
                      }`}
                    >
                      {fund.return}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
