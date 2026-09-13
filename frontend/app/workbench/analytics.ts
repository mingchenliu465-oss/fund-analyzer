export interface Point { date: string; close: number }

export function normalizePoints(value: unknown): Point[] {
  if (!Array.isArray(value)) throw new Error("数据格式异常，请稍后重试。");
  const byDate = new Map<string, Point>();
  for (const item of value) {
    if (item && typeof item.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(item.date) && typeof item.close === "number" && Number.isFinite(item.close) && item.close > 0) {
      byDate.set(item.date, { date: item.date, close: item.close });
    }
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function analyze(points: Point[], months: number) {
  const last = points.at(-1);
  const cutoff = last ? new Date(`${last.date}T00:00:00Z`) : null;
  if (cutoff) cutoff.setUTCMonth(cutoff.getUTCMonth() - months);
  const start = cutoff?.toISOString().slice(0, 10) ?? "";
  const visible = points.filter((p) => p.date >= start);
  const first = visible[0];
  let peak = first?.close ?? 0;
  const rows = visible.map((p) => {
    peak = Math.max(peak, p.close);
    return { ...p, change: (p.close / first.close - 1) * 100, drawdown: (p.close / peak - 1) * 100 };
  });
  return { rows, change: rows.length > 1 ? rows.at(-1)!.change : null, drawdown: rows.length > 1 ? Math.min(...rows.map((p) => p.drawdown)) : null };
}

// Fixed, illustrative series. Never used as an API failure fallback.
export function demoPoints(seed: number): Point[] {
  const result: Point[] = [];
  const day = new Date("2025-03-03T00:00:00Z");
  for (let i = 0; i < 550; i++) {
    if (day.getUTCDay() !== 0 && day.getUTCDay() !== 6) {
      const n = result.length;
      const close = 1 + n * (0.00045 + seed * 0.0001) + Math.sin(n / 23 + seed) * 0.055 + Math.sin(n / 5.7) * 0.015 - Math.exp(-(((n - 220) / 25) ** 2)) * 0.15;
      result.push({ date: day.toISOString().slice(0, 10), close: Number(close.toFixed(4)) });
    }
    day.setUTCDate(day.getUTCDate() + 1);
  }
  return result;
}
