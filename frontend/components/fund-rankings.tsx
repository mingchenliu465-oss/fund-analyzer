import Link from "next/link";
import { FundSummary, formatPercent } from "@/services/fund";
import { DataState } from "./research-ui";

export function FundRankings({ funds }: { funds: FundSummary[] }) {
  if (funds.length === 0) {
    return <DataState kind="empty" title="暂无排行数据" description="数据源暂时不可用，未使用替代数据。" />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>排名</th>
            <th>基金名称</th>
            <th className="hidden sm:table-cell">代码</th>
            <th className="hidden md:table-cell">类型</th>
            <th className="numeric">近一年收益</th>
            <th className="numeric hidden sm:table-cell">风险等级</th>
          </tr>
        </thead>
        <tbody>
          {funds.map((fund, index) => {
            const ret = fund.oneYearReturn;
            return (
              <tr key={fund.code || `fund-${index}`}>
                <td className="numeric text-muted-foreground">{index + 1}</td>
                <td>
                  <Link href={`/fund/${fund.code}`} className="font-medium hover:text-accent">
                    {fund.name ?? "—"}
                  </Link>
                  <span className="mt-0.5 block text-xs text-muted-foreground sm:hidden">{fund.code}</span>
                </td>
                <td className="hidden text-muted-foreground sm:table-cell">{fund.code}</td>
                <td className="hidden text-muted-foreground md:table-cell">{fund.type ?? "—"}</td>
                <td className={`numeric font-semibold ${ret == null ? "text-muted-foreground" : ret >= 0 ? "text-positive" : "text-negative"}`}>
                  {formatPercent(ret)}
                </td>
                <td className="numeric hidden sm:table-cell">{fund.riskLevel ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
