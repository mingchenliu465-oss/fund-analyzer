/**
 * Fund service layer.
 *
 * Data policy: this module only ever returns real, server-provided data. There is
 * no mock/demo mode and no fabricated fallback. When a request fails it throws;
 * the caller must render an explicit error state ("数据暂时不可用") and must never
 * substitute placeholder or generated numbers.
 *
 * Set NEXT_PUBLIC_API_URL to point to the backend (e.g. http://localhost:8000).
 * When running through Next.js dev server, /api/* is rewritten to the backend
 * automatically via next.config.ts, so the default empty API base works.
 */

export interface FundSummary {
  code: string;
  name: string;
  company: string;
  type: string;
  nav: number;
  changePct: number;
  oneYearReturn: number;
  riskLevel: "低" | "中低" | "中" | "中高" | "高";
  size: string;
  heat: number;
}

export interface FundReturns {
  daily: number;
  weekly: number;
  monthly: number;
  yearly: number;
}

export interface FundMetrics {
  maxDrawdown: number; // e.g. -0.182 for -18.2%
  volatility: number; // e.g. 0.164 for 16.4%
  sharpe: number;
  riskLevel: FundSummary["riskLevel"];
  riskScore: number; // 0 - 100
  alpha: number;
  beta: number;
  sortino: number;
  informationRatio: number;
}

export interface Sector {
  name: string;
  weight: number;
  color: string;
}

export interface TopHolding {
  name: string;
  code?: string;
  weight: number;
  changePct: number;
  assetType?: "股票" | "债券" | "基金" | "其他";
}

export interface FundDetail extends FundSummary {
  inceptionDate: string;
  returns: FundReturns;
  metrics: FundMetrics;
  sectors: Sector[];
  tags: string[];
  description: string;
  manager: string;
  /** 基金经理从业天数；数据源未提供时为 undefined（不做任何估算或补齐）。 */
  managerDays?: number;
  rating: number; // 1 - 5
  topHoldings: TopHolding[];
  investmentStyle: string;
}

export interface NavPoint {
  date: string; // ISO date or month label
  nav: number;
  normalized: number;
}

export interface KlinePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;   // ETF 成交量
  turnover?: number;  // ETF 成交额
}

export interface DrawdownPoint {
  date: string;
  drawdown: number; // negative, e.g. -0.18
}

export interface MarketIndex {
  code: string;
  name: string;
  value: string;
  change: number;
  up: boolean;
}

const MARKET_INDEX_CODE_BY_NAME: Record<string, string> = {
  上证指数: "sh000001",
  深证成指: "sz399001",
  沪深300: "sh000300",
  创业板指: "sz399006",
  中证500: "sh000905",
  中证全债: "H11001",
};

export interface PeerComparison {
  code: string;
  name: string;
  type: string;
  oneYearReturn: number;
  volatility: number;
  sharpe: number;
  riskLevel: string;
}

export interface ReturnRanking {
  rank: number;
  total: number;
  percentile: number; // 0-100, lower is better
}

export interface PortfolioOverview {
  totalAssets: number;
  /** 后端组合总览不提供日内变动时为 null —— 不填充 0，避免伪装成真实数据。 */
  todayReturn: number | null;
  todayReturnPct: number | null;
  cumulativeReturn: number;
  cumulativeReturnPct: number;
  allocation: { category: string; weight: number; color: string }[];
  riskLevel: string;
  riskScore: number;
}

export interface MarketStatus {
  status: "交易中" | "已收盘" | "未开盘" | "午间休市";
  session: string;
  updateTime: string;
}

// ── 真实持仓类型 ──

export interface HoldingItem {
  id: number;
  fund_code: string;
  fund_name: string;
  fund_type: string;
  buy_date: string;
  buy_amount: number;
  buy_nav: number;
  shares: number;
  fee: number;
  notes: string;
  is_sold: boolean;
  sell_date: string | null;
  sell_amount: number | null;
  sell_nav: number | null;
  current_nav: number | null;
  current_value: number | null;
  cost: number | null;
  profit: number | null;
  profit_pct: number | null;
}

export interface HoldingCreate {
  fund_code: string;
  fund_name: string;
  fund_type?: string;
  buy_date: string;
  buy_amount: number;
  buy_nav: number;
  shares: number;
  fee?: number;
  notes?: string;
}

export interface RealPortfolioSummary {
  total_cost: number;
  total_value: number;
  total_profit: number;
  total_profit_pct: number;
  holding_count: number;
  holdings: HoldingItem[];
  has_stale_nav: boolean;
}

