"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MetricCard } from "@/components/metric-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BarChart3,
  Clock,
  FileText,
  PieChart,
  Scale,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { PortfolioOverview } from "@/components/portfolio-overview";
import { FundRankings } from "@/components/fund-rankings";
import { RecentWatched } from "@/components/recent-watched";
import { useFundSearch } from "@/hooks/use-fund-search";
import {
  MarketStatus,
  PortfolioOverview as PortfolioOverviewData,
  formatPercent,
  getMarketIndices,
  getMarketStatus,
  getPortfolioOverview,
  getFundRankings,
  getRecentlyWatched,
} from "@/services/fund";

// ── React Query staleTime 配置 ──

const STALE_TIME = {
  rankings: 30 * 60 * 1000,       // 基金排行榜：30 分钟（每日更新一次）
  marketIndices: 2 * 60 * 1000,    // 市场指数：2 分钟（实时变动）
  marketStatus: 5 * 60 * 1000,     // 市场状态：5 分钟（仅在开盘/午休/收盘时切换）
  recentlyWatched: 0,              // 最近浏览：本地 localStorage，每次进入首页都读取最新
  portfolioOverview: 5 * 60 * 1000,// 组合总览：5 分钟（基于持仓 + 净值变化）
} as const;

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

const emptyPortfolio: PortfolioOverviewData = {
  totalAssets: 0, todayReturn: 0, todayReturnPct: 0,
  cumulativeReturn: 0, cumulativeReturnPct: 0,
  allocation: [], riskLevel: "暂无", riskScore: 0,
};

const MARKET_INDEX_CODE_BY_NAME: Record<string, string> = {
  上证指数: "sh000001",
  深证成指: "sz399001",
  沪深300: "sh000300",
  创业板指: "sz399006",
  中证500: "sh000905",
  中证全债: "H11001",
};

