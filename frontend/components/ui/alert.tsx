import * as React from "react";

/**
 * 全站统一的提示条（Alert）。
 *
 * 语义是「状态/质量」，不是行情涨跌，因此配色走
 * positive（绿=好）/ negative（红=坏）/ warning（黄=注意），
 * 与涨跌用的 rise/fall 是两套语义，不要混用。
 */

export type AlertVariant = "info" | "success" | "warning" | "error";

const VARIANT_CLASSES: Record<AlertVariant, string> = {
  info: "border-accent/30 bg-accent/5 text-foreground",
  success: "border-positive/30 bg-positive/10 text-positive",
  warning: "border-warning/30 bg-warning/10 text-warning",
  error: "border-negative/30 bg-negative/10 text-negative",
};

export function Alert({
  variant = "info",
  className = "",
  action,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  variant?: AlertVariant;
  action?: React.ReactNode;
}) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={`flex items-center justify-between gap-3 rounded-card border px-4 py-3 text-sm ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    >
      <span>{children}</span>
      {action}
    </div>
  );
}
