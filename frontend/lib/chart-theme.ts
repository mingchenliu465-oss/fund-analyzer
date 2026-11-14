/**
 * 全站图表配色的 JS 侧唯一来源。
 *
 * CSS 变量（app/globals.css 的 --chart-* / --rise / --fall）无法在
 * JS 图表库（lightweight-charts、recharts 的 SVG 属性）中直接读取，
 * 因此在此集中定义常量；两处取值必须保持一致。
 *
 * 语义约定：
 * - 行情涨跌用 CHART_RISE（红）/ CHART_FALL（绿），A 股约定，与
 *   services/fund.ts 的 KLINE_UP_COLOR / KLINE_DOWN_COLOR 同源同值。
 * - CHART_SERIES 是多序列图表（对比走势、持有人结构等）的分类配色，
 *   按序循环取用，不代表涨跌语义。
 */

// A 股配色约定：红涨绿跌（与 KLINE_UP_COLOR / KLINE_DOWN_COLOR 保持一致）
export const CHART_RISE = "#ff3b30";
export const CHART_FALL = "#00a550";

// 主色：净值线、资产曲线、K 线副图等单一主序列
export const CHART_PRIMARY = "#0071e3";

// 分类序列配色（多序列图表按序取用）
export const CHART_SERIES = [
  "#0071e3",
  "#5856d6",
  "#af52de",
  "#ff9500",
  "#00a550",
  "#ff3b30",
];

// 均线配色（K 线图 MA5 / MA10 / MA20）
export const MA_COLORS = {
  ma5: "#ff9500",
  ma10: "#ffcc00",
  ma20: "#af52de",
};

// 图表骨架中性色（网格、坐标轴文字）：不随涨跌语义变化
export const CHART_GRID = "#e5e7eb";
export const CHART_AXIS_TEXT = "#9ca3af";

// 图表中「当前选中项 / 目标项」的强调填充色（同类对比柱状图的目标基金等）
export const CHART_TARGET = "#171717";

/**
 * recharts Tooltip 的统一外观。所有图表的悬浮提示都用这一份，
 * 不再各自硬编码 contentStyle。
 */
export const RECHARTS_TOOLTIP_STYLE = {
  background: "var(--background)",
  border: "1px solid var(--border)",
  borderRadius: "12px",
  boxShadow: "0 8px 30px rgba(0,0,0,0.08)",
} as const;

// recharts 坐标轴刻度的统一文字样式
export const RECHARTS_TICK_PROPS = {
  fill: "var(--muted-foreground)",
  fontSize: 11,
} as const;
