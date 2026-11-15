"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DataState, PageHeader, ResearchSection, SourceNote } from "@/components/research-ui";
import {
  DEFAULT_RESEARCH_PREFERENCES,
  RESEARCH_PERIODS,
  ResearchPeriod,
  readResearchPreferences,
  writeResearchPreferences,
} from "@/lib/research-preferences";

const periodLabels: Record<ResearchPeriod, string> = {
  "1m": "近一个月",
  "3m": "近三个月",
  "6m": "近六个月",
  "1y": "近一年",
  "3y": "近三年",
  all: "成立以来",
};

export default function SettingsPage() {
  const [defaultCode, setDefaultCode] = useState(DEFAULT_RESEARCH_PREFERENCES.defaultCode);
  const [defaultPeriod, setDefaultPeriod] = useState<ResearchPeriod>(DEFAULT_RESEARCH_PREFERENCES.defaultPeriod);
  const [ready, setReady] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const preferences = readResearchPreferences();
      setDefaultCode(preferences.defaultCode);
      setDefaultPeriod(preferences.defaultPeriod);
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^\d{6}$/.test(defaultCode)) return;
    writeResearchPreferences({ defaultCode, defaultPeriod });
    setSaved(true);
  }

  return (
    <div className="page-container">
      <PageHeader title="偏好设置" description="设置研究概览的默认基金和统计区间。偏好仅保存在当前浏览器，不上传服务器。" />
      {!ready ? (
        <DataState kind="loading" title="正在读取本地偏好" />
      ) : (
        <ResearchSection title="研究默认值" description="默认基金只是初始研究对象，不构成推荐；进入页面后仍可切换。">
          <form onSubmit={save} className="max-w-xl space-y-5">
            <label className="block text-sm font-medium" htmlFor="default-fund-code">
              默认基金代码
              <Input
                id="default-fund-code"
                value={defaultCode}
                onChange={(event) => { setDefaultCode(event.target.value.trim()); setSaved(false); }}
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                className="mt-2"
                aria-describedby="default-fund-code-note"
              />
              <span id="default-fund-code-note" className="mt-1 block text-xs font-normal text-muted-foreground">请输入六位基金代码，例如 161725。</span>
            </label>
            <label className="block text-sm font-medium" htmlFor="default-research-period">
              默认统计区间
              <select
                id="default-research-period"
                value={defaultPeriod}
                onChange={(event) => { setDefaultPeriod(event.target.value as ResearchPeriod); setSaved(false); }}
                className="mt-2 h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground"
              >
                {RESEARCH_PERIODS.map((period) => <option key={period} value={period}>{periodLabels[period]}</option>)}
              </select>
            </label>
            <div className="flex items-center gap-4">
              <Button type="submit" disabled={!/^\d{6}$/.test(defaultCode)}>保存偏好</Button>
              {saved && <span role="status" className="text-sm text-muted-foreground">已保存在当前浏览器。</span>}
            </div>
          </form>
          <SourceNote>清除浏览器站点数据会移除这些偏好。颜色遵循中国市场红涨绿跌，不提供可能混淆风险语义的自定义涨跌色。</SourceNote>
        </ResearchSection>
      )}
    </div>
  );
}
