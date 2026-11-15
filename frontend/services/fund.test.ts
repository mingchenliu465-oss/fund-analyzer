import { describe, expect, it } from "vitest";

import {
  formatCurrency,
  formatPercent,
  formatPercentValue,
  HoldingItem,
  transformPortfolioToOverview,
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

describe("formatCurrency", () => {
  it("带千分位与两位小数", () => {
    expect(formatCurrency(1234.5)).toBe("¥1,234.50");
    expect(formatCurrency(0)).toBe("¥0.00");
  });
});

function holding(id: number, currentValue: number | null): HoldingItem {
  return {
    id,
    fund_code: `00000${id}`,
    fund_name: "测试基金",
    fund_type: "股票型",
    buy_date: "2026-01-01",
    buy_amount: 100,
    buy_nav: 1,
    shares: 100,
    fee: 0,
    notes: "",
    is_sold: false,
    sell_date: null,
    sell_amount: null,
    sell_nav: null,
    current_nav: 1,
    current_value: currentValue,
    cost: 100,
    profit: null,
    profit_pct: null,
  };
}

describe("组合配置不得把缺失估值当 0", () => {
  it("任一持仓市值缺失时不生成误导性的配置比例", () => {
    const result = transformPortfolioToOverview({
      total_cost: 200,
      total_value: 100,
      total_profit: null,
      total_profit_pct: null,
      holding_count: 2,
      holdings: [holding(1, 100), holding(2, null)],
      has_stale_nav: true,
    });
    expect(result.allocation).toEqual([]);
  });

  it("估值完整时仍按真实市值计算配置", () => {
    const result = transformPortfolioToOverview({
      total_cost: 200,
      total_value: 100,
      total_profit: 0,
      total_profit_pct: 0,
      holding_count: 2,
      holdings: [holding(1, 60), holding(2, 40)],
      has_stale_nav: false,
    });
    expect(result.allocation.map((item) => item.weight)).toEqual([100]);
  });
});
