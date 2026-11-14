"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { BookOpen } from "lucide-react";

/**
 * 全站统一的页面头部。
 *
 * 页面结构约定（风格统一改造后各页一致）：
 *   标题与一句话说明 → 阅读指引 → 白话结论 → 数据主体 → 披露
 *
 * PageHeader 负责第一段（标题 + 说明 + 阅读指引），右侧可放操作区
 * （周期切换等）。guide 只写「怎么看这个页面」的说明文字，不编造数据。
 */
export function PageHeader({
  title,
  description,
  guide,
  action,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** 阅读指引：2-4 条「怎么看本页」的说明文字 */
  guide?: string[];
  action?: React.ReactNode;
}) {
  return (
    <section className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
          className="text-2xl font-semibold tracking-tight sm:text-3xl"
        >
          {title}
        </motion.h1>
        {description && (
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05, ease: [0.23, 1, 0.32, 1] }}
            className="mt-2 text-muted-foreground"
          >
            {description}
          </motion.p>
        )}
        {guide && guide.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08, ease: [0.23, 1, 0.32, 1] }}
            className="mt-3 max-w-2xl rounded-control border border-border bg-muted/40 p-3"
          >
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5" />
              阅读指引
            </div>
            <ul className="mt-1.5 space-y-0.5 text-xs leading-relaxed text-muted-foreground">
              {guide.map((line) => (
                <li key={line}>· {line}</li>
              ))}
            </ul>
          </motion.div>
        )}
      </div>
      {action}
    </section>
  );
}
