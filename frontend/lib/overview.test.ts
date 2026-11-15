import { describe, expect, it } from "vitest";
import type { FundOverview } from "../services/fund";
import { excessReturn, isCurrentOverview, overviewConclusion } from "./overview";

const base: FundOverview = {
  code: "161725",
  name: "测试基金",
  period: "1y",
  dataStart: "2025-01-01",
  dataEnd: "2026-01-01",
  sampleCount: 3,
  metricStatus: "available",
  metrics: { periodReturn: 0.12, volatility: 0.2, maxDrawdown: -0.08, sharpe: 0.6 },
  curve: [],
  benchmark: {
    code: "sh000300",
    name: "沪深300",
    status: "available",
    source: "测试来源",
    periodReturn: 0.04,
    matchedSamples: 3,
    fundOnlyDates: 0,
    benchmarkOnlyDates: 0,
    note: "参考基准",
  },
  qualityStatus: "normal",
  qualityNotes: [],
  duplicateDates: 0,
  invalidNavRecords: 0,
  source: "测试来源",
  generatedAt: "2026-01-01T00:00:00+08:00",
};

describe("Overview 响应身份", () => {
  it("基金或区间不匹配的晚到响应不得用于当前页面", () => {
    expect(isCurrentOverview(base, "161725", "1y")).toBe(true);
    expect(isCurrentOverview(base, "510300", "1y")).toBe(false);
    expect(isCurrentOverview(base, "161725", "3m")).toBe(false);
    expect(isCurrentOverview(undefined, "161725", "1y")).toBe(false);
  });
});

describe("Overview 结论", () => {
  it("超额收益是收益差，而不是百分比相除", () => {
    expect(excessReturn(base)).toBeCloseTo(0.08);
    expect(overviewConclusion(base)).toContain("超额收益为 8.00%");
  });

  it("基准缺失时不伪造 0% 超额", () => {
    const missing = {
      ...base,
      benchmark: { ...base.benchmark, periodReturn: null, status: "unavailable" },
    } as FundOverview;
    expect(excessReturn(missing)).toBeNull();
    expect(overviewConclusion(missing)).toContain("未计算超额收益");
    expect(overviewConclusion(missing)).not.toContain("超额收益为 0.00%");
  });

  it("样本不足时不下收益或风险结论", () => {
    const insufficient = {
      ...base,
      metrics: { periodReturn: null, volatility: null, maxDrawdown: null, sharpe: null },
    } as FundOverview;
    expect(overviewConclusion(insufficient)).toContain("没有足够的真实累计净值");
  });
});
