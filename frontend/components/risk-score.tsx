"use client";

import { motion } from "framer-motion";

interface RiskScoreProps {
  /** 后端不再输出综合风险评分（无可复现定义），因此允许为 null。 */
  score: number | null;
  label: string | null;
  size?: number;
  stroke?: number;
}

export function RiskScore({ score, label, size = 160, stroke = 12 }: RiskScoreProps) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  // 没有评分就不画刻度环：绝不把 null 当成 0（那会显示成"风险最低"）。
  if (score == null) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-full border border-dashed border-border text-center"
        style={{ width: size, height: size }}
      >
        <span className="text-sm font-medium text-muted-foreground">暂无</span>
        <span className="mt-1 px-2 text-[11px] leading-tight text-muted-foreground">
          无可复现的综合风险评分
        </span>
      </div>
    );
  }

  const offset = circumference - (score / 100) * circumference;

  const color =
    score < 25
      ? "text-positive"
      : score < 50
      ? "text-warning"
      : score < 75
      ? "text-accent"
      : "text-negative";

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            className="text-muted/60"
            stroke="currentColor"
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            className={color}
            stroke="currentColor"
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1, ease: [0.23, 1, 0.32, 1] }}
            style={{ strokeDasharray: circumference }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold tracking-tight">{score}</span>
          <span className="text-xs text-muted-foreground">{label ?? "—"}</span>
        </div>
      </div>
    </div>
  );
}
