"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { PortfolioOverview } from "@/components/portfolio-overview";
import { FundRankings } from "@/components/fund-rankings";
import { RecentWatched } from "@/components/recent-watched";
import {
  DataState,
  PageHeader,
  PlainConclusion,
  ResearchSection,
  SourceNote,
} from "@/components/research-ui";
import { useFundSearch } from "@/hooks/use-fund-search";
import {
  MarketStatus,
  PortfolioOverview as PortfolioOverviewData,
  formatCurrency,
  formatPercent,
  getMarketIndices,
  getMarketStatus,
  getPortfolioOverview,
  getFundRankings,
  getRecentlyWatched,
} from "@/services/fund";

const STALE_TIME = {
  rankings: 30 * 60 * 1000,
  marketIndices: 2 * 60 * 1000,
  marketStatus: 5 * 60 * 1000,
  recentlyWatched: 0,
  portfolioOverview: 5 * 60 * 1000,
} as const;

const emptyPortfolio: PortfolioOverviewData = {
  totalAssets: 0,
  todayReturn: null,
  todayReturnPct: null,
  cumulativeReturn: 0,
  cumulativeReturnPct: 0,
  allocation: [],
  riskLevel: null,
  riskScore: null,
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
  const { suggestions, isSearching, isError } = useFundSearch(query, 6);

  const rankingsQuery = useQuery({
    queryKey: ["rankings", 8],
    queryFn: () => getFundRankings(8),
    staleTime: STALE_TIME.rankings,
  });
  const recentQuery = useQuery({
    queryKey: ["recentlyWatched"],
    queryFn: getRecentlyWatched,
    staleTime: STALE_TIME.recentlyWatched,
  });
  const indicesQuery = useQuery({
    queryKey: ["marketIndices"],
    queryFn: getMarketIndices,
    staleTime: STALE_TIME.marketIndices,
  });
  const { data: marketStatus = null } = useQuery<MarketStatus | null>({
    queryKey: ["marketStatus"],
    queryFn: getMarketStatus,
    staleTime: STALE_TIME.marketStatus,
  });
  const portfolioQuery = useQuery<PortfolioOverviewData>({
    queryKey: ["portfolioOverview"],
    queryFn: getPortfolioOverview,
    staleTime: STALE_TIME.portfolioOverview,
  });

  const rankings = rankingsQuery.data ?? [];
  const marketIndices = indicesQuery.data ?? [];
  const portfolio = portfolioQuery.data ?? emptyPortfolio;

  return (
    <div className="page-container">
      <PageHeader
        title="基金与市场数据"
        description="输入基金代码或名称，查看历史收益、回撤和持仓；组合页只使用你录入的真实交易。"
        action={
          marketStatus ? (
            <div className="text-left text-xs text-muted-foreground sm:text-right">
              <span className="block font-medium text-foreground">{marketStatus.status}</span>
              <span>{marketStatus.session} · {marketStatus.updateTime}</span>
            </div>
          ) : undefined
        }
      />

      <section className="relative mb-10 max-w-3xl" aria-label="基金搜索">
        <Search className="pointer-events-none absolute left-3 top-3.5 h-5 w-5 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="例如 000001 或 华夏成长"
          className="h-12 pl-11"
          aria-label="搜索基金代码或名称"
        />
        {query.trim() && (
          <div className="absolute z-20 mt-1 w-full border border-border bg-background py-2">
            {suggestions.length > 0 ? (
              suggestions.map((fund) => (
                <Link
                  key={fund.code}
                  href={`/fund/${fund.code}`}
                  onClick={() => setQuery("")}
                  className="flex min-h-11 items-center justify-between gap-4 px-4 py-2 text-sm hover:bg-muted"
                >
                  <span className="truncate font-medium">{fund.name}</span>
                  <span className="numeric text-xs text-muted-foreground">{fund.code}</span>
                </Link>
              ))
            ) : (
              <p className="px-4 py-3 text-xs text-muted-foreground">
                {isSearching ? "正在搜索…" : isError ? "搜索暂时不可用，请稍后重试。" : "暂时没有匹配结果。"}
              </p>
            )}
          </div>
        )}
      </section>

      <PlainConclusion label="你的组合" note={null}>
        {portfolioQuery.isLoading
          ? "正在读取组合数据；基金搜索和市场行情仍可分别使用。"
          : portfolioQuery.isError
            ? "组合数据暂时不可用；基金与市场数据仍可分别查看，未使用替代数据。"
            : portfolio.totalAssets != null && portfolio.totalAssets > 0
              ? `当前组合总市值为 ${formatCurrency(portfolio.totalAssets)}，累计收益为 ${formatCurrency(portfolio.cumulativeReturn)}。先看整体，再下钻到每只持仓。`
              : "还没有可用的持仓记录。可以先搜索基金，或到“我的组合”录入真实交易。"}
      </PlainConclusion>

      <nav className="mb-8 flex flex-wrap gap-x-6 gap-y-2 border-b border-border pb-5 text-sm" aria-label="常用功能">
        <Link className="text-link" href="/compare">基金对比</Link>
        <Link className="text-link" href="/workbench">分析工作台</Link>
        <Link className="text-link" href="/review">投资复盘</Link>
      </nav>

      <ResearchSection
        title="我的组合总览"
        description="资产、收益与仓位比例；没有数据的指标显示为“—”。"
        action={
          <Link href="/portfolio" className="text-link inline-flex items-center gap-1 text-sm">
            {portfolio.totalAssets != null && portfolio.totalAssets > 0 ? "查看持仓" : "录入持仓"}
            <ArrowRight className="h-4 w-4" />
          </Link>
        }
      >
        {portfolioQuery.isLoading ? (
          <DataState kind="loading" title="正在读取组合数据" />
        ) : portfolioQuery.isError ? (
          <DataState kind="error" title="组合数据暂时不可用" description="请稍后重新加载；这里不会使用假数据填充。" />
        ) : (
          <PortfolioOverview data={portfolio} />
        )}
      </ResearchSection>

      <ResearchSection title="主要市场指数" description="指数最新点位与日涨跌；点击名称可查看历史走势和回撤。">
        {indicesQuery.isLoading ? (
          <DataState kind="loading" title="正在读取指数行情" />
        ) : marketIndices.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>指数</th><th className="numeric">最新点位</th><th className="numeric">日涨跌</th><th className="numeric hidden sm:table-cell">数据说明</th></tr></thead>
              <tbody>
                {marketIndices.map((item) => {
                  const code = item.code || MARKET_INDEX_CODE_BY_NAME[item.name];
                  return (
                    <tr key={item.name}>
                      <td>{code ? <Link className="font-medium hover:text-accent" href={`/market/${code}`}>{item.name}</Link> : item.name}</td>
                      <td className="numeric font-semibold">{item.value || "—"}</td>
                      <td className={`numeric font-semibold ${item.change >= 0 ? "text-positive" : "text-negative"}`}>{formatPercent(item.change * 0.01)}</td>
                      <td className="numeric hidden text-xs text-muted-foreground sm:table-cell">交易日更新</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <DataState kind="error" title="指数数据暂时不可用" description="未使用任何替代行情。" />
        )}
        <SourceNote>来源：akshare 公开接口；行情日期以各指数详情页的最新交易日为准。</SourceNote>
      </ResearchSection>

      <ResearchSection
        title="近一年收益排行"
        description="按后端返回的近一年收益排序；历史不足一年的基金不以 0% 代替。"
        action={<Link href="/fund" className="text-link text-sm">查看基金列表</Link>}
      >
        {rankingsQuery.isLoading ? (
          <DataState kind="loading" title="正在读取基金排行" />
        ) : rankingsQuery.isError ? (
          <DataState kind="error" title="基金排行暂时不可用" description="请稍后重试；未使用示例基金或替代收益。" />
        ) : (
          <FundRankings funds={rankings} />
        )}
        <SourceNote>排行仅描述历史表现，不代表未来结果，也不构成买卖建议。</SourceNote>
      </ResearchSection>

      <ResearchSection title="最近浏览" description="保存在当前浏览器中的基金查看记录。">
        <RecentWatched funds={recentQuery.data ?? []} />
      </ResearchSection>
    </div>
  );
}