export interface PortfolioHistoryPoint {
  date: string;
  total_value: number;
  total_cost: number;
  profit: number;
  profit_rate: number;
}

export type PortfolioHistoryPeriod = "1W" | "1M" | "3M" | "1Y" | "ALL";

export interface AttributionContribution {
  fund_type: string;
  current_value: number;
  nav_stale: boolean;
  fund_code: string;
  fund_name: string;
  shares: number;
  nav: number;
  prev_nav: number;
  change_pct: number;
  contribution: number;
  contribution_rate: number;
}

export interface AttributionSummary {
  has_stale_nav: boolean;
  total_assets: number;
  today_return: number;
  today_return_pct: number;
  holding_count: number;
  gainers_count: number;
  losers_count: number;
  top_gainer_name: string | null;
  top_loser_name: string | null;
  note: string;
}

export interface AttributionResult {
  today_return: number;
  today_return_pct: number;
  yesterday_value: number;
  summary: AttributionSummary;
  contributions: AttributionContribution[];
  top_gainer: AttributionContribution | null;
  top_loser: AttributionContribution | null;
}

export interface PortfolioInsightContribution {
  fund_code: string;
  fund_name: string;
  fund_type: string;
  current_value: number;
  change_pct: number;
  contribution: number;
  contribution_rate: number;
  nav_stale: boolean;
}

export interface PortfolioInsights {
  period: string;
  generated_at: string;
  data_status: "ready" | "partial" | "empty" | string;
  headline: {
    today_return: number;
    today_return_pct: number;
    sentence: string;
    data_status: string;
  };
  return_explanation: {
    contributions: PortfolioInsightContribution[];
    top_gainers: PortfolioInsightContribution[];
    top_draggers: PortfolioInsightContribution[];
    positive_total: number;
    negative_total: number;
    stale_count: number;
  };
  risk: {
    allocation: { category: string; value: number; weight_pct: number; holding_count: number }[];
    max_holding: { fund_code: string | null; fund_name: string | null; value: number; weight_pct: number };
    concentration_ratio: number;
    hhi: number;
    concentration_level: string;
    overlap_status: string;
    overlap_pairs: { fund_a: string; fund_b: string; shared_holdings: string[]; overlap_pct: number; data_as_of: string | null }[];
    notes: string[];
  };
  market_comparison: {
    code: string;
    name: string;
    portfolio_return_pct: number | null;
    index_return_pct: number | null;
    relative_return_pct: number | null;
    available: boolean;
    reason: string | null;
  }[];
  history: {
    points: { date: string; total_value: number; profit: number; day_change: number | null; day_change_pct: number | null; is_anomaly: boolean }[];
    trend: string;
    anomaly_detected: boolean;
    anomaly_date: string | null;
    anomaly_reason: string | null;
    data_sufficiency: string;
    note: string;
  };
  review_context: { key: string; label: string; value: string; source: string }[];
  notes: string[];
}

export interface HoldStructurePoint {
  date: string;
  fundCount: number;
  institutionPct: number;
  individualPct: number;
  internalPct: number;
  totalShares: number;
}

export interface HoldStructure {
  points: HoldStructurePoint[];
  note: string;
}

export interface SellFormData {
  sell_date: string;
  sell_amount: number;
  sell_nav: number;
}

export type NavPeriod = "5D" | "10D" | "20D" | "日K" | "周K" | "月K" | "年K" | "1M" | "3M" | "6M" | "1Y" | "3Y";

// Chinese market convention: up = red, down = green.
export const KLINE_UP_COLOR = "#ff3b30";
export const KLINE_DOWN_COLOR = "#00a550";

