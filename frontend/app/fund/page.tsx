"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { BarChart3, RotateCcw, Scale, Search, TrendingDown, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { FundSummary, formatCurrency, formatPercent, getAllFunds } from "@/services/fund";

export default function FundListPage() {
  const [funds, setFunds] = useState<FundSummary[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      getAllFunds(query).then(setFunds);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const filteredFunds = useMemo(() => {
    // 真实模式下后端已按 query 过滤，本地仅做兜底
    const q = query.trim().toLowerCase();
    if (!q) return funds;
    return funds.filter(
      (f) => f.code.toLowerCase().includes(q) || f.name.toLowerCase().includes(q)
    );
  }, [funds, query]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Header */}
      <section className="mb-5">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
        >
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">基金列表</h1>
          <p className="mt-1 text-sm text-muted-foreground">全部基金一览，支持按名称 / 代码筛选</p>
        </motion.div>
      </section>

      {/* Search */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
        className="mb-5 flex flex-col gap-3 sm:flex-row"
      >
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入基金代码 / 名称筛选"
            className="h-11 rounded-2xl border-border bg-background pl-11 text-base shadow-sm placeholder:text-muted-foreground/60"
          />
        </div>
        <Button
          variant="outline"
          onClick={() => setQuery("")}
          className="h-11 rounded-2xl px-5"
        >
          <RotateCcw className="mr-2 h-4 w-4" />
          重置
        </Button>
      </motion.div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.23, 1, 0.32, 1] }}
        className="rounded-2xl border border-border bg-background p-2"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-3 py-3 font-medium">基金名称</th>
                <th className="px-3 py-3 font-medium">代码</th>
                <th className="px-3 py-3 font-medium">类型</th>
                <th className="px-3 py-3 text-right font-medium">净值</th>
                <th className="px-3 py-3 text-right font-medium">日涨跌</th>
                <th className="px-3 py-3 text-right font-medium">近一年收益</th>
                <th className="px-3 py-3 text-right font-medium">风险等级</th>
                <th className="px-3 py-3 text-right font-medium">规模</th>
                <th className="px-3 py-3 text-right font-medium">热度</th>
                <th className="px-3 py-3 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredFunds.map((fund) => (
                <tr
                  key={fund.code}
                  className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
                >
                  <td className="px-3 py-3">
                    <Link href={`/fund/${fund.code}`} className="font-medium hover:text-accent">
                      {fund.name}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{fund.code}</td>
                  <td className="px-3 py-3">
                    <Badge variant="outline">{fund.type}</Badge>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {formatCurrency(fund.nav, 4)}
                  </td>
                  <td
                    className={`px-3 py-3 text-right font-medium tabular-nums ${
                      fund.changePct >= 0 ? "text-positive" : "text-negative"
                    }`}
                  >
                    <span className="inline-flex items-center gap-1">
                      {fund.changePct >= 0 ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {formatPercent(fund.changePct * 0.01)}
                    </span>
                  </td>
                  <td
                    className={`px-3 py-3 text-right font-medium tabular-nums ${
                      fund.oneYearReturn >= 0 ? "text-positive" : "text-negative"
                    }`}
                  >
                    {formatPercent(fund.oneYearReturn)}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <Badge variant="outline">{fund.riskLevel}</Badge>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums text-muted-foreground">
                    {fund.size}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <HeatBadge heat={fund.heat} />
                  </td>
                  <td className="px-3 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link href={`/fund/${fund.code}`}>
                        <Button variant="default" size="sm" className="h-8 rounded-lg px-3">
                          <BarChart3 className="mr-1 h-3 w-3" />
                          分析
                        </Button>
                      </Link>
                      <Link href="/compare">
                        <Button variant="outline" size="sm" className="h-8 rounded-lg px-3">
                          <Scale className="mr-1 h-3 w-3" />
                          对比
                        </Button>
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredFunds.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-muted-foreground">
                    未找到匹配的基金
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}

function HeatBadge({ heat }: { heat: number }) {
  if (heat >= 80) return <Badge variant="negative">高热 {heat}</Badge>;
  if (heat >= 50) return <Badge variant="warning">活跃 {heat}</Badge>;
  return <Badge variant="outline">一般 {heat}</Badge>;
}
