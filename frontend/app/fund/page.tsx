"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RotateCcw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataState, PageHeader, PlainConclusion, ResearchSection, SourceNote } from "@/components/research-ui";
import { FundSummary, formatCurrency, formatPercent, getAllFunds } from "@/services/fund";

export default function FundListPage() {
  const [funds, setFunds] = useState<FundSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setLoading(true);
      getAllFunds(query)
        .then((rows) => {
          setFunds(rows);
          setFailed(false);
        })
        .catch((error) => {
          console.error("Fund list request failed", error);
          setFunds([]);
          setFailed(true);
        })
        .finally(() => setLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [query, reloadKey]);

  const filteredFunds = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return funds;
    return funds.filter((fund) => fund.code.toLowerCase().includes(q) || fund.name.toLowerCase().includes(q));
  }, [funds, query]);

  return (
    <div className="page-container">
      <PageHeader title="基金列表" description="按名称或代码筛选，先比较最新净值、日涨跌与近一年收益，再进入详情。" />
      <PlainConclusion note={null}>
        {loading
          ? "正在读取基金数据，表格会在返回后更新。"
          : failed
            ? "基金数据暂时不可用。请重试或缩短搜索条件；页面不会用示例基金补位。"
            : query
              ? `“${query}”当前匹配 ${filteredFunds.length} 只基金。缺失的净值或收益以“—”表示。`
              : `当前显示 ${filteredFunds.length} 只基金。先看近一年收益，再结合风险和净值日期判断是否值得继续研究。`}
      </PlainConclusion>

      <ResearchSection title="筛选基金" description="搜索会请求现有后端接口，本地筛选只作为兜底。">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="输入基金代码 / 名称筛选"
              className="pl-10"
              aria-label="筛选基金"
            />
          </div>
          <Button variant="outline" onClick={() => setQuery("")} disabled={!query}>
            <RotateCcw className="h-4 w-4" /> 重置
          </Button>
        </div>
      </ResearchSection>

      <ResearchSection title="基金数据" description="红涨绿跌；净值日期与数据状态用于识别过期或不可用行情。">
        {loading && filteredFunds.length === 0 ? (
          <DataState kind="loading" title="正在加载真实数据" description="基金列表可能需要几秒钟，请稍候。" />
        ) : failed ? (
          <DataState
            kind="error"
            title="数据暂时不可用"
            description="请检查网络或稍后重试，未使用替代数据。"
            action={<Button variant="outline" onClick={() => setReloadKey((value) => value + 1)}>重新加载</Button>}
          />
        ) : filteredFunds.length === 0 ? (
          <DataState kind="empty" title="没有匹配的基金" description="试试完整基金代码，或减少名称中的关键字。" />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>基金名称</th>
                  <th className="hidden md:table-cell">类型</th>
                  <th className="numeric">净值</th>
                  <th className="numeric">日涨跌</th>
                  <th className="numeric">近一年收益</th>
                  <th className="numeric hidden lg:table-cell">风险等级</th>
                  <th className="numeric hidden lg:table-cell">规模</th>
                  <th className="numeric hidden xl:table-cell">热度</th>
                  <th className="numeric">操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredFunds.map((fund) => (
                  <tr key={fund.code}>
                    <td>
                      <Link href={`/fund/${fund.code}`} className="font-medium hover:text-accent">{fund.name}</Link>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {fund.code}{fund.navDate ? ` · ${fund.navDate}` : " · 净值日期缺失"}
                      </div>
                    </td>
                    <td className="hidden text-muted-foreground md:table-cell">{fund.type || "—"}</td>
                    <td className="numeric">{formatCurrency(fund.nav, 4)}</td>
                    <td className={`numeric font-semibold ${fund.changePct == null ? "text-muted-foreground" : fund.changePct >= 0 ? "text-positive" : "text-negative"}`}>
                      {fund.changePct == null ? "—" : formatPercent(fund.changePct * 0.01)}
                    </td>
                    <td className={`numeric font-semibold ${fund.oneYearReturn == null ? "text-muted-foreground" : fund.oneYearReturn >= 0 ? "text-positive" : "text-negative"}`}>
                      {formatPercent(fund.oneYearReturn)}
                    </td>
                    <td className="numeric hidden lg:table-cell">{fund.riskLevel ?? "—"}</td>
                    <td className="numeric hidden text-muted-foreground lg:table-cell">{fund.size || "—"}</td>
                    <td className="numeric hidden xl:table-cell"><HeatValue heat={fund.heat} /></td>
                    <td className="numeric whitespace-nowrap">
                      <Link href={`/fund/${fund.code}`} className="text-link mr-3">详情</Link>
                      <Link href="/compare" className="text-link">对比</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <SourceNote>来源：akshare 公开接口。每只基金的净值日期可能不同；“—”表示接口未提供或无法计算，不代表 0。</SourceNote>
      </ResearchSection>
    </div>
  );
}

function HeatValue({ heat }: { heat: number | null }) {
  if (heat == null) return <span className="text-muted-foreground">—</span>;
  if (heat >= 80) return <span>高热 {heat}</span>;
  if (heat >= 50) return <span>活跃 {heat}</span>;
  return <span>一般 {heat}</span>;
}