// ---------------------------------------------------------------------------
// API base
// ---------------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const DEFAULT_TIMEOUT_MS = 30000; // 30 秒超时（后端 akshare 冷启动可能较慢，15s 偏紧）
const FAST_READ_TIMEOUT_MS = 2500;
const DETAIL_TIMEOUT_MS = 8000;
const MARKET_TIMEOUT_MS = 20000;

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`API ${path} returned ${res.status}: ${text}`);
    }
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${timeoutMs / 1000}秒）: ${path}。请检查网络连接或关闭 VPN 后重试。`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function searchFunds(query: string): Promise<FundSummary[]> {
  const q = query.trim();
  if (!q) return [];
  return fetchJson<FundSummary[]>(
    `/api/funds/search?q=${encodeURIComponent(q)}`,
    undefined,
    FAST_READ_TIMEOUT_MS
  );
}

export async function getAllFunds(query?: string): Promise<FundSummary[]> {
  const path = query
    ? `/api/funds?q=${encodeURIComponent(query.trim())}&limit=1000`
    : "/api/funds";
  return fetchJson<FundSummary[]>(path);
}

export async function getFundDetail(code: string): Promise<FundDetail> {
  const detail = await fetchJson<FundDetail>(
    `/api/funds/${encodeURIComponent(code.trim().toUpperCase())}`,
    undefined,
    DETAIL_TIMEOUT_MS
  );
  return { ...detail, sectors: normalizeSectors(detail.sectors) };
}

/** Keep API inconsistencies from rendering impossible allocation percentages. */
export function normalizeSectors(sectors: Sector[] | undefined): Sector[] {
  if (!Array.isArray(sectors)) return [];
  const valid = sectors.filter((sector) => Number.isFinite(sector.weight) && sector.weight > 0);
  const total = valid.reduce((sum, sector) => sum + sector.weight, 0);
  if (!total) return [];
  const multiplier = total <= 1.05 ? 100 : 1;
  const scale = total > 100.5 ? 100 / total : 1;
  const normalized = valid.map((sector) => ({ ...sector, weight: Math.round(sector.weight * multiplier * scale * 100) / 100 }));
  normalized.sort((a, b) => b.weight - a.weight);
  const top = normalized.slice(0, 10);
  const remainder = Math.round((100 - top.reduce((sum, sector) => sum + sector.weight, 0)) * 100) / 100;
  if (remainder > 0.05) {
    const other = top.find((sector) => sector.name === "其他");
    if (other) other.weight = Math.round((other.weight + remainder) * 100) / 100;
    else top.push({ name: "其他", weight: remainder, color: "#d1d1d6" });
  }
  return top;
}

export async function getFundNavHistory(
  code: string,
  period: NavPeriod = "1Y"
): Promise<NavPoint[]> {
  return fetchJson<NavPoint[]>(
    `/api/funds/${encodeURIComponent(code.trim().toUpperCase())}/nav-history?period=${encodeURIComponent(period)}`
  );
}

export async function getFundKlineHistory(
  code: string,
  period: NavPeriod = "日K"
): Promise<KlinePoint[]> {
  return fetchJson<KlinePoint[]>(
    `/api/market/kline?code=${encodeURIComponent(
      code.trim().toUpperCase()
    )}&period=${encodeURIComponent(period)}`,
    undefined,
    DETAIL_TIMEOUT_MS
  );
}

export async function getMarketIndexKlineHistory(
  code: string,
  period: NavPeriod = "日K"
): Promise<KlinePoint[]> {
  return fetchJson<KlinePoint[]>(
    `/api/market/indices/${encodeURIComponent(code.trim())}/kline?period=${encodeURIComponent(period)}`,
    undefined,
    MARKET_TIMEOUT_MS
  );
}

export async function getFundDrawdownHistory(
  code: string,
  period: NavPeriod = "1Y"
): Promise<DrawdownPoint[]> {
  return fetchJson<DrawdownPoint[]>(
    `/api/analysis/drawdown/${encodeURIComponent(code.trim().toUpperCase())}?period=${encodeURIComponent(period)}`,
    undefined,
    DETAIL_TIMEOUT_MS
  );
}

export async function listPopularFunds(limit = 6): Promise<FundSummary[]> {
  return fetchJson<FundSummary[]>(`/api/funds/popular?limit=${limit}`);
}

export async function getFundRankings(limit = 10): Promise<FundSummary[]> {
  return fetchJson<FundSummary[]>(
    `/api/funds/rankings?limit=${limit}`,
    undefined,
    FAST_READ_TIMEOUT_MS
  );
}

// ── 最近浏览（本地 localStorage，替代后端"最近关注=持仓"的误导逻辑）──

const RECENT_WATCHED_KEY = "fund_analyzer_recent_watched";
const RECENT_WATCHED_MAX = 6;

export function getBrowsedFunds(): FundSummary[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENT_WATCHED_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as FundSummary[]) : [];
  } catch {
    return [];
  }
}

export function recordBrowsedFund(fund: FundSummary): void {
  if (typeof window === "undefined") return;
  try {
    const existing = getBrowsedFunds().filter((f) => f.code !== fund.code);
    existing.unshift(fund);
    window.localStorage.setItem(
      RECENT_WATCHED_KEY,
      JSON.stringify(existing.slice(0, RECENT_WATCHED_MAX))
    );
  } catch {
    // localStorage 不可用（隐私模式等）时静默忽略
  }
}

export async function getRecentlyWatched(): Promise<FundSummary[]> {
  // 最近浏览 = 用户在详情页查看过的基金（本地记录），而非持仓。
  return getBrowsedFunds();
}

export async function getMarketIndices(): Promise<MarketIndex[]> {
  const rows = await fetchJson<(Omit<MarketIndex, "code"> & { code?: string })[]>(
    "/api/market/indices",
    undefined,
    MARKET_TIMEOUT_MS
  );
  return rows.map((item) => ({
    ...item,
    code: item.code || MARKET_INDEX_CODE_BY_NAME[item.name] || "",
  }));
}

export async function getMarketStatus(): Promise<MarketStatus> {
  // 交易时段是确定的本地规则，无需为它增加一次网络往返。
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const weekday = now.getDay();
  const isTradingDay = weekday >= 1 && weekday <= 5;
  const timeStr = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;

  if (isTradingDay && ((hour === 9 && minute >= 30) || (hour === 10) || (hour === 11 && minute <= 30) || (hour >= 13 && hour < 15))) {
    return { status: "交易中", session: "A股连续竞价", updateTime: timeStr };
  }
  if (!isTradingDay || hour >= 15 || hour < 9 || (hour === 9 && minute < 30)) {
    return { status: "已收盘", session: "等待下一交易日", updateTime: timeStr };
  }
  return { status: "未开盘", session: "午间休市", updateTime: timeStr };
}

// ── 基金类型 → 颜色映射 ──

const TYPE_COLORS: Record<string, string> = {
  "股票型": "#3b82f6",
  "混合型": "#8b5cf6",
  "债券型": "#10b981",
  "货币型": "#f59e0b",
  "ETF": "#ef4444",
  "ETF联接": "#f97316",
  "QDII": "#06b6d4",
};

function transformPortfolioToOverview(summary: RealPortfolioSummary): PortfolioOverview {
  const holdings = summary.holdings ?? [];

  // 按基金类型汇总持仓市值，生成仓位分配
  const typeValues: Record<string, number> = {};
  for (const h of holdings) {
    const type = h.fund_type || "其他";
    typeValues[type] = (typeValues[type] ?? 0) + (h.current_value ?? 0);
  }

  const totalValue = summary.total_value;
  const allocation: PortfolioOverview["allocation"] = [];

  for (const [category, value] of Object.entries(typeValues)) {
    if (value > 0 && totalValue > 0) {
      allocation.push({
        category,
        weight: Math.round((value / totalValue) * 100),
        color: TYPE_COLORS[category] ?? "#6b7280",
      });
    }
  }
  allocation.sort((a, b) => b.weight - a.weight);

  // 根据仓位推导风险等级和评分
  let stockWeight = 0;
  for (const [type, value] of Object.entries(typeValues)) {
    if (type === "股票型" || type === "ETF" || type === "ETF联接") stockWeight += value;
  }

  let riskLevel: string;
  let riskScore: number;

  if (totalValue > 0) {
    const stockRatio = stockWeight / totalValue;
    if (stockRatio >= 0.7)      { riskLevel = "高";   riskScore = 80; }
    else if (stockRatio >= 0.4) { riskLevel = "中高"; riskScore = 60; }
    else if (stockRatio >= 0.2) { riskLevel = "中";   riskScore = 40; }
    else if (stockRatio > 0)    { riskLevel = "中低"; riskScore = 20; }
    else                         { riskLevel = "低";   riskScore = 10; }
  } else {
    riskLevel = "暂无";
    riskScore = 0;
  }

  return {
    totalAssets: totalValue,
    // 不编造日内收益：/api/portfolio 不返回该字段，无数据即 null。
    todayReturn: null,
    todayReturnPct: null,
    cumulativeReturn: summary.total_profit,
    cumulativeReturnPct: summary.total_profit_pct,
    allocation,
    riskLevel,
    riskScore,
  };
}

export async function getPortfolioOverview(): Promise<PortfolioOverview> {
  const summary = await fetchJson<RealPortfolioSummary>(
    "/api/portfolio",
    undefined,
    DETAIL_TIMEOUT_MS
  );
  return transformPortfolioToOverview(summary);
}

export async function getPeerComparison(code: string): Promise<PeerComparison[]> {
  return fetchJson<PeerComparison[]>(
    `/api/analysis/peers/${encodeURIComponent(code.trim().toUpperCase())}`,
    undefined,
    DETAIL_TIMEOUT_MS
  );
}

// ── 真实持仓 API ──

export async function getRealPortfolio(): Promise<RealPortfolioSummary> {
  return fetchJson<RealPortfolioSummary>("/api/portfolio", undefined, DETAIL_TIMEOUT_MS);
}

export async function getPortfolioHistory(
  period: PortfolioHistoryPeriod = "1M"
): Promise<PortfolioHistoryPoint[]> {
  const res = await fetchJson<{ points: PortfolioHistoryPoint[] }>(
    `/api/portfolio/history?period=${period}`
  );
  return res.points ?? [];
}

export async function getPortfolioAttribution(): Promise<AttributionResult> {
  return fetchJson<AttributionResult>("/api/portfolio/attribution");
}

export async function getPortfolioInsights(
  period: PortfolioHistoryPeriod = "1M"
): Promise<PortfolioInsights> {
  return fetchJson<PortfolioInsights>(
    `/api/portfolio/insights?period=${period}`,
    undefined,
    MARKET_TIMEOUT_MS
  );
}

// ── 自动定投 ──
export interface DripCreateInput {
  fund_code: string;
  fund_name: string;
  fund_type?: string;
  amount: number;
  frequency: "daily" | "weekly" | "monthly";
  start_date: string;
  end_date: string;
  day_of_week?: number;
  fee?: number;
  notes?: string;
}

export interface DripResult {
  created: number;
  items: HoldingItem[];
  skipped: { date: string; reason: string }[];
}

export async function autoDrip(data: DripCreateInput): Promise<DripResult> {
  return fetchJson<DripResult>("/api/portfolio/auto-drip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export interface DailyReviewSegment {
  type: string;
  text: string;
}

export interface DailyReview {
  date: string;
  provider: "llm" | "rules";
  segments: DailyReviewSegment[];
  summary: string;
}

export async function getDailyReview(): Promise<DailyReview> {
  return fetchJson<DailyReview>("/api/review/daily");
}

export async function createHolding(data: HoldingCreate): Promise<HoldingItem> {
  return fetchJson<HoldingItem>("/api/portfolio/holdings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function sellHolding(id: number, data: { sell_date: string; sell_amount: number; sell_nav: number }): Promise<HoldingItem> {
  return fetchJson<HoldingItem>(`/api/portfolio/holdings/${id}/sell`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteHolding(id: number): Promise<void> {
  await fetchJson<void>(`/api/portfolio/holdings/${id}`, { method: "DELETE" });
}

export async function updateHolding(id: number, data: HoldingCreate): Promise<HoldingItem> {
  return fetchJson<HoldingItem>(`/api/portfolio/holdings/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getAllHoldings(): Promise<HoldingItem[]> {
  return fetchJson<HoldingItem[]>("/api/portfolio/holdings?include_sold=true");
}

