"use client";

import Link from "next/link";
import { FundSummary, formatCurrency, formatPercent } from "@/services/fund";
import { Badge } from "./ui/badge";
import { TrendingDown, TrendingUp } from "lucide-react";

interface RecentWatchedProps {
  funds: FundSummary[];
}

export function RecentWatched({ funds }: RecentWatchedProps) {
  if (funds.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
        <p className="text-sm">暂无浏览记录</p>
        <p className="mt-1 text-xs">搜索并查看基金后将在此显示</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {funds.map((fund) => {
        const chg = fund.changePct ?? 0;
        return (
        <Link
          key={fund.code}
          href={`/fund/${fund.code}`}
          className="flex items-center justify-between rounded-xl border border-border bg-background p-3 transition-colors hover:bg-muted/40"
        >
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{fund.name ?? "—"}</div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span>{fund.code}</span>
              <span>·</span>
              <Badge variant="outline">{fund.type ?? "—"}</Badge>
            </div>
          </div>
          <div className="ml-3 text-right">
            <div className="text-sm font-medium tabular-nums">{formatCurrency(fund.nav, 4)}</div>
            <div
              className={`inline-flex items-center gap-0.5 text-xs font-medium tabular-nums ${
                chg >= 0 ? "text-positive" : "text-negative"
              }`}
            >
              {chg >= 0 ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {formatPercent(chg * 0.01)}
            </div>
          </div>
        </Link>
        );
      })}
    </div>
  );
}
