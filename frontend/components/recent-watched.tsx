"use client";

import Link from "next/link";
import { FundSummary, formatCurrency } from "@/services/fund";
import { Badge } from "./ui/badge";
import { SignedChange } from "@/components/signed-change";

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
      {funds.map((fund) => (
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
            {/* 涨跌幅缺失时后端返回 null：SignedChange 统一显示「—」，
                不会伪装成 "上涨箭头 + +0.00%" 的持平报价。 */}
            <div className="text-xs">
              <SignedChange value={fund.changePct} />
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
