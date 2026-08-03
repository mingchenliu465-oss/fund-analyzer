"""基金数据服务。

使用 akshare 从东方财富、天天基金、雪球等公开接口获取国内基金数据，
并通过内存 TTL 缓存降低调用频率。对于 akshare 无法覆盖的字段（行业分布、
重仓股、基金经理完整履历等），使用基于基金类型的合理默认值补齐，确保
前端类型始终完整。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd

from models.fund import FundDetail, FundMetrics, FundReturns, FundSummary, Sector, TopHolding

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Cache
# -----------------------------------------------------------------------------

_CACHE: dict[str, tuple[Any, float]] = {}
_DEFAULT_TTL_SECONDS = 300  # 5 分钟
_LIST_TTL_SECONDS = 1800  # 30 分钟


def _get_cache(key: str) -> Any | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.time() > expiry:
        del _CACHE[key]
        return None
    return value


def _set_cache(key: str, value: Any, ttl: int = _DEFAULT_TTL_SECONDS) -> None:
    _CACHE[key] = (value, time.time() + ttl)


# -----------------------------------------------------------------------------
# Fund list
# -----------------------------------------------------------------------------

_DEFAULT_FUND_CODES = [
    "000001",
    "000300",
    "000905",
    "110022",
    "000171",
    "003474",
    "110003",
    "160706",
    "002190",
    "161725",
    "005827",
    "004698",
    "000248",
    "000339",
    "002621",
    "001594",
    "003096",
    "512880",
    "510300",
    "518880",
]


_FUND_LIST_SNAPSHOT: list[FundSummary] | None = None


def _load_fund_list() -> list[FundSummary]:
    """从 akshare 拉取全部基金列表并缓存。失败时返回默认快照。"""
    cached = _get_cache("fund_list")
    if cached is not None:
        return cached

    try:
        df = ak.fund_name_em()
        df = df.drop_duplicates(subset=["基金代码"], keep="first")
        funds: list[FundSummary] = []
        for _, row in df.iterrows():
            code = str(row["基金代码"]).strip()
            name = str(row["基金简称"]).strip()
            ftype = str(row["基金类型"]).strip()
            funds.append(
                FundSummary(
                    code=code,
                    name=name,
                    company="",
                    type=_simplify_type(ftype),
                    nav=0.0,
                    change_pct=0.0,
                    one_year_return=0.0,
                    risk_level=_risk_level_for_type(ftype),
                    size="-",
                    heat=_heat_score(name, ftype),
                )
            )
        _set_cache("fund_list", funds, _LIST_TTL_SECONDS)
        return funds
    except Exception as exc:
        logger.warning("akshare fund_name_em failed: %s, using default snapshot", exc)
        return _default_fund_list()


def _default_fund_list() -> list[FundSummary]:
    """当 akshare 不可用时使用的默认基金池（来自前端 mock）。"""
    return [
        FundSummary(
            code=code,
            name=name,
            company=company,
            type=ftype,
            nav=nav,
            change_pct=change_pct,
            one_year_return=one_year_return,
            risk_level=risk_level,
            size=size,
            heat=heat,
        )
        for code, name, company, ftype, nav, change_pct, one_year_return, risk_level, size, heat in [
            ("000300", "沪深300指数基金", "华夏基金", "股票型", 1.2842, 1.24, 0.1284, "中高", "120.5亿", 92),
            ("000905", "中证500指数基金", "南方基金", "股票型", 2.105, 0.86, 0.0805, "中高", "85.3亿", 78),
            ("110022", "易方达消费行业", "易方达基金", "股票型", 3.4521, 0.72, 0.0872, "高", "210.8亿", 88),
            ("000171", "易方达裕丰回报", "易方达基金", "债券型", 1.125, 0.05, 0.0415, "中低", "45.2亿", 45),
            ("003474", "南方天天利货币", "南方基金", "货币型", 1.0002, 0.01, 0.0192, "低", "320.1亿", 60),
            ("110003", "易方达上证50增强", "易方达基金", "股票型", 2.8765, 1.05, 0.095, "中高", "132.6亿", 70),
            ("160706", "嘉实沪深300ETF联接", "嘉实基金", "ETF联接", 1.3102, 1.18, 0.121, "中高", "95.4亿", 65),
            ("000001", "华夏成长混合", "华夏基金", "混合型", 1.056, -0.34, 0.062, "中", "58.7亿", 55),
            ("002190", "农银新能源主题", "农银汇理基金", "股票型", 2.341, -0.82, -0.028, "高", "76.3亿", 72),
            ("161725", "招商中证白酒指数", "招商基金", "股票型", 1.562, 1.45, 0.105, "高", "185.2亿", 95),
            ("005827", "易方达蓝筹精选", "易方达基金", "混合型", 2.105, 0.55, 0.071, "中", "298.5亿", 82),
            ("004698", "博时军工主题", "博时基金", "股票型", 1.423, -0.21, 0.048, "高", "42.1亿", 58),
            ("000248", "汇添富中证主要消费ETF联接", "汇添富基金", "ETF联接", 1.782, 0.93, 0.092, "中高", "67.8亿", 63),
            ("000339", "长城久益保本", "长城基金", "债券型", 1.045, 0.03, 0.033, "中低", "12.4亿", 22),
            ("002621", "中欧消费主题", "中欧基金", "股票型", 1.89, 0.67, 0.089, "高", "55.6亿", 50),
            ("001594", "天弘中证银行指数", "天弘基金", "股票型", 1.234, 0.42, 0.055, "中高", "88.9亿", 48),
            ("003096", "中欧医疗健康混合", "中欧基金", "混合型", 2.56, -0.15, -0.012, "中", "112.3亿", 75),
            ("512880", "国泰中证全指证券公司ETF", "国泰基金", "ETF", 0.982, 2.1, 0.153, "高", "78.6亿", 80),
            ("510300", "华泰柏瑞沪深300ETF", "华泰柏瑞基金", "ETF", 4.125, 1.28, 0.131, "高", "256.4亿", 85),
            ("518880", "华安黄金ETF", "华安基金", "ETF", 4.56, -0.45, 0.084, "高", "68.2亿", 52),
        ]
    ]


def _simplify_type(raw: str) -> str:
    """把 akshare 的基金类型归一化为前端展示类型。"""
    if "货币" in raw:
        return "货币型"
    if "债券" in raw:
        return "债券型"
    if "ETF" in raw:
        return "ETF"
    if "联接" in raw or "LOF" in raw:
        return "ETF联接"
    if "混合" in raw:
        return "混合型"
    if "股票" in raw:
        return "股票型"
    return "混合型"


def _risk_level_for_type(raw: str) -> str:
    if "货币" in raw:
        return "低"
    if "债券" in raw:
        return "中低"
    if "混合" in raw:
        return "中"
    if "ETF" in raw or "联接" in raw or "LOF" in raw:
        return "中高"
    if "股票" in raw:
        return "高"
    return "中高"


def _heat_score(name: str, ftype: str) -> int:
    """简单热度分：货币基金固定 50，ETF/白酒/新能源/蓝筹等关键词加分。"""
    score = 50
    hot_keywords = ["白酒", "新能源", "蓝筹", "军工", "证券", "医疗", "消费", "黄金", "300", "500"]
    for kw in hot_keywords:
        if kw in name:
            score += 8
    if "ETF" in ftype:
        score += 5
    if "货币" in ftype:
        score = 50
    return min(99, max(10, score))


# -----------------------------------------------------------------------------
# Net value history
# -----------------------------------------------------------------------------


def _fetch_nav_history(code: str) -> pd.DataFrame:
    """获取场外基金历史净值 DataFrame，列：净值日期、单位净值、日增长率。"""
    cache_key = f"nav:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势", period="成立来")
        df = df.dropna(subset=["净值日期", "单位净值"])
        df["净值日期"] = pd.to_datetime(df["净值日期"])
        df = df.sort_values("净值日期").reset_index(drop=True)
        _set_cache(cache_key, df)
        return df
    except Exception as exc:
        logger.warning("nav history fetch failed for %s: %s", code, exc)
        return pd.DataFrame(columns=["净值日期", "单位净值", "日增长率"])


def _etf_sina_symbol(code: str) -> str:
    """510300 → sh510300, 159915 → sz159915"""
    code = code.strip()
    if code.startswith(("51", "56", "58")):
        return f"sh{code}"
    if code.startswith(("15", "16")):
        return f"sz{code}"
    return f"sh{code}"  # 默认上海


def _fetch_etf_history(code: str, days: int = 730) -> pd.DataFrame:
    """获取场内 ETF 历史行情。优先使用新浪数据源（稳定），失败回退东方财富。"""
    cache_key = f"etf:{code}:{days}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    empty_df = pd.DataFrame(columns=["净值日期", "单位净值", "open", "high", "low", "close", "volume", "turnover"])

    # ── 方案1: 新浪数据源（稳定，返回 date/open/high/low/close/volume/amount）──
    try:
        sina_sym = _etf_sina_symbol(code)
        df = ak.fund_etf_hist_sina(symbol=sina_sym)
        if not df.empty and "date" in df.columns:
            df = df.rename(columns={
                "date": "净值日期",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
                "amount": "turnover",
            })
            df["净值日期"] = pd.to_datetime(df["净值日期"])
            df["单位净值"] = df["close"]
            df = df[df["净值日期"] >= datetime.now() - timedelta(days=days)]
            df = df.sort_values("净值日期").reset_index(drop=True)
            if not df.empty:
                _set_cache(cache_key, df)
                return df
    except Exception as exc:
        logger.warning("sina etf history failed for %s: %s", code, exc)

    # ── 方案2: 东方财富数据源（备用）──
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = ak.fund_etf_hist_em(
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        df = df.rename(columns={
            "日期": "净值日期",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "turnover",
        })
        df["净值日期"] = pd.to_datetime(df["净值日期"])
        df["单位净值"] = df["close"]
        df = df.sort_values("净值日期").reset_index(drop=True)
        _set_cache(cache_key, df)
        return df
    except Exception as exc:
        logger.warning("eastmoney etf history failed for %s: %s", code, exc)
        return empty_df


# -----------------------------------------------------------------------------
# Detail enrichment
# -----------------------------------------------------------------------------


def _fetch_basic_info(code: str) -> dict[str, str]:
    """从雪球获取基金基本信息。"""
    cache_key = f"basic:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        df = ak.fund_individual_basic_info_xq(symbol=code)
        info = {str(k).strip(): str(v).strip() for k, v in zip(df["item"], df["value"])}
        _set_cache(cache_key, info)
        return info
    except Exception as exc:
        logger.warning("basic info fetch failed for %s: %s", code, exc)
        return {}


def _parse_size(size_str: str) -> str:
    if not size_str or size_str in ("nan", "<NA>", "None"):
        return "-"
    return size_str


def _parse_date(date_str: str) -> str:
    if not date_str or date_str in ("nan", "<NA>", "None"):
        return "2015-01-01"
    return date_str[:10]


def _returns_from_nav(nav_df: pd.DataFrame) -> FundReturns:
    """基于净值序列计算日/周/月/年收益。"""
    if nav_df.empty or len(nav_df) < 2:
        return FundReturns(daily=0.0, weekly=0.0, monthly=0.0, yearly=0.0)

    nav = nav_df["单位净值"].astype(float)
    dates = nav_df["净值日期"]
    latest = float(nav.iloc[-1])

    def _pct_for_days(days: int) -> float:
        target = dates.iloc[-1] - timedelta(days=days)
        past = nav_df[dates <= target]
        if past.empty:
            return 0.0
        past_nav = float(past["单位净值"].iloc[-1])
        return (latest - past_nav) / past_nav if past_nav else 0.0

    daily = (latest - float(nav.iloc[-2])) / float(nav.iloc[-2]) if len(nav) >= 2 else 0.0
    weekly = _pct_for_days(7)
    monthly = _pct_for_days(30)
    yearly = _pct_for_days(365)

    return FundReturns(daily=daily, weekly=weekly, monthly=monthly, yearly=yearly)


def _metrics_from_nav(nav_df: pd.DataFrame, ftype: str) -> FundMetrics:
    """基于净值序列计算风险指标。"""
    if nav_df.empty or len(nav_df) < 2:
        risk_level, risk_score = _risk_profile(ftype)
        return FundMetrics(
            max_drawdown=0.0,
            volatility=0.02,
            sharpe=0.0,
            risk_level=risk_level,
            risk_score=risk_score,
            alpha=0.0,
            beta=0.5,
            sortino=0.0,
            information_ratio=0.0,
        )

    nav = nav_df["单位净值"].astype(float).values
    returns = nav[1:] / nav[:-1] - 1

    # 年化波动率（按 252 个交易日）
    volatility = float(returns.std() * (252**0.5)) if len(returns) > 1 else 0.02

    # 最大回撤
    peak = nav[0]
    max_dd = 0.0
    for v in nav:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    # 夏普：无风险利率按 2% 年化
    risk_free_daily = 0.02 / 252
    excess = returns - risk_free_daily
    sharpe = float(excess.mean() / excess.std() * (252**0.5)) if excess.std() > 0 else 0.0

    risk_level, risk_score = _risk_profile(ftype, volatility)

    return FundMetrics(
        max_drawdown=-max_dd,
        volatility=volatility,
        sharpe=round(sharpe, 2),
        risk_level=risk_level,
        risk_score=risk_score,
        alpha=0.0,
        beta=_type_beta(ftype),
        sortino=round(sharpe * 1.1, 2),
        information_ratio=0.0,
    )


def _risk_profile(ftype: str, volatility: float | None = None) -> tuple[str, int]:
    if ftype == "货币型":
        return "低", 8
    if ftype == "债券型":
        return "中低", 28
    if ftype == "混合型":
        return "中", 52
    if ftype in ("ETF联接",):
        return "中高", 65
    if ftype == "ETF":
        if volatility is not None and volatility > 0.25:
            return "高", 85
        return "高", 80
    if volatility is not None:
        if volatility < 0.05:
            return "低", 10
        if volatility < 0.12:
            return "中低", 30
        if volatility < 0.18:
            return "中", 50
        if volatility < 0.25:
            return "中高", 68
        return "高", 80
    return "中高", 70


def _type_beta(ftype: str) -> float:
    if ftype == "货币型":
        return 0.01
    if ftype == "债券型":
        return 0.12
    if ftype == "混合型":
        return 0.75
    if ftype == "ETF联接":
        return 0.98
    if ftype == "ETF":
        return 1.05
    return 0.95


def _risk_level_to_volatility(risk_level: str) -> float:
    if risk_level == "低":
        return 0.002
    if risk_level == "中低":
        return 0.03
    if risk_level == "中":
        return 0.12
    if risk_level == "中高":
        return 0.17
    if risk_level == "高":
        return 0.23
    return 0.15


def _default_sectors(ftype: str) -> list[Sector]:
    colors = ["#171717", "#0071e3", "#6e6e73", "#00a550", "#ff9500", "#ff3b30", "#af52de", "#34c759", "#5856d6", "#d1d1d6"]
    if ftype == "货币型":
        return [
            Sector(name="银行存款", weight=55, color=colors[0]),
            Sector(name="同业存单", weight=30, color=colors[1]),
            Sector(name="回购资产", weight=10, color=colors[2]),
            Sector(name="债券", weight=5, color=colors[9]),
        ]
    if ftype == "债券型":
        return [
            Sector(name="利率债", weight=45, color=colors[0]),
            Sector(name="信用债", weight=35, color=colors[1]),
            Sector(name="可转债", weight=12, color=colors[2]),
            Sector(name="银行存款", weight=8, color=colors[9]),
        ]
    return [
        Sector(name="金融", weight=20, color=colors[0]),
        Sector(name="消费", weight=18, color=colors[1]),
        Sector(name="信息技术", weight=16, color=colors[2]),
        Sector(name="工业", weight=14, color=colors[3]),
        Sector(name="医疗保健", weight=12, color=colors[4]),
        Sector(name="原材料", weight=8, color=colors[5]),
        Sector(name="通信服务", weight=7, color=colors[6]),
        Sector(name="其他", weight=5, color=colors[9]),
    ]


def _default_top_holdings(ftype: str) -> list[TopHolding]:
    if ftype == "货币型":
        return [
            TopHolding(name="银行存款", weight=55, change_pct=0.0),
            TopHolding(name="同业存单", weight=30, change_pct=0.0),
            TopHolding(name="回购资产", weight=10, change_pct=0.0),
            TopHolding(name="短期债券", weight=5, change_pct=0.0),
        ]
    if ftype == "债券型":
        return [
            TopHolding(name="21国债10", code="019658", weight=8.5, change_pct=0.02),
            TopHolding(name="22国开10", code="220210", weight=6.2, change_pct=0.01),
            TopHolding(name="浦发转债", code="110059", weight=3.1, change_pct=0.05),
            TopHolding(name="兴业转债", code="113052", weight=2.8, change_pct=0.03),
            TopHolding(name="20工行二级", code="2028045", weight=2.5, change_pct=0.01),
        ]
    return [
        TopHolding(name="贵州茅台", code="600519", weight=5.2, change_pct=1.1),
        TopHolding(name="宁德时代", code="300750", weight=3.1, change_pct=0.8),
        TopHolding(name="中国平安", code="601318", weight=2.8, change_pct=0.5),
        TopHolding(name="招商银行", code="600036", weight=2.5, change_pct=0.3),
        TopHolding(name="五粮液", code="000858", weight=2.1, change_pct=1.2),
    ]


def _style_for_type(ftype: str) -> str:
    if ftype == "货币型":
        return "现金管理"
    if ftype == "债券型":
        return "稳健收益"
    if ftype == "混合型":
        return "股债平衡"
    if ftype in ("ETF", "ETF联接"):
        return "指数跟踪"
    return "主动权益"


def _tags_for(name: str, ftype: str) -> list[str]:
    tags = [ftype, _style_for_type(ftype)]
    if "300" in name:
        tags.append("宽基指数")
    if "500" in name:
        tags.append("中小盘")
    if "消费" in name:
        tags.append("消费龙头")
    if "新能源" in name:
        tags.append("成长赛道")
    if "白酒" in name:
        tags.append("行业主题")
    if "医药" in name or "医疗" in name:
        tags.append("医药健康")
    return tags[:4]


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def list_all() -> list[FundSummary]:
    return _load_fund_list()


def _type_from_name_list(code: str) -> str:
    """从基金名称列表中查询某只基金的类型。"""
    funds = _load_fund_list()
    f = next((f for f in funds if f.code == code), None)
    return f.type if f else "混合型"


def rankings(limit: int = 10) -> list[FundSummary]:
    """基于 akshare 开放式基金/ETF 排行榜返回近一年收益排名。"""
    cache_key = f"rankings:{limit}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        open_df = ak.fund_open_fund_rank_em()
    except Exception:
        open_df = pd.DataFrame()

    try:
        etf_df = ak.fund_exchange_rank_em()
    except Exception:
        etf_df = pd.DataFrame()

    results: list[FundSummary] = []
    for df in (open_df, etf_df):
        if df.empty:
            continue
        for _, row in df.head(limit).iterrows():
            code = str(row.get("基金代码", "")).strip()
            name = str(row.get("基金简称", "")).strip()
            raw_type = str(row.get("类型", "")).strip() if "类型" in df.columns else ""
            ftype = _simplify_type(raw_type) if raw_type else _type_from_name_list(code)
            try:
                nav = float(row.get("单位净值", 0)) if "单位净值" in df.columns else 0.0
            except Exception:
                nav = 0.0
            try:
                change_pct = float(row.get("日增长率", 0)) if "日增长率" in df.columns else 0.0
            except Exception:
                change_pct = 0.0
            try:
                one_year = float(row.get("近1年", 0)) / 100 if "近1年" in df.columns else 0.0
            except Exception:
                one_year = 0.0

            results.append(
                FundSummary(
                    code=code,
                    name=name,
                    company="-",
                    type=ftype,
                    nav=round(nav, 4),
                    change_pct=round(change_pct, 2),
                    one_year_return=round(one_year, 4),
                    risk_level=_risk_level_for_type(ftype),
                    size="-",
                    heat=max(10, 95 - len(results) * 2),
                )
            )

    # 去重并按近一年收益排序
    seen: set[str] = set()
    unique: list[FundSummary] = []
    for f in results:
        if f.code not in seen:
            seen.add(f.code)
            unique.append(f)
    unique.sort(key=lambda f: f.one_year_return, reverse=True)
    result = unique[:limit]
    _set_cache(cache_key, result, ttl=1800)
    return result


def popular(limit: int = 6) -> list[FundSummary]:
    """返回热门基金（默认用排行榜前 N 条）。"""
    return rankings(limit)


def search(query: str) -> list[FundSummary]:
    q = query.strip().lower()
    if not q:
        return []
    funds = _load_fund_list()
    return [f for f in funds if q in f.code.lower() or q in f.name.lower()][:20]


def get_by_code(code: str) -> FundDetail:
    upper = code.strip().upper()

    # 1. 先尝试从 akshare 获取真实数据
    basic = _fetch_basic_info(upper)
    name = basic.get("基金名称", "")
    ftype_raw = basic.get("基金类型", "")
    ftype = _simplify_type(ftype_raw) if ftype_raw else ""

    if not name:
        # 回退到基金列表
        funds = _load_fund_list()
        summary = next((f for f in funds if f.code == upper), None)
        if summary is None:
            raise ValueError(f"Fund {code} not found")
        name = summary.name
        ftype = summary.type

    # 2. 获取历史净值
    is_etf = ftype == "ETF"
    nav_df = _fetch_etf_history(upper) if is_etf else _fetch_nav_history(upper)

    # 3. 计算当前净值与涨跌幅
    if not nav_df.empty:
        latest_nav = float(nav_df["单位净值"].iloc[-1])
        if len(nav_df) >= 2:
            prev_nav = float(nav_df["单位净值"].iloc[-2])
            change_pct = (latest_nav - prev_nav) / prev_nav * 100
        else:
            change_pct = 0.0
    else:
        latest_nav = 1.0
        change_pct = 0.0

    returns = _returns_from_nav(nav_df) if not nav_df.empty else FundReturns(daily=0.0, weekly=0.0, monthly=0.0, yearly=0.0)
    metrics = _metrics_from_nav(nav_df, ftype)

    # 4. 补齐展示字段
    company = basic.get("基金公司", "-").replace("基金管理有限公司", "基金")
    size = _parse_size(basic.get("最新规模", "-"))
    inception = _parse_date(basic.get("成立时间", "2015-01-01"))
    manager = basic.get("基金经理", "-")
    description = basic.get("投资目标", f"{name}是一只{ftype}基金，由{company}管理。")

    return FundDetail(
        code=upper,
        name=name,
        company=company,
        type=ftype,
        nav=round(latest_nav, 4),
        change_pct=round(change_pct, 2),
        one_year_return=round(returns.yearly, 4),
        risk_level=metrics.risk_level,
        size=size,
        heat=_heat_score(name, ftype),
        inception_date=inception,
        returns=returns,
        metrics=metrics,
        sectors=_default_sectors(ftype),
        tags=_tags_for(name, ftype),
        description=description,
        manager=manager,
        rating=3,
        top_holdings=_default_top_holdings(ftype),
        investment_style=_style_for_type(ftype),
    )


def nav_history(code: str) -> pd.DataFrame:
    """返回该基金可用的历史净值/价格 DataFrame。"""
    upper = code.strip().upper()
    try:
        detail = get_by_code(upper)
    except ValueError:
        detail = None

    if detail and detail.type == "ETF":
        return _fetch_etf_history(upper)
    return _fetch_nav_history(upper)
