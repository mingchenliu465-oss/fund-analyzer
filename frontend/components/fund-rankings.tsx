"use client";

import Link from "next/link";
import { FundSummary, formatPercent } from "@/services/fund";
import { Badge } from "./ui/badge";

interface FundRankingsProps {
  funds: FundSummary[];
}

export function FundRankings({ funds }: FundRankingsProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="px-3 py-2 font-medium">排名</th>
            <th className="px-3 py-2 font-medium">基金名称</th>
            <th className="px-3 py-2 font-medium">代码</th>
            <th className="px-3 py-2 font-medium">类型</th>
            <th className="px-3 py-2 text-right font-medium">近一年收益</th>
            <th className="px-3 py-2 text-right font-medium">风险等级</th>
          </tr>
        </thead>
        <tbody>
          {funds.map((fund, index) => (
            <tr
              key={fund.code}
              className="border-b border-border last:border-0 transition-colors hover:bg-muted/40"
            >
              <td className="px-3 py-2.5">
                <span
                  className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold ${
                    index < 3 ? "bg-foreground text-background" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {index + 1}
                </span>
              </td>
              <td className="px-3 py-2.5">
                <Link href={`/fund/${fund.code}`} className="font-medium hover:text-accent">
                  {fund.name}
                </Link>
              </td>
              <td className="px-3 py-2.5 text-muted-foreground">{fund.code}</td>
              <td className="px-3 py-2.5 text-muted-foreground">{fund.type}</td>
              <td
                className={`px-3 py-2.5 text-right font-medium tabular-nums ${
                  fund.oneYearReturn >= 0 ? "text-positive" : "text-negative"
                }`}
              >
                {formatPercent(fund.oneYearReturn)}
              </td>
              <td className="px-3 py-2.5 text-right">
                <Badge variant="outline">{fund.riskLevel}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
