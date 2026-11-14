"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import { formatPercent } from "@/services/fund";

/**
 * 行情涨跌幅的统一展示组件。
 *
 * - 配色遵循 A 股约定：红涨（text-rise）绿跌（text-fall），与 K 线图一致。
 * - 后端涨跌幅字段本身是「百分数」，统一乘 0.01 后交给 formatPercent
 *   （比率 → 两位小数百分比），不要各处重复换算。
 * - 缺失（null / 非有限值）显示「—」，绝不伪装成 "+0.00%"。
 */
export function SignedChange({
  value,
  className = "",
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value == null || !Number.isFinite(value)) {
    return <span className={`text-muted-foreground ${className}`}>—</span>;
  }

  const up = value >= 0;
  return (
    <span
      className={`inline-flex items-center gap-1 font-medium tabular-nums ${
        up ? "text-rise" : "text-fall"
      } ${className}`}
    >
      {up ? (
        <TrendingUp className="h-3 w-3" />
      ) : (
        <TrendingDown className="h-3 w-3" />
      )}
      {formatPercent(value * 0.01)}
    </span>
  );
}
