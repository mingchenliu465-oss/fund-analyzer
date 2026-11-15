/** JavaScript chart constants mirrored by the CSS custom properties in globals.css. */
export const CHART_RISE = "#d84a4a";
export const CHART_FALL = "#16a36a";
export const CHART_PRIMARY = "#315eaa";
export const CHART_BENCHMARK = "#8993a2";
export const CHART_STRATEGY = "#7a5c9e";
export const CHART_DRAWDOWN = "#16a36a";
export const CHART_GRID = "#edf0f4";
export const CHART_AXIS_TEXT = "#697586";

export const CHART_SERIES = [
  CHART_PRIMARY,
  CHART_STRATEGY,
  CHART_BENCHMARK,
  CHART_RISE,
  CHART_FALL,
] as const;

export const MA_COLORS = {
  ma5: CHART_PRIMARY,
  ma10: CHART_BENCHMARK,
  ma20: CHART_STRATEGY,
} as const;

export const RECHARTS_TOOLTIP_STYLE = {
  background: "var(--chart-tooltip)",
  border: "1px solid var(--border)",
  borderRadius: "6px",
  boxShadow: "none",
} as const;

export const RECHARTS_TICK_PROPS = {
  fill: "var(--muted-foreground)",
  fontSize: 11,
} as const;
