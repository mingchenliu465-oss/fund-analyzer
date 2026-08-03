"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  IChartApi,
  ISeriesApi,
  CandlestickSeriesPartialOptions,
  LineSeriesPartialOptions,
  Time,
  MouseEventParams,
} from "lightweight-charts";
import { KlinePoint, KLINE_UP_COLOR, KLINE_DOWN_COLOR } from "@/services/fund";

// ═══════════════════════════════════════════════════════════════════════════════
// Props
// ═══════════════════════════════════════════════════════════════════════════════

interface KLineChartProps {
  data: KlinePoint[];
  fundType?: string; // "ETF" → 显示成交量; 其他 → 仅显示净值走势线
}

// ═══════════════════════════════════════════════════════════════════════════════
// Crosshair tooltip state
// ═══════════════════════════════════════════════════════════════════════════════

interface CrosshairInfo {
  visible: boolean;
  x: number;
  y: number;
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  changePct: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
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

// MA colors — professional finance convention
const MA_COLORS = {
  ma5: "#ff9500",  // orange
  ma10: "#ffcc00", // yellow
  ma20: "#af52de", // purple
};

const MA_OPTIONS: Record<string, LineSeriesPartialOptions> = {
  ma5: { color: MA_COLORS.ma5, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
  ma10: { color: MA_COLORS.ma10, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
  ma20: { color: MA_COLORS.ma20, lineWidth: 1, priceLineVisible: false, lastValueVisible: false },
};

// ═══════════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════════

function normalizeDate(dateStr: string, fallbackYear: number): string {
  const trimmed = dateStr.trim();
  if (!trimmed) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    const [y, m, d] = trimmed.split("-").map(Number);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return trimmed;
    return "";
  }
  if (/^\d{4}-\d{2}$/.test(trimmed)) {
    const [y, m] = trimmed.split("-").map(Number);
    if (m >= 1 && m <= 12) return `${trimmed}-01`;
    return "";
  }
  if (/^\d{2}-\d{2}$/.test(trimmed)) {
    const [m, d] = trimmed.split("-").map(Number);
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) return `${fallbackYear}-${trimmed}`;
    return "";
  }
  return "";
}

function toEpoch(dateStr: string): number {
  return new Date(dateStr + "T00:00:00").getTime();
}

/** Compute simple moving average. Returns null for positions without enough data. */
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

/** Format a number to 4 decimal places for display. */
function fmt(n: number): string {
  return n.toFixed(4);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════════════

export function KLineChart({ data, fundType }: KLineChartProps) {
  const isETF = fundType === "ETF";
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ma5Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma10Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ma20Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const [crosshair, setCrosshair] = useState<CrosshairInfo>({
    visible: false, x: 0, y: 0,
    time: "", open: 0, high: 0, low: 0, close: 0, changePct: 0,
    ma5: null, ma10: null, ma20: null,
  });

  const closePricesRef = useRef<number[]>([]);
  const maValuesRef = useRef<{ ma5: (number | null)[]; ma10: (number | null)[]; ma20: (number | null)[] }>({
    ma5: [], ma10: [], ma20: [],
  });

  // ── Init chart + series ──────────────────────────────────────────────
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
      crosshair: {
        mode: 0,
        vertLine: {
          color: "#6b7280",
          style: 2,
          labelBackgroundColor: "#6b7280",
        },
        horzLine: {
          color: "#6b7280",
          style: 2,
          labelBackgroundColor: "#6b7280",
        },
      },
      timeScale: {
        borderColor: "#e5e7eb",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#e5e7eb",
        autoScale: true,
      },
      leftPriceScale: {
        visible: false,
      },
      localization: { locale: "zh-CN" },
    });

