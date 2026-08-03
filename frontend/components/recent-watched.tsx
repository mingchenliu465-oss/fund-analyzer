"use client";

import Link from "next/link";
import { FundSummary, formatCurrency, formatPercent } from "@/services/fund";
import { Badge } from "./ui/badge";
import { TrendingDown, TrendingUp } from "lucide-react";

interface RecentWatchedProps {
  funds: FundSummary[];
}

export function RecentWatched({ funds }: RecentWatchedProps) {
  return (
    <div className="space-y-3">
      {funds.map((fund) => (
        <Link
          key={fund.code}
          href={`/fund/${fund.code}`}
          className="flex items-center justify-between rounded-xl border border-border bg-background p-3 transition-colors hover:bg-muted/40"
        >
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium">{fund.name}</div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span>{fund.code}</span>
              <span>·</span>
              <Badge variant="outline">{fund.type}</Badge>
            </div>
          </div>
          <div className="ml-3 text-right">
            <div className="text-sm font-medium tabular-nums">{formatCurrency(fund.nav, 4)}</div>
            <div
              className={`inline-flex items-center gap-0.5 text-xs font-medium tabular-nums ${
                fund.changePct >= 0 ? "text-positive" : "text-negative"
              }`}
            >
              {fund.changePct >= 0 ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {formatPercent(fund.changePct * 0.01)}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
