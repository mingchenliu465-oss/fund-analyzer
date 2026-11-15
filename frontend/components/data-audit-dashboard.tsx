"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ResearchControls } from "@/components/research-controls";
import { Button } from "@/components/ui/button";
import {
  DataState,
  KeyValueList,
  MetricStrip,
  PageHeader,
  PlainConclusion,
  ResearchSection,
  SourceNote,
} from "@/components/research-ui";
import { useResearchSelection } from "@/hooks/use-research-selection";
import { AuditStatus, formatPercent, getFundDataAudit } from "@/services/fund";

const STATUS_LABELS: Record<AuditStatus, string> = {
  normal: "正常",
  warning: "警告",
  abnormal: "异常",
  missing: "缺失",
  unverified: "未验证",
};

const OVERALL_STATE = {
  normal: { kind: "success" as const, title: "当前检查未发现异常" },
  warning: { kind: "partial" as const, title: "数据可用，但存在需要复核的项目" },
  abnormal: { kind: "error" as const, title: "发现影响数据可信度的异常" },
  missing: { kind: "missing" as const, title: "关键审计数据缺失" },
  unverified: { kind: "unsupported" as const, title: "基础检查完成，仍有项目未验证" },
};

export default function DataAuditDashboard() {
  const { code, period, ready, setCode, setPeriod } = useResearchSelection();
  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["fundDataAudit", code, period],
    queryFn: () => getFundDataAudit(code, period),
    enabled: ready,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const current = data?.code === code && data.period === period ? data : undefined;
  const loading = !ready || isPending || (isFetching && !current);

  return (
    <div className="page-container">
      <PageHeader
        title="数据审计"
        description="回答数据能否使用、为什么、问题在哪里。检查来源、连续性、净值一致性与验证边界。"
        action={<Link className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-accent" href="/">返回研究概览 <ArrowRight size={15} /></Link>}
      />
      <ResearchControls code={code} period={period} onCodeChange={setCode} onPeriodChange={setPeriod} />

      {loading && <DataState kind="loading" title={`正在审计 ${code} 的原始净值记录`} description="审计读取原始单位净值与累计净值，指标计算仍只使用累计净值。" />}
      {!loading && isError && <DataState kind="error" title="审计数据暂时不可用" description={error instanceof Error ? error.message : "请稍后重试。"} action={<Button variant="outline" onClick={() => void refetch()}>重新加载</Button>} />}
      {!loading && !isError && !current && <DataState kind="error" title="响应与当前研究对象不一致" description="已丢弃基金或区间不匹配的响应。" />}

      {current && !loading && (
        <>
          <PlainConclusion note="“正常”只表示当前规则未发现问题；“未验证”不会被包装成“正常”。">
            {current.overallStatus === "abnormal" || current.overallStatus === "missing"
              ? "当前数据存在异常或关键缺失，请先查看检查项，再决定是否用于研究。"
              : current.overallStatus === "warning"
                ? "当前数据可用于谨慎研究，但存在警告项；请结合下方证据理解指标。"
                : "基础质量检查已完成；跨数据源和权益事件尚未独立验证，因此不宣称数据已被完全核验。"}
          </PlainConclusion>
          <MetricStrip items={[
            { label: "综合状态", value: STATUS_LABELS[current.overallStatus], note: "按最严重检查项汇总", tone: current.overallStatus === "normal" ? "up" : "warning" },
            { label: "区间记录", value: current.recordCount, note: "原始有效日期记录", tone: "neutral" },
            { label: "交易日覆盖率", value: formatPercent(current.coverageRatio).replace(/^\+/, ""), note: "仅覆盖交易日历", tone: "risk" },
            { label: "缺失日期样本", value: current.missingDates.length, note: "最多披露 20 项", tone: current.missingDates.length ? "warning" : "neutral" },
          ]} />

          <ResearchSection title="质量检查清单" description="每个项目独立呈现状态，不用一个总分掩盖具体问题。">
            <DataState {...OVERALL_STATE[current.overallStatus]} />
            <div className="research-table-wrap"><table className="data-table audit-table">
              <thead><tr><th>检查项</th><th>状态</th><th>证据与解释</th></tr></thead>
              <tbody>{current.checks.map((check) => <tr key={check.key}><td>{check.label}</td><td><span className={`audit-status status-${check.status}`}>{STATUS_LABELS[check.status]}</span></td><td>{check.detail}</td></tr>)}</tbody>
            </table></div>
          </ResearchSection>

          <div className="overview-evidence-grid">
            <ResearchSection title="来源与覆盖">
              <KeyValueList items={[
                { label: "数据来源", value: current.source },
                { label: "实际覆盖", value: `${current.dataStart ?? "—"} 至 ${current.dataEnd ?? "—"}` },
                { label: "响应生成时间", value: new Date(current.generatedAt).toLocaleString("zh-CN") },
                { label: "基金 / 区间", value: `${current.code} / ${current.period}` },
              ]} />
            </ResearchSection>
            <ResearchSection title="交易日缺口" description="缺口是复核线索，不自动等同于数据错误。">
              {current.missingDates.length ? <div className="date-chip-list">{current.missingDates.map((day) => <span key={day}>{day}</span>)}</div> : <DataState kind="success" title="未发现交易日历内缺口" />}
            </ResearchSection>
          </div>

          <ResearchSection title="极端累计净值变动" description="单日绝对变动达到 10% 时列出；可能是真实市场波动，也可能需要复核权益事件。">
            {current.extremeMoves.length ? <div className="research-table-wrap"><table className="data-table"><thead><tr><th>日期</th><th className="numeric">累计净值变动</th><th>说明</th></tr></thead><tbody>{current.extremeMoves.map((item) => <tr key={item.date}><td>{item.date}</td><td className="numeric">{formatPercent(item.return)}</td><td>{item.note}</td></tr>)}</tbody></table></div> : <DataState kind="success" title="未触发极端变动阈值" description="这不等于已完成公告或权益事件核验。" />}
          </ResearchSection>

          <ResearchSection title="单位净值与累计净值差异" description="每日净值变动差异达到 0.005 个净值单位时列为候选事件；没有官方事件源时一律标记未验证。">
            {current.distributionCandidates.length ? <div className="research-table-wrap"><table className="data-table"><thead><tr><th>日期</th><th className="numeric">单位净值变动</th><th className="numeric">累计净值变动</th><th className="numeric">变动差异</th><th>状态</th></tr></thead><tbody>{current.distributionCandidates.map((item) => <tr key={item.date}><td>{item.date}</td><td className="numeric">{item.unitChange.toFixed(4)}</td><td className="numeric">{item.cumulativeChange.toFixed(4)}</td><td className="numeric">{item.difference.toFixed(4)}</td><td><span className="audit-status status-unverified">可能分红/复权 · 未验证</span></td></tr>)}</tbody></table></div> : <DataState kind="success" title="未发现超过阈值的净值变动差异" description="未发现差异不代表基金从未分红或拆分。" />}
          </ResearchSection>

          <ResearchSection title="审计边界"><ul className="quality-note-list">{current.notes.map((note) => <li key={note}>{note}</li>)}</ul><SourceNote>本页不会用 ETF 二级市场成交价替代基金累计净值，也不会将缺失值静默改成 0。</SourceNote></ResearchSection>
        </>
      )}
    </div>
  );
}