export async function getHoldStructure(): Promise<HoldStructure> {
  return fetchJson<HoldStructure>(
    "/api/analysis/hold-structure",
    undefined,
    DETAIL_TIMEOUT_MS
  );
}

export async function getReturnRanking(code: string): Promise<ReturnRanking> {
  return fetchJson<ReturnRanking>(
    `/api/analysis/ranking/${encodeURIComponent(code.trim().toUpperCase())}`,
    undefined,
    DETAIL_TIMEOUT_MS
  );
}

// ---------------------------------------------------------------------------
// Formatting helpers (presentational but commonly used alongside service data)
// ---------------------------------------------------------------------------

/**
 * 把"小数比率"格式化为百分比：0.9802 → "+98.02%"。
 * 只用于 ratio 语义字段（oneYearReturn / volatility / maxDrawdown / alpha / drawdown）。
 */
export function formatPercent(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

/**
 * 把"百分数"字段格式化为百分比：98.02 → "+98.02%"。
 *
 * 后端所有 `*_pct` 字段（total_profit_pct / change_pct / today_return_pct /
 * change_pct / profit_pct）本身就是百分数，必须用这个函数格式化。
 * 不要再对它们写 `* 0.01` 或 `* 100` 之类的换算 —— 单位不一致正是
 * "首页累计收益率放大 100 倍" 的根因。
 */
export function formatPercentValue(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatRatio(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export function formatCurrency(value: number | null | undefined, digits = 2): string {
  return `¥${(value ?? 0).toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function formatAsset(value: number | null | undefined): string {
  const v = value ?? 0;
  if (v >= 100000000) return `${(v / 100000000).toFixed(2)}亿`;
  if (v >= 10000) return `${(v / 10000).toFixed(2)}万`;
  return v.toFixed(2);
}
