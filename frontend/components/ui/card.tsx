import * as React from "react";

/**
 * 全站统一的卡片容器。各页面的「圆角 + 边框 + 背景」面板一律用 Card，
 * 不再各自手写 rounded-2xl border border-border bg-background。
 */
export function Card({
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-card border border-border bg-background ${className}`}
      {...props}
    />
  );
}

/**
 * 卡片头部：标题 + 一句话说明 + 右侧操作区，全站统一结构。
 */
export function CardHeader({
  title,
  description,
  action,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
