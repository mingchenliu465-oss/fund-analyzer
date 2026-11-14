"use client";

import { formatPercent } from "@/services/fund";

/**
 * 小型信息块（MetaItem）：标签 + 文本值。
 * 基金详情页 / 指数详情页的「基金规模、成立时间、发布方」等元信息统一用它。
 */
export function StatItem({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={`rounded-control border border-border bg-background p-3 ${className}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm font-medium">{value}</div>
    </div>
  );
}

/**
 * 区间收益小卡片（日 / 周 / 月收益）。
 * 收益为「比率」语义（后端返回小数），两位小数百分比；缺失显示「—」。
 * 配色遵循 A 股约定：红涨绿跌。
 */
export function ReturnStat({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  return (
    <div className="rounded-card border border-border bg-background p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`mt-1 text-xl font-semibold tabular-nums ${
          value == null
            ? "text-muted-foreground"
            : value >= 0
              ? "text-rise"
              : "text-fall"
        }`}
      >
        {/* 历史不足时后端返回 null：绝不能只写 >= 0 —— null >= 0 为 true，
            会把「算不出来」渲染成红彤彤的 "+0.00%"。 */}
        {formatPercent(value)}
      </div>
    </div>
  );
}