export default function HomePage() {
  const [query, setQuery] = useState("");
  const { suggestions } = useFundSearch(query, 6);

  // ── React Query: 数据请求自动缓存、去重、后台更新 ──

  const { data: rankings = [] } = useQuery({
    queryKey: ["rankings", 8],
    queryFn: () => getFundRankings(8),
    staleTime: STALE_TIME.rankings,
  });

  const { data: recentWatched = [] } = useQuery({
    queryKey: ["recentlyWatched"],
    queryFn: getRecentlyWatched,
    staleTime: STALE_TIME.recentlyWatched,
  });

  const { data: marketIndices = [] } = useQuery({
    queryKey: ["marketIndices"],
    queryFn: getMarketIndices,
    staleTime: STALE_TIME.marketIndices,
  });

  const { data: marketStatus = null } = useQuery<MarketStatus | null>({
    queryKey: ["marketStatus"],
    queryFn: getMarketStatus,
    staleTime: STALE_TIME.marketStatus,
  });

  const { data: portfolio = emptyPortfolio } = useQuery<PortfolioOverviewData>({
    queryKey: ["portfolioOverview"],
    queryFn: getPortfolioOverview,
    staleTime: STALE_TIME.portfolioOverview,
  });

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Hero + Market status */}
      <section className="mb-5">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-5 sm:p-6"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-xl">
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                AI 基金投资分析助手
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                专业、克制、优雅地理解基金表现。输入代码，快速获得业绩、风险与配置建议。
              </p>
            </div>
            {marketStatus && (
              <div className="flex items-center gap-2 rounded-xl border border-border bg-muted/40 px-3 py-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <div className="text-sm">
                  <div className="font-medium">{marketStatus.status}</div>
                  <div className="text-xs text-muted-foreground">
                    {marketStatus.session} · {marketStatus.updateTime}
                  </div>
                </div>
              </div>
            )}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
            className="relative mt-5 max-w-xl"
          >
            <div className="relative">
              <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="输入基金代码 / 名称，例如 000001 或 华夏成长"
                className="h-11 rounded-2xl border-border bg-muted/40 pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
              />
            </div>
            {suggestions.length > 0 && (
              <div className="absolute z-20 mt-2 w-full rounded-2xl border border-border bg-background p-2 shadow-lg">
                {suggestions.map((fund) => (
                  <Link
                    key={fund.code}
                    href={`/fund/${fund.code}`}
                    onClick={() => setQuery("")}
                    className="flex items-center justify-between rounded-xl px-3 py-2.5 text-sm hover:bg-muted"
                  >
                    <span className="font-medium">{fund.name}</span>
                    <span className="text-muted-foreground">{fund.code}</span>
                  </Link>
                ))}
              </div>
            )}
          </motion.div>
        </motion.div>
      </section>

      {/* Quick Links */}
      <section className="mb-5">
        <motion.h2
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15, ease: [0.23, 1, 0.32, 1] }}
          className="mb-3 text-base font-semibold tracking-tight"
        >
          快速入口
        </motion.h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
                className="group block rounded-2xl border border-border bg-background p-4 transition-shadow hover:shadow-lg"
              >
                <div
                  className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl ${item.color} ${
                    item.color === "bg-muted" ? "text-foreground" : "text-white"
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                </div>
                <h3 className="text-sm font-semibold">{item.title}</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">{item.desc}</p>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Portfolio + Market Indices */}
      <section className="mb-5 grid gap-4 lg:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5 lg:col-span-2"
        >
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold tracking-tight">我的组合总览</h2>
              <p className="text-xs text-muted-foreground">
                {portfolio.totalAssets > 0 ? "真实持仓数据" : "暂无持仓记录"}
              </p>
            </div>
            <Link href="/portfolio">
              <Button variant="outline" size="sm" className="h-8 rounded-lg px-3">
                {portfolio.totalAssets > 0 ? "查看详情" : "录入持仓"}
                <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </div>
          {portfolio.totalAssets > 0 ? (
              <PortfolioOverview data={portfolio} />
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <PieChart className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm font-medium">暂无持仓数据</p>
                <p className="mt-1 text-xs">前往投资组合页面录入真实交易</p>
                <Link href="/portfolio" className="mt-3">
                  <Button size="sm" className="h-8 rounded-lg px-3">
                    开始录入
                    <ArrowRight className="ml-1 h-3 w-3" />
                  </Button>
                </Link>
              </div>
            )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h2 className="text-base font-semibold tracking-tight">市场指数表现</h2>
            <p className="text-xs text-muted-foreground">主要宽基指数收盘情况</p>
          </div>
          <div className="grid gap-2">
            {marketIndices.length > 0 ? (
              marketIndices.map((item, index) => (
                <Link
                  key={item.name}
                  href={`/market/${item.code || MARKET_INDEX_CODE_BY_NAME[item.name]}`}
                  aria-label={`查看${item.name}市场详情`}
                  className="block rounded-3xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20"
                >
                  <MetricCard
                    title={item.name}
                    value={item.value}
                    trend={item.up ? "up" : "down"}
                    trendValue={formatPercent(item.change * 0.01)}
                    subtitle="今日收盘"
                    icon={item.up ? TrendingUp : TrendingDown}
                    delay={0.45 + index * 0.05}
                  />
                </Link>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <p className="text-sm">暂无指数数据</p>
                <p className="mt-1 text-xs">数据源暂时不可用</p>
              </div>
            )}
          </div>
        </motion.div>
      </section>

      {/* Rankings + Recently watched */}
      <section className="grid gap-4 lg:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.55, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5 lg:col-span-2"
        >
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold tracking-tight">热门基金排行榜</h2>
              <p className="text-xs text-muted-foreground">按近一年收益排序</p>
            </div>
            <Link
              href="/fund"
              className="flex items-center text-xs font-medium text-accent hover:underline"
            >
              查看全部
              <ArrowRight className="ml-1 h-3 w-3" />
            </Link>
          </div>
          <FundRankings funds={rankings} />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="rounded-2xl border border-border bg-background p-4 sm:p-5"
        >
          <div className="mb-3">
            <h2 className="text-base font-semibold tracking-tight">最近浏览</h2>
            <p className="text-xs text-muted-foreground">近期查看过的基金</p>
          </div>
          <RecentWatched funds={recentWatched} />
        </motion.div>
      </section>
    </div>
  );
}
