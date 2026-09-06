"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  IChartApi,
  ISeriesApi,
  CandlestickSeriesPartialOptions,
  Time,
  SeriesType,
} from "lightweight-charts";
import { KlinePoint, KLINE_UP_COLOR, KLINE_DOWN_COLOR } from "@/services/fund";

// ═══════════════════════════════════════════════════════════════════════════════
// Props
// ═══════════════════════════════════════════════════════════════════════════════

interface KLineChartProps {
  data: KlinePoint[];
  fundType?: string; // "ETF"/"指数" → 蜡烛图+成交量; 其他 → 净值折线+均线
  chartMode?: "candlestick" | "line";
  code?: string; // 基金代码，用于按代码前缀兜底判断是否场内 ETF
  period?: string; // 当前聚合周期（日K/周K/月K），用于计算初始可见窗口
  chartRange?: string; // 时间范围（1M/3M/6M/1Y/3Y），控制初始可见窗口
}

// 场内 ETF 代码前缀（与后端 fund_service._is_etf_code 保持一致，唯一真源）
function isEtfCode(code: string | undefined): boolean {
  if (!code) return false;
  const c = code.trim();
  if (c.length !== 6) return false;
  return /^(51|56|58|15|16)/.test(c);
}

// 初始可见窗口条数：周期 × 时间范围 → 需显示的 bar 数（近似交易日）
function visibleBarsFor(period: string | undefined, range: string | undefined): number {
  const map: Record<string, Record<string, number>> = {
    日K: { "1M": 22, "3M": 66, "6M": 130, "1Y": 250, "3Y": 750 },
    周K: { "1M": 5, "3M": 13, "6M": 26, "1Y": 52, "3Y": 156 },
    月K: { "1M": 1, "3M": 3, "6M": 6, "1Y": 12, "3Y": 36 },
  };
  const per = map[period ?? "日K"] ?? map["日K"];
  return per[range ?? "1Y"] ?? 250;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════════

const CANDLESTICK_OPTIONS: CandlestickSeriesPartialOptions = {
  upColor: KLINE_UP_COLOR,
  downColor: KLINE_DOWN_COLOR,
  borderUpColor: KLINE_UP_COLOR,
  borderDownColor: KLINE_DOWN_COLOR,
  wickUpColor: KLINE_UP_COLOR,
  wickDownColor: KLINE_DOWN_COLOR,
};

const MA_COLORS = {
  ma5: "#ff9500",
  ma10: "#ffcc00",
  ma20: "#af52de",
};

// ═══════════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════════

function normalizeDate(dateStr: string, fallbackYear: number): string {
  const trimmed = dateStr.trim();
  if (!trimmed) return "";
  // yyyy-MM-dd
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    const [, m, d] = trimmed.split("-").map(Number);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return trimmed;
    return "";
  }
  // yyyy-MM → yyyy-MM-01
  if (/^\d{4}-\d{2}$/.test(trimmed)) {
    const [, m] = trimmed.split("-").map(Number);
    if (m >= 1 && m <= 12) return `${trimmed}-01`;
    return "";
  }
  // MM-dd → yyyy-MM-dd
  if (/^\d{2}-\d{2}$/.test(trimmed)) {
    const [m, d] = trimmed.split("-").map(Number);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return `${fallbackYear}-${trimmed}`;
    return "";
  }
  return "";
}

function computeMA(values: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += values[j];
      result.push(sum / period);
    }
  }
  return result;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════════

