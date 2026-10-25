import { describe, expect, it } from "vitest";

import { formatCurrency, formatPercent, formatPercentValue } from "./fund";

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

describe("formatCurrency", () => {
  it("带千分位与两位小数", () => {
    expect(formatCurrency(1234.5)).toBe("¥1,234.50");
    expect(formatCurrency(0)).toBe("¥0.00");
  });
});
