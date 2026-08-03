/**
 * Fund service layer.
 *
 * Supports two modes:
 * 1. Mock mode (default): in-memory data for UI development without a backend.
 * 2. Real API mode: talk to the FastAPI backend when NEXT_PUBLIC_USE_REAL_API=true.
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
}

export interface FundDetail extends FundSummary {
  inceptionDate: string;
  returns: FundReturns;
  metrics: FundMetrics;
  sectors: Sector[];
  tags: string[];
  description: string;
  manager: string;
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
  name: string;
  value: string;
  change: number;
  up: boolean;
}

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
  todayReturn: number;
  todayReturnPct: number;
  cumulativeReturn: number;
  cumulativeReturnPct: number;
  allocation: { category: string; weight: number; color: string }[];
  riskLevel: string;
  riskScore: number;
}

export interface MarketStatus {
  status: "交易中" | "已收盘" | "未开盘";
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
}

export type NavPeriod = "5D" | "10D" | "20D" | "日K" | "周K" | "月K" | "年K" | "1M" | "3M" | "6M" | "1Y" | "3Y";

const SECTOR_COLORS = [
  "#171717",
  "#0071e3",
  "#6e6e73",
  "#00a550",
  "#ff9500",
  "#ff3b30",
  "#af52de",
  "#34c759",
  "#5856d6",
  "#d1d1d6",
];

// Chinese market convention: up = red, down = green.
export const KLINE_UP_COLOR = "#ff3b30";
export const KLINE_DOWN_COLOR = "#00a550";

// ---------------------------------------------------------------------------
// Mode switch
// ---------------------------------------------------------------------------

const USE_REAL_API = process.env.NEXT_PUBLIC_USE_REAL_API === "true";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} returned ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const FUND_POOL: FundSummary[] = [
  { code: "110020", name: "易方达沪深300ETF联接A", company: "易方达基金", type: "股票型", nav: 1.2842, changePct: 1.24, oneYearReturn: 0.1284, riskLevel: "中高", size: "120.5亿", heat: 92 },
  { code: "000905", name: "嘉实中证500ETF联接A", company: "嘉实基金", type: "股票型", nav: 2.105, changePct: 0.86, oneYearReturn: 0.0805, riskLevel: "中高", size: "85.3亿", heat: 78 },
  { code: "110022", name: "易方达消费行业", company: "易方达基金", type: "股票型", nav: 3.4521, changePct: 0.72, oneYearReturn: 0.0872, riskLevel: "高", size: "210.8亿", heat: 88 },
  { code: "000171", name: "易方达裕丰回报", company: "易方达基金", type: "债券型", nav: 1.125, changePct: 0.05, oneYearReturn: 0.0415, riskLevel: "中低", size: "45.2亿", heat: 45 },
  { code: "003474", name: "南方天天利货币", company: "南方基金", type: "货币型", nav: 1.0002, changePct: 0.01, oneYearReturn: 0.0192, riskLevel: "低", size: "320.1亿", heat: 60 },
  { code: "110003", name: "易方达上证50增强", company: "易方达基金", type: "股票型", nav: 2.8765, changePct: 1.05, oneYearReturn: 0.095, riskLevel: "中高", size: "132.6亿", heat: 70 },
  { code: "160706", name: "嘉实沪深300ETF联接", company: "嘉实基金", type: "ETF联接", nav: 1.3102, changePct: 1.18, oneYearReturn: 0.121, riskLevel: "中高", size: "95.4亿", heat: 65 },
  { code: "000001", name: "华夏成长混合", company: "华夏基金", type: "混合型", nav: 1.056, changePct: -0.34, oneYearReturn: 0.062, riskLevel: "中", size: "58.7亿", heat: 55 },
  { code: "002190", name: "农银新能源主题", company: "农银汇理基金", type: "股票型", nav: 2.341, changePct: -0.82, oneYearReturn: -0.028, riskLevel: "高", size: "76.3亿", heat: 72 },
  { code: "161725", name: "招商中证白酒指数", company: "招商基金", type: "股票型", nav: 1.562, changePct: 1.45, oneYearReturn: 0.105, riskLevel: "高", size: "185.2亿", heat: 95 },
  { code: "005827", name: "易方达蓝筹精选", company: "易方达基金", type: "混合型", nav: 2.105, changePct: 0.55, oneYearReturn: 0.071, riskLevel: "中", size: "298.5亿", heat: 82 },
  { code: "004698", name: "博时军工主题", company: "博时基金", type: "股票型", nav: 1.423, changePct: -0.21, oneYearReturn: 0.048, riskLevel: "高", size: "42.1亿", heat: 58 },
  { code: "000248", name: "汇添富中证主要消费ETF联接", company: "汇添富基金", type: "ETF联接", nav: 1.782, changePct: 0.93, oneYearReturn: 0.092, riskLevel: "中高", size: "67.8亿", heat: 63 },
  { code: "000339", name: "长城久益保本", company: "长城基金", type: "债券型", nav: 1.045, changePct: 0.03, oneYearReturn: 0.033, riskLevel: "中低", size: "12.4亿", heat: 22 },
  { code: "002621", name: "中欧消费主题", company: "中欧基金", type: "股票型", nav: 1.89, changePct: 0.67, oneYearReturn: 0.089, riskLevel: "高", size: "55.6亿", heat: 50 },
  { code: "001594", name: "天弘中证银行指数", company: "天弘基金", type: "股票型", nav: 1.234, changePct: 0.42, oneYearReturn: 0.055, riskLevel: "中高", size: "88.9亿", heat: 48 },
  { code: "003096", name: "中欧医疗健康混合", company: "中欧基金", type: "混合型", nav: 2.56, changePct: -0.15, oneYearReturn: -0.012, riskLevel: "中", size: "112.3亿", heat: 75 },
  { code: "512880", name: "国泰中证全指证券公司ETF", company: "国泰基金", type: "ETF", nav: 0.982, changePct: 2.1, oneYearReturn: 0.153, riskLevel: "高", size: "78.6亿", heat: 80 },
  { code: "510300", name: "华泰柏瑞沪深300ETF", company: "华泰柏瑞基金", type: "ETF", nav: 4.125, changePct: 1.28, oneYearReturn: 0.131, riskLevel: "高", size: "256.4亿", heat: 85 },
  { code: "518880", name: "华安黄金ETF", company: "华安基金", type: "ETF", nav: 4.56, changePct: -0.45, oneYearReturn: 0.084, riskLevel: "高", size: "68.2亿", heat: 52 },
];

const FUND_DETAILS: Record<string, FundDetail> = {
  "110020": buildDetail("110020", {
    inceptionDate: "2005-04-08",
    returns: { daily: 0.0124, weekly: 0.0215, monthly: 0.0482, yearly: 0.1284 },
    metrics: {
      maxDrawdown: -0.182,
      volatility: 0.164,
      sharpe: 0.72,
      riskLevel: "中高",
      riskScore: 68,
      alpha: 0.001,
      beta: 1.0,
      sortino: 0.95,
      informationRatio: 0.12,
    },
    sectors: [
      { name: "金融", weight: 22, color: SECTOR_COLORS[0] },
      { name: "消费", weight: 18, color: SECTOR_COLORS[1] },
      { name: "信息技术", weight: 16, color: SECTOR_COLORS[2] },
      { name: "工业", weight: 14, color: SECTOR_COLORS[3] },
      { name: "医疗保健", weight: 10, color: SECTOR_COLORS[4] },
      { name: "原材料", weight: 8, color: SECTOR_COLORS[5] },
      { name: "通信服务", weight: 7, color: SECTOR_COLORS[6] },
      { name: "其他", weight: 5, color: SECTOR_COLORS[9] },
    ],
    tags: ["宽基指数", "大盘", "长期配置"],
    description: "跟踪沪深300指数，覆盖A股市场市值最大、流动性最好的300只股票，是分享中国经济增长的核心宽基工具。",
    manager: "张弘弢",
    rating: 4,
    topHoldings: [
      { name: "贵州茅台", code: "600519", weight: 5.2, changePct: 1.1 },
      { name: "宁德时代", code: "300750", weight: 3.1, changePct: 0.8 },
      { name: "中国平安", code: "601318", weight: 2.8, changePct: 0.5 },
      { name: "招商银行", code: "600036", weight: 2.5, changePct: 0.3 },
      { name: "五粮液", code: "000858", weight: 2.1, changePct: 1.2 },
    ],
    investmentStyle: "大盘价值",
  }),
  "000905": buildDetail("000905", {
    inceptionDate: "2007-01-15",
    returns: { daily: 0.0086, weekly: 0.0142, monthly: 0.0355, yearly: 0.0805 },
    metrics: {
      maxDrawdown: -0.215,
      volatility: 0.187,
      sharpe: 0.58,
      riskLevel: "中高",
      riskScore: 72,
      alpha: -0.005,
      beta: 1.05,
      sortino: 0.78,
      informationRatio: -0.08,
    },
    sectors: [
      { name: "工业", weight: 20, color: SECTOR_COLORS[3] },
      { name: "信息技术", weight: 19, color: SECTOR_COLORS[2] },
      { name: "原材料", weight: 15, color: SECTOR_COLORS[5] },
      { name: "消费", weight: 13, color: SECTOR_COLORS[1] },
      { name: "医疗保健", weight: 12, color: SECTOR_COLORS[4] },
      { name: "金融", weight: 10, color: SECTOR_COLORS[0] },
      { name: "其他", weight: 11, color: SECTOR_COLORS[9] },
    ],
    tags: ["中小盘", "成长", "波动较大"],
    description: "跟踪中证500指数，聚焦中小市值公司，成长性较强但波动也较大，适合作为卫星配置。",
    manager: "罗文杰",
    rating: 4,
    topHoldings: [
      { name: "中际旭创", code: "300308", weight: 1.2, changePct: 2.1 },
      { name: "新易盛", code: "300502", weight: 1.0, changePct: 1.8 },
      { name: "沪电股份", code: "002463", weight: 0.9, changePct: 1.5 },
      { name: "石头科技", code: "688169", weight: 0.8, changePct: -0.5 },
      { name: "思源电气", code: "002028", weight: 0.7, changePct: 0.6 },
    ],
    investmentStyle: "中盘成长",
  }),
  "110022": buildDetail("110022", {
    inceptionDate: "2010-08-20",
    returns: { daily: 0.0072, weekly: 0.0188, monthly: 0.0521, yearly: 0.0872 },
    metrics: {
      maxDrawdown: -0.254,
      volatility: 0.192,
      sharpe: 0.55,
      riskLevel: "高",
      riskScore: 78,
      alpha: 0.008,
      beta: 0.95,
      sortino: 0.82,
      informationRatio: 0.35,
    },
    sectors: [
      { name: "食品饮料", weight: 32, color: SECTOR_COLORS[1] },
      { name: "家用电器", weight: 18, color: SECTOR_COLORS[0] },
      { name: "农林牧渔", weight: 12, color: SECTOR_COLORS[3] },
      { name: "商贸零售", weight: 10, color: SECTOR_COLORS[2] },
      { name: "社会服务", weight: 9, color: SECTOR_COLORS[4] },
      { name: "其他", weight: 19, color: SECTOR_COLORS[9] },
    ],
    tags: ["消费龙头", "行业主题", "高波动"],
    description: "重点投资消费行业龙头，长期受益于居民消费升级，但行业集中度较高，短期波动较大。",
    manager: "萧楠",
    rating: 5,
    topHoldings: [
      { name: "贵州茅台", code: "600519", weight: 9.5, changePct: 1.1 },
      { name: "五粮液", code: "000858", weight: 8.2, changePct: 1.2 },
      { name: "泸州老窖", code: "000568", weight: 6.8, changePct: 0.9 },
      { name: "美的集团", code: "000333", weight: 5.5, changePct: 0.4 },
      { name: "山西汾酒", code: "600809", weight: 4.9, changePct: 1.5 },
    ],
    investmentStyle: "大盘成长",
  }),
  "000171": buildDetail("000171", {
    inceptionDate: "2013-08-23",
    returns: { daily: 0.0005, weekly: 0.0012, monthly: 0.0038, yearly: 0.0415 },
    metrics: {
      maxDrawdown: -0.021,
      volatility: 0.032,
      sharpe: 1.25,
      riskLevel: "中低",
      riskScore: 28,
      alpha: 0.003,
      beta: 0.12,
      sortino: 1.8,
      informationRatio: 0.45,
    },
    sectors: [
      { name: "利率债", weight: 45, color: SECTOR_COLORS[0] },
      { name: "信用债", weight: 35, color: SECTOR_COLORS[1] },
      { name: "可转债", weight: 12, color: SECTOR_COLORS[2] },
      { name: "银行存款", weight: 8, color: SECTOR_COLORS[9] },
    ],
    tags: ["二级债基", "稳健", "固收+"],
    description: "以债券资产为主，适度参与权益市场，追求稳健收益，适合风险厌恶型投资者。",
    manager: "张雅君",
    rating: 4,
    topHoldings: [
      { name: "21国债10", code: "019658", weight: 8.5, changePct: 0.02 },
      { name: "22国开10", code: "220210", weight: 6.2, changePct: 0.01 },
      { name: "浦发转债", code: "110059", weight: 3.1, changePct: 0.05 },
      { name: "兴业转债", code: "113052", weight: 2.8, changePct: 0.03 },
      { name: "20工行二级", code: "2028045", weight: 2.5, changePct: 0.01 },
    ],
    investmentStyle: "稳健收益",
  }),
  "003474": buildDetail("003474", {
    inceptionDate: "2016-11-04",
    returns: { daily: 0.0001, weekly: 0.0004, monthly: 0.0016, yearly: 0.0192 },
    metrics: {
      maxDrawdown: 0,
      volatility: 0.001,
      sharpe: 0.05,
      riskLevel: "低",
      riskScore: 8,
      alpha: 0.0,
      beta: 0.01,
      sortino: 0.02,
      informationRatio: 0.0,
    },
    sectors: [
      { name: "银行存款", weight: 55, color: SECTOR_COLORS[0] },
      { name: "同业存单", weight: 30, color: SECTOR_COLORS[1] },
      { name: "回购资产", weight: 10, color: SECTOR_COLORS[2] },
      { name: "债券", weight: 5, color: SECTOR_COLORS[9] },
    ],
    tags: ["货币基金", "流动性", "低风险"],
    description: "主要投资于短期货币工具，流动性好、风险极低，是现金管理的理想选择。",
    manager: "夏晨曦",
    rating: 3,
    topHoldings: [
      { name: "银行存款", weight: 55, changePct: 0.0 },
      { name: "同业存单", weight: 30, changePct: 0.0 },
      { name: "回购资产", weight: 10, changePct: 0.0 },
      { name: "短期债券", weight: 5, changePct: 0.0 },
    ],
    investmentStyle: "现金管理",
  }),
  "512880": buildDetail("512880", {
    inceptionDate: "2016-07-26",
    returns: { daily: 0.021, weekly: 0.0455, monthly: 0.0812, yearly: 0.153 },
    metrics: {
      maxDrawdown: -0.287,
      volatility: 0.245,
      sharpe: 0.62,
      riskLevel: "高",
      riskScore: 85,
      alpha: 0.012,
      beta: 1.25,
      sortino: 0.88,
      informationRatio: 0.22,
    },
    sectors: [
      { name: "证券公司", weight: 92, color: SECTOR_COLORS[0] },
      { name: "其他金融", weight: 8, color: SECTOR_COLORS[9] },
    ],
    tags: ["证券ETF", "牛市弹性", "高Beta"],
    description: "跟踪中证全指证券公司指数，与资本市场活跃度高度相关，牛市弹性大但回撤也深。",
    manager: "艾小军",
    rating: 4,
    topHoldings: [
      { name: "东方财富", code: "300059", weight: 14.5, changePct: 3.2 },
      { name: "中信证券", code: "600030", weight: 12.8, changePct: 2.1 },
      { name: "海通证券", code: "600837", weight: 8.5, changePct: 1.8 },
      { name: "华泰证券", code: "601688", weight: 7.2, changePct: 1.5 },
      { name: "国泰君安", code: "601211", weight: 6.8, changePct: 1.3 },
    ],
    investmentStyle: "行业主题",
  }),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildDetail(code: string, partial: Omit<FundDetail, keyof FundSummary | "code">): FundDetail {
  const summary = FUND_POOL.find((f) => f.code === code);
  if (!summary) throw new Error(`Fund ${code} not found in pool`);
  return { ...summary, code, ...partial };
}

function getRiskProfile(type: string): Pick<FundMetrics, "riskLevel" | "riskScore"> {
  switch (type) {
    case "货币型":
      return { riskLevel: "低", riskScore: 8 };
    case "债券型":
      return { riskLevel: "中低", riskScore: 28 };
    case "混合型":
      return { riskLevel: "中", riskScore: 52 };
    case "ETF联接":
      return { riskLevel: "中高", riskScore: 65 };
    case "ETF":
      return { riskLevel: "高", riskScore: 80 };
    case "股票型":
    default:
      return { riskLevel: "中高", riskScore: 70 };
  }
}

function defaultTopHoldings(type: string): TopHolding[] {
  if (type === "货币型") {
    return [
      { name: "银行存款", weight: 55, changePct: 0.0 },
      { name: "同业存单", weight: 30, changePct: 0.0 },
      { name: "回购资产", weight: 10, changePct: 0.0 },
      { name: "短期债券", weight: 5, changePct: 0.0 },
    ];
  }
  if (type === "债券型") {
    return [
      { name: "21国债10", code: "019658", weight: 8.5, changePct: 0.02 },
      { name: "22国开10", code: "220210", weight: 6.2, changePct: 0.01 },
      { name: "浦发转债", code: "110059", weight: 3.1, changePct: 0.05 },
      { name: "兴业转债", code: "113052", weight: 2.8, changePct: 0.03 },
      { name: "20工行二级", code: "2028045", weight: 2.5, changePct: 0.01 },
    ];
  }
  return [
    { name: "贵州茅台", code: "600519", weight: 5.2, changePct: 1.1 },
    { name: "宁德时代", code: "300750", weight: 3.1, changePct: 0.8 },
    { name: "中国平安", code: "601318", weight: 2.8, changePct: 0.5 },
    { name: "招商银行", code: "600036", weight: 2.5, changePct: 0.3 },
    { name: "五粮液", code: "000858", weight: 2.1, changePct: 1.2 },
  ];
}

function defaultSectors(type: string): Sector[] {
  if (type === "货币型") {
    return [
      { name: "银行存款", weight: 55, color: SECTOR_COLORS[0] },
      { name: "同业存单", weight: 30, color: SECTOR_COLORS[1] },
      { name: "回购资产", weight: 10, color: SECTOR_COLORS[2] },
      { name: "债券", weight: 5, color: SECTOR_COLORS[9] },
    ];
  }
  if (type === "债券型") {
    return [
      { name: "利率债", weight: 45, color: SECTOR_COLORS[0] },
      { name: "信用债", weight: 35, color: SECTOR_COLORS[1] },
      { name: "可转债", weight: 12, color: SECTOR_COLORS[2] },
      { name: "银行存款", weight: 8, color: SECTOR_COLORS[9] },
    ];
  }
  return [
    { name: "金融", weight: 20, color: SECTOR_COLORS[0] },
    { name: "消费", weight: 18, color: SECTOR_COLORS[1] },
    { name: "信息技术", weight: 16, color: SECTOR_COLORS[2] },
    { name: "工业", weight: 14, color: SECTOR_COLORS[3] },
    { name: "医疗保健", weight: 12, color: SECTOR_COLORS[4] },
    { name: "原材料", weight: 8, color: SECTOR_COLORS[5] },
    { name: "通信服务", weight: 7, color: SECTOR_COLORS[6] },
    { name: "其他", weight: 5, color: SECTOR_COLORS[9] },
  ];
}

function styleForType(type: string): string {
  if (type === "货币型") return "现金管理";
  if (type === "债券型") return "稳健收益";
  if (type === "混合型") return "股债平衡";
  if (type.includes("ETF")) return "指数跟踪";
  return "主动权益";
}

function syntheticDetail(summary: FundSummary): FundDetail {
  const { riskLevel, riskScore } = getRiskProfile(summary.type);
  const yearly = summary.oneYearReturn;
  const volatility = Math.max(0.005, Math.abs(yearly) * 0.9 + 0.05);
  const sharpe = yearly / (volatility + 0.001);

  return buildDetail(summary.code, {
    inceptionDate: "2015-01-01",
    returns: {
      daily: summary.changePct * 0.01,
      weekly: summary.changePct * 1.5 * 0.01,
      monthly: summary.changePct * 3 * 0.01,
      yearly,
    },
    metrics: {
      maxDrawdown: -Math.min(0.5, volatility * 1.2 + 0.02),
      volatility: Math.min(0.5, volatility),
      sharpe: Math.min(2.5, Math.max(-1, sharpe)),
      riskLevel,
      riskScore,
      alpha: 0.0,
      beta: typeBeta(summary.type),
      sortino: Math.min(2.5, Math.max(-1, sharpe * 1.1)),
      informationRatio: 0.0,
    },
    sectors: defaultSectors(summary.type),
    tags: [summary.type, styleForType(summary.type)],
    description: `${summary.name}是一只${summary.type}基金，由${summary.company}管理。以上为模拟数据，仅用于前端展示。`,
    manager: "基金经理（模拟）",
    rating: 3,
    topHoldings: defaultTopHoldings(summary.type),
    investmentStyle: styleForType(summary.type),
  });
}

function typeBeta(type: string): number {
  if (type === "货币型") return 0.01;
  if (type === "债券型") return 0.12;
  if (type === "混合型") return 0.75;
  if (type === "ETF联接") return 0.98;
  if (type === "ETF") return 1.05;
  return 0.95;
}

function periodConfig(period: NavPeriod) {
  switch (period) {
    case "5D":
      return { count: 5, stepDays: 1, labelFormat: "MM-dd" as const };
    case "10D":
      return { count: 10, stepDays: 1, labelFormat: "MM-dd" as const };
    case "20D":
      return { count: 20, stepDays: 1, labelFormat: "MM-dd" as const };
    case "日K":
      return { count: 42, stepDays: 1, labelFormat: "MM-dd" as const };
    case "周K":
      return { count: 26, stepDays: 7, labelFormat: "MM-dd" as const };
    case "月K":
      return { count: 24, stepDays: 30, labelFormat: "yyyy-MM" as const };
    case "年K":
      return { count: 5, stepDays: 365, labelFormat: "yyyy-MM" as const };
    case "1M":
      return { count: 22, stepDays: 1, labelFormat: "MM-dd" as const };
    case "3M":
      return { count: 12, stepDays: 7, labelFormat: "MM-dd" as const };
    case "6M":
      return { count: 12, stepDays: 14, labelFormat: "MM-dd" as const };
    case "1Y":
      return { count: 12, stepDays: 30, labelFormat: "yyyy-MM" as const };
    case "3Y":
      return { count: 12, stepDays: 90, labelFormat: "yyyy-MM" as const };
  }
}

function formatDate(date: Date, format: "MM-dd" | "yyyy-MM"): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return format === "MM-dd" ? `${m}-${d}` : `${y}-${m}`;
}

function seededRandom(seed: string) {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash << 5) - hash + seed.charCodeAt(i);
    hash |= 0;
  }
  return () => {
    hash = (hash * 9301 + 49297) % 233280;
    return hash / 233280;
  };
}

function generateNavHistory(fund: FundDetail, period: NavPeriod): NavPoint[] {
  const { count, stepDays, labelFormat } = periodConfig(period);
  const rng = seededRandom(`${fund.code}-${period}`);
  const endDate = new Date();
  const points: NavPoint[] = [];

  const annualReturn = fund.returns.yearly;
  const annualVol = fund.metrics.volatility;
  const periodReturn = (annualReturn * (stepDays * count)) / 365;
  const periodVol = annualVol * Math.sqrt((stepDays * count) / 365);

  let nav = fund.nav / (1 + periodReturn);
  const startNormalized = 1.0;
  const totalGrowth = 1 + periodReturn;

  for (let i = 0; i < count; i++) {
    const date = new Date(endDate);
    date.setDate(date.getDate() - stepDays * (count - 1 - i));

    const trend = Math.pow(totalGrowth, i / (count - 1));
    const noise = 1 + (rng() - 0.5) * periodVol * 2.5;
    nav = (fund.nav / totalGrowth) * trend * noise;

    points.push({
      date: formatDate(date, labelFormat),
      nav: Number(nav.toFixed(4)),
      normalized: Number(((nav / (fund.nav / totalGrowth)) * startNormalized).toFixed(4)),
    });
  }

  if (points.length > 0) {
    points[points.length - 1].nav = fund.nav;
    points[points.length - 1].normalized = Number((fund.nav / (fund.nav / totalGrowth)).toFixed(4));
  }

  return points;
}

function generateDrawdownHistory(fund: FundDetail, period: NavPeriod): DrawdownPoint[] {
  const navHistory = generateNavHistory(fund, period);
  const points: DrawdownPoint[] = [];
  let peak = -Infinity;

  for (const point of navHistory) {
    if (point.nav > peak) peak = point.nav;
    const drawdown = (point.nav - peak) / peak;
    points.push({ date: point.date, drawdown: Number(drawdown.toFixed(4)) });
  }

  return points;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function searchFunds(query: string): Promise<FundSummary[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<FundSummary[]>(`/api/funds/search?q=${encodeURIComponent(query.trim())}`);
    } catch (err) {
      console.warn("searchFunds API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 120));
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return FUND_POOL.filter(
    (f) => f.code.toLowerCase().includes(q) || f.name.toLowerCase().includes(q)
  );
}

export async function getAllFunds(query?: string): Promise<FundSummary[]> {
  if (USE_REAL_API) {
    try {
      const path = query
        ? `/api/funds?q=${encodeURIComponent(query.trim())}&limit=1000`
        : "/api/funds";
      return await fetchJson<FundSummary[]>(path);
    } catch (err) {
      console.warn("getAllFunds API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 100));
  let funds = [...FUND_POOL];
  if (query) {
    const q = query.trim().toLowerCase();
    funds = funds.filter(
      (f) => f.code.toLowerCase().includes(q) || f.name.toLowerCase().includes(q)
    );
  }
  return funds;
}

export async function getFundDetail(code: string): Promise<FundDetail | null> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<FundDetail>(`/api/funds/${encodeURIComponent(code.trim().toUpperCase())}`);
    } catch (err) {
      console.warn("getFundDetail API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 180));
  const upper = code.trim().toUpperCase();
  if (FUND_DETAILS[upper]) return FUND_DETAILS[upper];
  const summary = FUND_POOL.find((f) => f.code === upper);
  if (!summary) return null;
  return syntheticDetail(summary);
}

export async function getFundNavHistory(
  code: string,
  period: NavPeriod = "1Y"
): Promise<NavPoint[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<NavPoint[]>(
        `/api/funds/${encodeURIComponent(code.trim().toUpperCase())}/nav-history?period=${period}`
      );
    } catch (err) {
      console.warn("getFundNavHistory API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 160));
  const fund = await getFundDetail(code);
  if (!fund) return [];
  return generateNavHistory(fund, period);
}

export async function getFundKlineHistory(
  code: string,
  period: NavPeriod = "日K"
): Promise<KlinePoint[]> {
  try {
    return await fetchJson<KlinePoint[]>(
      `/api/market/kline?code=${encodeURIComponent(code.trim().toUpperCase())}&period=${period}`
    );
  } catch (err) {
    console.warn("getFundKlineHistory failed:", err);
    return [];
  }
}

export async function getFundDrawdownHistory(
  code: string,
  period: NavPeriod = "1Y"
): Promise<DrawdownPoint[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<DrawdownPoint[]>(
        `/api/analysis/drawdown/${encodeURIComponent(code.trim().toUpperCase())}?period=${period}`
      );
    } catch (err) {
      console.warn("getFundDrawdownHistory API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 160));
  const fund = await getFundDetail(code);
  if (!fund) return [];
  return generateDrawdownHistory(fund, period);
}

export async function listPopularFunds(limit = 6): Promise<FundSummary[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<FundSummary[]>(`/api/funds/popular?limit=${limit}`);
    } catch (err) {
      console.warn("listPopularFunds API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 100));
  return FUND_POOL.slice(0, limit);
}

export async function getFundRankings(limit = 10): Promise<FundSummary[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<FundSummary[]>(`/api/funds/rankings?limit=${limit}`);
    } catch (err) {
      console.warn("getFundRankings API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 100));
  return [...FUND_POOL].sort((a, b) => b.oneYearReturn - a.oneYearReturn).slice(0, limit);
}

export async function getRecentlyWatched(): Promise<FundSummary[]> {
  // 从 portfolio 持仓中取最近查看的基金代码
  try {
    const res = await fetchJson<{ holdings: { fund_code: string }[] }>("/api/portfolio/holdings");
    const codes = [...new Set(res.holdings.map((h) => h.fund_code))].slice(0, 6);
    const details = await Promise.all(codes.map((code) => getFundDetail(code)));
    return details.filter((d): d is FundDetail => d !== null);
  } catch {
    return [];
  }
}

export async function getMarketIndices(): Promise<MarketIndex[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<MarketIndex[]>("/api/market/indices");
    } catch (err) {
      console.warn("getMarketIndices API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 80));
  return [
    { name: "沪深300", value: "3,842.15", change: 1.24, up: true },
    { name: "中证500", value: "5,621.38", change: 0.86, up: true },
    { name: "创业板指", value: "2,018.72", change: -0.34, up: false },
    { name: "中证全债", value: "245.18", change: 0.05, up: true },
  ];
}

export async function getMarketStatus(): Promise<MarketStatus> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<MarketStatus>("/api/market/status");
    } catch (err) {
      console.warn("getMarketStatus API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 60));
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const timeStr = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;

  if ((hour === 9 && minute >= 30) || (hour === 10) || (hour === 11 && minute <= 30) || (hour >= 13 && hour < 15)) {
    return { status: "交易中", session: "A股连续竞价", updateTime: timeStr };
  }
  if (hour >= 15 || hour < 9 || (hour === 9 && minute < 30)) {
    return { status: "已收盘", session: "等待下一交易日", updateTime: timeStr };
  }
  return { status: "未开盘", session: "午间休市", updateTime: timeStr };
}

export async function getPortfolioOverview(): Promise<PortfolioOverview> {
  try {
    return await fetchJson<PortfolioOverview>("/api/portfolio");
  } catch (err) {
    console.warn("getPortfolioOverview failed:", err);
    return {
      totalAssets: 0, todayReturn: 0, todayReturnPct: 0,
      cumulativeReturn: 0, cumulativeReturnPct: 0,
      allocation: [], riskLevel: "暂无", riskScore: 0,
    };
  }
}

export async function getPeerComparison(code: string): Promise<PeerComparison[]> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<PeerComparison[]>(
        `/api/analysis/peers/${encodeURIComponent(code.trim().toUpperCase())}`
      );
    } catch (err) {
      console.warn("getPeerComparison API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 140));
  const fund = await getFundDetail(code);
  if (!fund) return [];

  const peers = FUND_POOL.filter(
    (f) => f.code !== fund.code && (f.type === fund.type || f.type.includes("ETF"))
  ).slice(0, 4);

  return peers.map((p) => ({
    code: p.code,
    name: p.name,
    type: p.type,
    oneYearReturn: p.oneYearReturn,
    volatility: riskLevelToVolatility(p.riskLevel),
    sharpe: p.oneYearReturn / (riskLevelToVolatility(p.riskLevel) + 0.001),
    riskLevel: p.riskLevel,
  }));
}

// ── 真实持仓 API ──

export async function getRealPortfolio(): Promise<RealPortfolioSummary> {
  return fetchJson<RealPortfolioSummary>("/api/portfolio");
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

function riskLevelToVolatility(riskLevel: FundSummary["riskLevel"]): number {
  switch (riskLevel) {
    case "低":
      return 0.002;
    case "中低":
      return 0.03;
    case "中":
      return 0.12;
    case "中高":
      return 0.17;
    case "高":
      return 0.23;
    default:
      return 0.15;
  }
}

export async function getReturnRanking(code: string): Promise<ReturnRanking> {
  if (USE_REAL_API) {
    try {
      return await fetchJson<ReturnRanking>(
        `/api/analysis/ranking/${encodeURIComponent(code.trim().toUpperCase())}`
      );
    } catch (err) {
      console.warn("getReturnRanking API failed, fallback to mock", err);
    }
  }
  await new Promise((r) => setTimeout(r, 120));
  const sorted = [...FUND_POOL].sort((a, b) => b.oneYearReturn - a.oneYearReturn);
  const rank = sorted.findIndex((f) => f.code === code) + 1;
  const total = sorted.length;
  return {
    rank: rank || total,
    total,
    percentile: Math.round(((rank || total) / total) * 100),
  };
}

// ---------------------------------------------------------------------------
// Formatting helpers (presentational but commonly used alongside service data)
// ---------------------------------------------------------------------------

export function formatPercent(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

export function formatRatio(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export function formatCurrency(value: number, digits = 2): string {
  return `¥${value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export function formatAsset(value: number): string {
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(2)}万`;
  return value.toFixed(2);
}