    // Candlestick (main price scale)
    const candleSeries = chart.addSeries(CandlestickSeries, CANDLESTICK_OPTIONS);
    candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: isETF ? 0.25 : 0.2 } });

    // Volume histogram (separate scale at bottom, ETF only)
    let volumeSeries: ISeriesApi<"Histogram"> | null = null;
    if (isETF) {
      volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
        visible: false,
      });
      volumeSeriesRef.current = volumeSeries;
    }

    // MA lines — same price scale as candlestick
    const ma5 = chart.addSeries(LineSeries, MA_OPTIONS.ma5);
    const ma10 = chart.addSeries(LineSeries, MA_OPTIONS.ma10);
    const ma20 = chart.addSeries(LineSeries, MA_OPTIONS.ma20);

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    ma5Ref.current = ma5;
    ma10Ref.current = ma10;
    ma20Ref.current = ma20;

    // Crosshair subscription
    const handleCrosshair = (param: MouseEventParams) => {
      if (!param.point || !param.time || !param.seriesData) {
        setCrosshair((prev) => ({ ...prev, visible: false }));
        return;
      }

      const candleData = param.seriesData.get(candleSeries);
      if (!candleData) {
        setCrosshair((prev) => ({ ...prev, visible: false }));
        return;
      }

      const cd = candleData as { open: number; high: number; low: number; close: number };
      const prevClose = closePricesRef.current[closePricesRef.current.length - 1];
      const changePct = prevClose ? ((cd.close - prevClose) / prevClose) * 100 : 0;

      // Find index to look up MA values
      const timeStr = param.time as string;
      const idx = closePricesRef.current.findIndex((_, i) => {
        // We stored times in candle data, but we can just get index from param
        return true; // fallback
      });

      // Use logical index from param.logical if available
      const logicalIdx = param.logical ?? 0;
      const maIdx = Math.min(logicalIdx, maValuesRef.current.ma5.length - 1);

      setCrosshair({
        visible: true,
        x: param.point.x,
        y: param.point.y,
        time: timeStr,
        open: cd.open,
        high: cd.high,
        low: cd.low,
        close: cd.close,
        changePct,
        ma5: maValuesRef.current.ma5[maIdx] ?? null,
        ma10: maValuesRef.current.ma10[maIdx] ?? null,
        ma20: maValuesRef.current.ma20[maIdx] ?? null,
      });
    };

    chart.subscribeCrosshairMove(handleCrosshair);

    // Resize
    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    };
    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.unsubscribeCrosshairMove(handleCrosshair);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      ma5Ref.current = null;
      ma10Ref.current = null;
      ma20Ref.current = null;
    };
  }, []);

  // ── Update data + MAs ────────────────────────────────────────────────
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    // Empty data
    if (!data || data.length === 0) {
      try { candleSeriesRef.current.setData([]); } catch { /* */ }
      try { ma5Ref.current?.setData([]); } catch { /* */ }
      try { ma10Ref.current?.setData([]); } catch { /* */ }
      try { ma20Ref.current?.setData([]); } catch { /* */ }
      return;
    }

    const currentYear = new Date().getFullYear();

    // Normalize + validate OHLC (carry volume/turnover through _-prefixed keys)
    const raw: { time: Time; open: number; high: number; low: number; close: number; _epoch: number; _volume: number; _turnover: number | undefined }[] = [];
    for (const point of data) {
      const date = normalizeDate(point.date, currentYear);
      if (!date) continue;
      const epoch = toEpoch(date);
      if (Number.isNaN(epoch)) continue;
      raw.push({
        time: date as Time,
        open: point.open, high: point.high, low: point.low, close: point.close,
        _epoch: epoch,
        _volume: point.volume ?? 0,
        _turnover: point.turnover,
      });
    }

    if (raw.length === 0) {
      try { candleSeriesRef.current.setData([]); } catch { /* */ }
      return;
    }

    // Sort asc, dedup
    raw.sort((a, b) => a._epoch - b._epoch);
    const seen = new Set<string>();
    const deduped = raw.filter((item) => {
      const key = item.time as string;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Strip internal fields for chart
    const candles = deduped.map(({ _epoch, _volume, _turnover, ...rest }) => rest);
    const closes = deduped.map((d) => d.close);
    const volumes = deduped.map((d) => d._volume);

    // Compute MAs
    const ma5 = computeMA(closes, 5);
    const ma10 = computeMA(closes, 10);
    const ma20 = computeMA(closes, 20);

    // Store for crosshair
    closePricesRef.current = closes;
    maValuesRef.current = { ma5, ma10, ma20 };

    // Build MA line data
    const ma5Data = candles.map((c, i) => ({ time: c.time, value: ma5[i]! })).filter((d) => d.value != null);
    const ma10Data = candles.map((c, i) => ({ time: c.time, value: ma10[i]! })).filter((d) => d.value != null);
    const ma20Data = candles.map((c, i) => ({ time: c.time, value: ma20[i]! })).filter((d) => d.value != null);

    // Build volume data (color by price direction)
    const volumeData = candles.map((c, i) => ({
      time: c.time,
      value: volumes[i],
      color: (i > 0 ? closes[i] >= closes[i - 1] : true)
        ? KLINE_UP_COLOR + "66"
        : KLINE_DOWN_COLOR + "66",
    }));

    try {
      candleSeriesRef.current.setData(candles);
      ma5Ref.current?.setData(ma5Data.length >= 5 ? ma5Data : []);
      ma10Ref.current?.setData(ma10Data.length >= 10 ? ma10Data : []);
      ma20Ref.current?.setData(ma20Data.length >= 20 ? ma20Data : []);
      if (volumeSeriesRef.current) {
        volumeSeriesRef.current.setData(volumeData);
      }
      chartRef.current?.timeScale().fitContent();
    } catch (err) {
      console.warn("KLineChart setData failed:", err);
    }
  }, [data]);

  // ── Render ───────────────────────────────────────────────────────────
  return (
    <div className="relative h-full w-full" style={{ minHeight: 280 }}>
      {/* Chart container */}
      <div ref={containerRef} className="h-full w-full" />

      {/* Crosshair OHLC tooltip */}
      {crosshair.visible && (
        <div
          className="pointer-events-none absolute z-20 rounded-lg border border-border bg-background/95 px-3 py-2 text-xs shadow-lg backdrop-blur-sm"
          style={{
            left: Math.min(crosshair.x + 12, (containerRef.current?.clientWidth ?? 400) - 180),
            top: Math.max(8, crosshair.y - 80),
          }}
        >
          <div className="mb-1 font-medium text-foreground">{crosshair.time}</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
            <span className="text-muted-foreground">开</span>
            <span className="text-right tabular-nums text-foreground">{fmt(crosshair.open)}</span>
            <span className="text-muted-foreground">高</span>
            <span className="text-right tabular-nums text-foreground">{fmt(crosshair.high)}</span>
            <span className="text-muted-foreground">低</span>
            <span className="text-right tabular-nums text-foreground">{fmt(crosshair.low)}</span>
            <span className="text-muted-foreground">收</span>
            <span className="text-right tabular-nums text-foreground">{fmt(crosshair.close)}</span>
            <span className="text-muted-foreground">涨跌</span>
            <span className={`text-right tabular-nums ${crosshair.changePct >= 0 ? "text-positive" : "text-negative"}`}>
              {crosshair.changePct >= 0 ? "+" : ""}{crosshair.changePct.toFixed(2)}%
            </span>
          </div>
          {/* MA display */}
          <div className="mt-1.5 flex gap-3 border-t border-border pt-1.5">
            <span className="tabular-nums" style={{ color: MA_COLORS.ma5 }}>
              MA5 {crosshair.ma5 != null ? fmt(crosshair.ma5) : "-"}
            </span>
            <span className="tabular-nums" style={{ color: MA_COLORS.ma10 }}>
              MA10 {crosshair.ma10 != null ? fmt(crosshair.ma10) : "-"}
            </span>
            <span className="tabular-nums" style={{ color: MA_COLORS.ma20 }}>
              MA20 {crosshair.ma20 != null ? fmt(crosshair.ma20) : "-"}
            </span>
          </div>
        </div>
      )}

      {/* MA legend (always visible, top-left) */}
      {data.length > 0 && (
        <div className="pointer-events-none absolute left-2 top-2 z-10 flex gap-3 rounded bg-background/80 px-2 py-1 text-[11px] backdrop-blur-sm">
          <span style={{ color: MA_COLORS.ma5 }}>MA5</span>
          <span style={{ color: MA_COLORS.ma10 }}>MA10</span>
          <span style={{ color: MA_COLORS.ma20 }}>MA20</span>
        </div>
      )}

      {/* Empty state */}
      {(!data || data.length === 0) && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
          暂无数据
        </div>
      )}
    </div>
  );
}
