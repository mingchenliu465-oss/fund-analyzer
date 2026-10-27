import { describe, expect, it } from "vitest";

import {
  countConclusions,
  formatCurrency,
  formatPercent,
  formatPercentValue,
  plainHistoryFrequencySummary,
} from "./fund";

// 两种百分比语义必须分清（这是"首页累计收益率被放大 100 倍"的根因）：
// - formatPercent      接收小数比率：0.9802 -> +98.02%
// - formatPercentValue 接收百分数：  98.02  -> +98.02%（后端所有 *_pct 字段）
describe("formatPercent / formatPercentValue 语义不得混用", () => {
  it("同一个涨幅用对函数时结果一致", () => {
    expect(formatPercent(0.9802)).toBe("+98.02%");
    expect(formatPercentValue(98.02)).toBe("+98.02%");
    expect(formatPercent(0.9802)).toBe(formatPercentValue(98.02));
  });

  it("负数不加正号", () => {
    expect(formatPercent(-0.05)).toBe("-5.00%");
    expect(formatPercentValue(-5)).toBe("-5.00%");
  });

  it("零就是 0.00%，不带符号", () => {
    expect(formatPercent(0)).toBe("0.00%");
    expect(formatPercentValue(0)).toBe("0.00%");
  });
});

describe("缺失值必须显示为 —，不得伪装成 0", () => {
  it("null / undefined / NaN 都返回 —", () => {
    for (const missing of [null, undefined, Number.NaN]) {
      expect(formatPercent(missing)).toBe("—");
      expect(formatPercentValue(missing)).toBe("—");
      expect(formatCurrency(missing)).toBe("—");
    }
  });
});

describe("countConclusions（回测总览的结论分布）", () => {
  it("按结论原文计数，不合并、不改名", () => {
    const combos = [
      { conclusion: "不成立" },
      { conclusion: "不成立" },
      { conclusion: "证据不足" },
      { conclusion: "成立" },
      { conclusion: "不成立" },
      { conclusion: "证据不足" },
    ];
    expect(countConclusions(combos)).toEqual({ 不成立: 3, 证据不足: 2, 成立: 1 });
  });

  it("空组合返回空对象", () => {
    expect(countConclusions([])).toEqual({});
  });
});

describe("formatCurrency", () => {
  it("带千分位与两位小数", () => {
    expect(formatCurrency(1234.5)).toBe("¥1,234.50");
    expect(formatCurrency(0)).toBe("¥0.00");
  });
});

describe("plainHistoryFrequencySummary 只复述数字，不加对未来的判断", () => {
  const base = {
    code: "161725",
    name: "测试基金",
    status: "ok" as const,
    refusal_reason: null,
    evidence: "足" as const,
    evidence_reason: null,
    data_start: "2015-05-27",
    data_end: "2026-11-06",
    dropped_rows: 0,
    origins_6m: 2656,
    origins_12m: 2530,
    non_overlapping_blocks_12m: 11,
    positive_6m: { freq: 0.5184, count: 1377, n: 2656 },
    positive_12m: { freq: 0.5569, count: 1409, n: 2530 },
    drawdown_exceed_12m: {
      "5": { freq: 0.9579, count: 2423, n: 2530 },
      "10": { freq: 0.7645, count: 1934, n: 2530 },
      "15": { freq: 0.3139, count: 794, n: 2530 },
    },
    payback_5pct: {
      origins: 2785,
      events: 2036,
      recovered: 1275,
      unrecovered: 761,
      unrecovered_share: 0.3738,
      median_days: 108,
      p75_days: 169,
      p90_days: 290,
      evidence: "足" as const,
    },
    yearly: [],
    disclosures: [],
  };

  it("正常报告复述三个核心数字", () => {
    const text = plainHistoryFrequencySummary(base);
    expect(text).toContain("55.7%");
    expect(text).toContain("1409/2530");
    expect(text).toContain("76.4%");
    expect(text).toContain("37.4%");
    expect(text).not.toContain("证据不足");
  });

  it("先解释起点是什么，两个比例同批时明说同一批", () => {
    const text = plainHistoryFrequencySummary(base);
    expect(text).toContain("就在那天买入");
    expect(text).toContain("同一批起点");
  });

  it("证据不足时追加降级句", () => {
    const text = plainHistoryFrequencySummary({ ...base, evidence: "不足" as const });
    expect(text).toContain("只能写证据不足");
  });

  it("拒绝出结论时原样返回拒绝原因", () => {
    const text = plainHistoryFrequencySummary({
      ...base,
      status: "refused" as const,
      refusal_reason: "可用历史仅约 1.5 年，不足 3 年，按数据纪律拒绝出结论",
    });
    expect(text).toContain("不足 3 年");
  });
});