export function KLineChart({ data, fundType, chartMode, code, period, chartRange }: KLineChartProps) {
  // 统一以代码前缀判断是否场内 ETF（不依赖 type 字段，数据源可能误标）。
  // 同时兼容显式 type="ETF"（如默认快照里已标 ETF 的基金）。
  const isETF = chartMode
    ? chartMode === "candlestick"
    : isEtfCode(code) || fundType === "ETF" || fundType === "指数";
  const lineLabel = fundType?.includes("指数") ? "指数" : "净值";
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // Track all series so we can remove them before adding new ones
  const seriesRefs = useRef<ISeriesApi<SeriesType>[]>([]);
  // 当前已加载的数据条数，供 range 变化时设置可视窗口（不重建 series）
  const dataLengthRef = useRef(0);

  const applyVisibleRange = useCallback(
    (chart: IChartApi) => {
      const n = dataLengthRef.current;
      if (n === 0) return;
      const bars = visibleBarsFor(period, chartRange);
      chart.timeScale().setVisibleLogicalRange({
        from: Math.max(0, n - bars),
        to: n + 0.5,
      });
    },
    [period, chartRange]
  );

  // ── Init chart (recreated when fundType changes) ──────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#e5e7eb", style: 3 },
        horzLines: { color: "#e5e7eb", style: 3 },
      },
      crosshair: { mode: 0 },
      timeScale: {
        borderColor: "#e5e7eb",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#e5e7eb",
        autoScale: true,
      },
      localization: { locale: "zh-CN" },
    });

    chartRef.current = chart;
    seriesRefs.current = [];

    // Resize observer
    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    };
    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRefs.current = [];
    };
  }, []); // Chart config is identical for ETF/non-ETF; series swap handled by data effect

  // ── Update data ───────────────────────────────────────────────────────
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !data || data.length === 0) return;

    // Remove all existing series before adding new ones
    for (const s of seriesRefs.current) {
      try { chart.removeSeries(s); } catch (e) { if (process.env.NODE_ENV === "development") console.warn("removeSeries failed:", e); }
    }
    seriesRefs.current = [];

    const currentYear = new Date().getFullYear();

    // Normalize + validate OHLC data
    const raw: { time: Time; open: number; high: number; low: number; close: number; _epoch: number; _volume: number }[] = [];
    for (const point of data) {
      const date = normalizeDate(point.date, currentYear);
      if (!date) continue;
      const epoch = new Date(date + "T00:00:00").getTime();
      if (Number.isNaN(epoch)) continue;
      raw.push({
        time: date as Time,
        open: point.open,
        high: point.high,
        low: point.low,
        close: point.close,
        _epoch: epoch,
        _volume: point.volume ?? 0,
      });
    }

    if (raw.length === 0) return;

    // Sort asc, dedup
    raw.sort((a, b) => a._epoch - b._epoch);
    const seen = new Set<string>();
    const deduped = raw.filter((item) => {
      const key = item.time as string;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    const closes = deduped.map((d) => d.close);
    const ma5 = computeMA(closes, 5);
    const ma10 = computeMA(closes, 10);
    const ma20 = computeMA(closes, 20);

    if (isETF) {
      // ── ETF 模式：真实 K 线 + 成交量 ──
      const candles = deduped.map(({ time, open, high, low, close }) => ({
        time,
        open,
        high,
        low,
        close,
      }));

      const candleSeries = chart.addSeries(CandlestickSeries, CANDLESTICK_OPTIONS);
      candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.25 } });
      candleSeries.setData(candles);
      seriesRefs.current.push(candleSeries);

      // 成交量柱状图（红涨绿跌，半透明）
      const volumeData = candles.map((c, i) => ({
        time: c.time,
        value: deduped[i]._volume,
        color: (i > 0 ? closes[i] >= closes[i - 1] : true)
          ? KLINE_UP_COLOR + "66"
          : KLINE_DOWN_COLOR + "66",
      }));
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
        visible: false,
      });
      volumeSeries.setData(volumeData);
      seriesRefs.current.push(volumeSeries);

      // MA 均线（叠加在 K 线图上）
      const ma5Data = candles.map((c, i) => ({ time: c.time, value: ma5[i] })).filter((d): d is { time: Time; value: number } => d.value != null);
      const ma10Data = candles.map((c, i) => ({ time: c.time, value: ma10[i] })).filter((d): d is { time: Time; value: number } => d.value != null);
      const ma20Data = candles.map((c, i) => ({ time: c.time, value: ma20[i] })).filter((d): d is { time: Time; value: number } => d.value != null);

      if (ma5Data.length >= 5) {
        const s = chart.addSeries(LineSeries, { color: MA_COLORS.ma5, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ma5Data);
        seriesRefs.current.push(s);
      }
      if (ma10Data.length >= 10) {
        const s = chart.addSeries(LineSeries, { color: MA_COLORS.ma10, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ma10Data);
        seriesRefs.current.push(s);
      }
      if (ma20Data.length >= 20) {
        const s = chart.addSeries(LineSeries, { color: MA_COLORS.ma20, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ma20Data);
        seriesRefs.current.push(s);
      }
    } else {
      // ── 非 ETF 模式：净值折线图 + MA 均线 ──
      const lineData = deduped.map((d) => ({ time: d.time, value: d.close }));

      const navLine = chart.addSeries(LineSeries, {
        color: "#0071e3",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
      });
      navLine.setData(lineData);
      seriesRefs.current.push(navLine);

      // MA 均线
      const times = deduped.map((d) => d.time);
      const ma5Data = times.map((t, i) => ({ time: t, value: ma5[i] })).filter((d): d is { time: Time; value: number } => d.value != null);
      const ma10Data = times.map((t, i) => ({ time: t, value: ma10[i] })).filter((d): d is { time: Time; value: number } => d.value != null);
      const ma20Data = times.map((t, i) => ({ time: t, value: ma20[i] })).filter((d): d is { time: Time; value: number } => d.value != null);

      if (ma5Data.length >= 5) {
        const s = chart.addSeries(LineSeries, { color: MA_COLORS.ma5, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ma5Data);
        seriesRefs.current.push(s);
      }
      if (ma10Data.length >= 10) {
        const s = chart.addSeries(LineSeries, { color: MA_COLORS.ma10, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ma10Data);
        seriesRefs.current.push(s);
      }
      if (ma20Data.length >= 20) {
        const s = chart.addSeries(LineSeries, { color: MA_COLORS.ma20, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
        s.setData(ma20Data);
        seriesRefs.current.push(s);
      }
    }

    // 保存数据条数并设置初始可见窗口（按周期×时间范围显示最近一段，而非 fitContent 显示全部）
    dataLengthRef.current = deduped.length;
    applyVisibleRange(chart);
  }, [data, isETF, applyVisibleRange]);

  // ── 时间范围变化：仅调整可视窗口，不重建 series、不强制覆盖用户缩放 ──
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || dataLengthRef.current === 0) return;
    applyVisibleRange(chart);
  }, [applyVisibleRange]);

  // ── Empty state ───────────────────────────────────────────────────────
  if (!data || data.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground" style={{ minHeight: 280 }}>
        暂无数据
      </div>
    );
  }

  // ── Render ───────────────────────────────────────────────────────────
  return (
    <div className="relative h-full w-full" style={{ minHeight: 280 }}>
      {/* Chart container */}
      <div ref={containerRef} className="h-full w-full" />

      {/* Legend */}
      <div className="pointer-events-none absolute left-2 top-2 z-10 flex gap-3 rounded bg-background/80 px-2 py-1 text-[11px] backdrop-blur-sm">
        {isETF ? (
          <>
            <span style={{ color: MA_COLORS.ma5 }}>MA5</span>
            <span style={{ color: MA_COLORS.ma10 }}>MA10</span>
            <span style={{ color: MA_COLORS.ma20 }}>MA20</span>
          </>
        ) : (
          <>
            <span style={{ color: "#0071e3", fontWeight: 600 }}>{lineLabel}</span>
            <span style={{ color: MA_COLORS.ma5 }}>MA5</span>
            <span style={{ color: MA_COLORS.ma10 }}>MA10</span>
            <span style={{ color: MA_COLORS.ma20 }}>MA20</span>
          </>
        )}
      </div>
    </div>
  );
}
