"use client";

import * as React from "react";

/**
 * 全站统一的分段选择器（Segmented Control）。
 *
 * 用于：K 线周期 / 时间范围 / 历史区间 / 视图切换 / 单笔定投切换等。
 * 各页面不再各自手写「圆角容器 + 选中按钮」的重复实现。
 */

export interface SegmentedOption<T extends string> {
  value: T;
  label: React.ReactNode;
  disabled?: boolean;
}

interface SegmentedControlProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: SegmentedOption<T>[];
  size?: "sm" | "md";
  className?: string;
  ariaLabel?: string;
}

export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  size = "sm",
  className = "",
  ariaLabel,
}: SegmentedControlProps<T>) {
  const sizeClasses =
    size === "md"
      ? "px-3 py-1.5 text-sm"
      : "px-3 py-1 text-xs";

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`flex gap-1 rounded-control border border-border bg-muted/40 p-1 ${className}`}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          disabled={option.disabled}
          onClick={() => onChange(option.value)}
          className={`rounded-lg font-medium transition-colors ${sizeClasses} ${
            value === option.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
