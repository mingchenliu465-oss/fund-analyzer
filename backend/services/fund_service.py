"""基金数据服务。

使用 akshare 从东方财富、天天基金、雪球等公开接口获取国内基金数据，
并通过内存 TTL 缓存降低调用频率。对于 akshare 无法覆盖的字段（行业分布、
重仓股、基金经理完整履历等），使用基于基金类型的合理默认值补齐，确保
前端类型始终完整。
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock, Thread
from typing import Any, Callable, TypeVar

import akshare as ak
import pandas as pd

from models.fund import FundDetail, FundMetrics, FundReturns, FundSummary, Sector, TopHolding

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Cache
# -----------------------------------------------------------------------------

_CACHE: dict[str, tuple[Any, float]] = {}
_DEFAULT_TTL_SECONDS = 1800  # 30 分钟（基金净值数据日内不更新）
_LIST_TTL_SECONDS = 3600  # 1 小时（基金列表与排行榜每天更新一次）


def _get_cache(key: str) -> Any | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.time() > expiry:
        _CACHE.pop(key, None)
        return None
    return value


def _set_cache(key: str, value: Any, ttl: int = _DEFAULT_TTL_SECONDS) -> None:
    _CACHE[key] = (value, time.time() + ttl)


# -----------------------------------------------------------------------------
# Timeout wrapper for akshare calls (prevents VPN/proxy hangs)
# -----------------------------------------------------------------------------

_AKSHARE_TIMEOUT = 6  # 交互请求快速失败并回退缓存，避免页面长时间无响应

_AkExecute = TypeVar("_AkExecute")


def _call_akshare(func: Callable[..., _AkExecute], *args: Any, timeout: int = _AKSHARE_TIMEOUT, **kwargs: Any) -> _AkExecute:
    """在独立线程中调用 akshare 函数并设置超时。

    超时时抛出 TimeoutError，调用方应捕获并回退到缓存/默认数据。
    这样可以避免 VPN 或代理导致的无限挂起。
    """
    future: Future[_AkExecute] = Future()

    def _runner() -> None:
        try:
            result = func(*args, **kwargs)
            if not future.done():
                future.set_result(result)
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    try:
        return future.result(timeout=timeout)
    except Exception:
        # TimeoutError 或 akshare 内部异常：取消 future，但线程会自行结束（daemon）
        if not future.done():
            future.cancel()
        raise


# -----------------------------------------------------------------------------
# Fund list
# -----------------------------------------------------------------------------

_DEFAULT_FUND_CODES = [
    "000001",
    "000300",
    "000905",
    "110020",
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
    "510050",
    "159915",
    "000295",
    "519300",
]


_FUND_LIST_SNAPSHOT: list[FundSummary] | None = None

# 基金列表加载锁：warmup 与并发请求同时触发时会重复调用慢接口（fund_name_em
# 实测 16s+），导致双双超时回退默认快照。用锁实现单飞（single-flight），
# 并发调用排队等待，第一个加载完成后其余直接命中缓存。
_FUND_LIST_LOCK = Lock()


def _build_enrichment_lookup() -> dict[str, dict[str, float]]:
    """从 akshare 排行榜获取真实净值/收益率数据，构建 code → 数据的查找表。
    缓存 60 分钟，因为排行榜数据每天只更新一次。
    """
    cache_key = "enrichment_lookup"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    lookup: dict[str, dict[str, float]] = {}
    try:
        df = _call_akshare(_open_rank_frame, timeout=30)
        for _, row in df.iterrows():
            code = str(row.get("基金代码", "")).strip()
            if not code:
                continue
            try:
                nav = float(row.get("单位净值", 0) or 0)
                change = float(row.get("日增长率", 0) or 0)
                ret_1y = float(row.get("近1年", 0) or 0) / 100  # 百分比转小数
            except (ValueError, TypeError):
                continue
            lookup[code] = {"nav": nav, "change_pct": change, "one_year_return": ret_1y}
        _set_cache(cache_key, lookup, ttl=3600)  # 1 小时
        logger.info("Enrichment lookup built: %d funds", len(lookup))
    except Exception as exc:
        logger.warning("Failed to build enrichment lookup: %s", exc)
        _set_cache(cache_key, {}, ttl=600)  # 失败时缓存空结果 10 分钟
    return lookup


def _load_fund_list() -> list[FundSummary]:
    """从 akshare 拉取全部基金列表，用排行榜数据丰富后缓存。失败时返回默认快照。"""
    cached = _get_cache("fund_list")
    if cached is not None:
        return cached

    with _FUND_LIST_LOCK:
        # 双重检查：排队等待期间可能已被其他线程（含启动预热）加载完成
        cached = _get_cache("fund_list")
        if cached is not None:
            return cached

        try:
            # fund_name_em 全市场列表较大（实测 16s+），默认 12s 超时会被误掐断导致
            # 只能回退默认快照；这里单独放宽到 45s，并与排行榜丰富数据并行获取，
            # 冷启动总耗时趋近最慢的一个请求而不是两者之和。
            with ThreadPoolExecutor(max_workers=2) as _ex:
                _f_list = _ex.submit(_call_akshare, ak.fund_name_em, timeout=45)
                _f_enrich = _ex.submit(_build_enrichment_lookup)
                df = _f_list.result()
                enrichment = _f_enrich.result()

            df = df.drop_duplicates(subset=["基金代码"], keep="first")

            funds: list[FundSummary] = []
            for _, row in df.iterrows():
                code = str(row["基金代码"]).strip()
                name = str(row["基金简称"]).strip()
                raw_ftype = str(row["基金类型"]).strip()
                enriched = enrichment.get(code, {})
                # 场内 ETF 用代码前缀覆盖类型，避免数据源误标为"股票型"
                ftype = "ETF" if _is_etf_code(code) else _simplify_type(raw_ftype)

                funds.append(
                    FundSummary(
                        code=code,
                        name=name,
                        company=_extract_company(name),
                        type=ftype,
                        nav=round(enriched.get("nav", 0.0), 4),
                        change_pct=round(enriched.get("change_pct", 0.0), 2),
                        one_year_return=round(enriched.get("one_year_return", 0.0), 4),
                        risk_level=_risk_level_for_type(ftype),
                        size="-",
                        heat=_heat_score(name, ftype),
                    )
                )
            _set_cache("fund_list", funds, _LIST_TTL_SECONDS)
            enriched_count = sum(1 for f in funds if f.nav > 0)
            logger.info("Fund list loaded: %d total, %d enriched with real data", len(funds), enriched_count)
            return funds
        except Exception as exc:
            logger.warning("akshare fund_name_em failed: %s, using default snapshot", exc)
            default = _default_fund_list()
            _set_cache("fund_list", default, ttl=600)  # 失败时缓存回退列表 10 分钟，避免重复超时
            return default


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
            ("110020", "易方达沪深300ETF联接A", "易方达基金", "ETF联接", 1.2842, 1.24, 0.1284, "中高", "120.5亿", 92),
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
            ("510050", "华夏上证50ETF", "华夏基金", "ETF", 3.125, 1.15, 0.095, "高", "512.3亿", 82),
            ("159915", "易方达创业板ETF", "易方达基金", "ETF", 2.45, 0.85, 0.062, "高", "185.6亿", 78),
            ("000295", "华安科技动力混合", "华安基金", "混合型", 2.34, 0.55, 0.076, "中", "35.2亿", 62),
            ("519300", "大成沪深300增强", "大成基金", "股票型", 1.856, 0.92, 0.115, "中高", "45.8亿", 68),
        ]
    ]


def _simplify_type(raw: str) -> str:
    """把 akshare 的基金类型归一化为前端展示类型。
    检查顺序很重要：ETF联接必须在ETF之前检查，否则会被误判为ETF。
    """
    if "货币" in raw:
        return "货币型"
    if "债券" in raw:
        return "债券型"
    if "ETF联接" in raw or "ETF 联接" in raw:
        return "ETF联接"
    if "联接" in raw or "LOF" in raw:
        return "ETF联接"
    if "ETF" in raw:
        return "ETF"
    if "混合" in raw:
        return "混合型"
    if "股票" in raw:
        return "股票型"
    return "混合型"


def _is_etf_code(code: str) -> bool:
    """按代码前缀判断是否为场内 ETF（唯一真源，不依赖数据源的类型字段）。

    数据源（fund_name_em 等）常把场内 ETF 标为"股票型"，导致前端无法按
    type=ETF 进入 K 线逻辑。统一用代码前缀作为确定性判断。
        上海 ETF：51 / 56 / 58 开头
        深圳 ETF：15 / 16 开头
    六位代码才有效。
    """
    code = str(code).strip()
    if len(code) != 6:
        return False
    return code.startswith(("51", "56", "58", "15", "16"))


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
        df = _call_akshare(ak.fund_open_fund_info_em, symbol=code, indicator="单位净值走势", period="成立来")
        df = df.dropna(subset=["净值日期", "单位净值"])
        df["净值日期"] = pd.to_datetime(df["净值日期"])
        df = df.sort_values("净值日期").reset_index(drop=True)
        _set_cache(cache_key, df, ttl=3600)  # 1 小时，净值日内不变
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
        df = _call_akshare(ak.fund_etf_hist_sina, symbol=sina_sym)
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
                _set_cache(cache_key, df, ttl=7200)  # 2 小时
                return df
    except Exception as exc:
        logger.warning("sina etf history failed for %s: %s", code, exc)

    # ── 方案2: 东方财富数据源（备用）──
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = _call_akshare(
            ak.fund_etf_hist_em,
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
        _set_cache(cache_key, df, ttl=7200)  # 2 小时
        return df
    except Exception as exc:
        logger.warning("eastmoney etf history failed for %s: %s", code, exc)
        return empty_df


# -----------------------------------------------------------------------------
# Detail enrichment
# -----------------------------------------------------------------------------

# 常见基金公司简称 → 全称映射（从基金名称前缀提取公司名）
_FUND_COMPANY_PREFIXES: list[tuple[str, str]] = [
    ("易方达", "易方达基金"),
    ("华夏", "华夏基金"),
    ("南方", "南方基金"),
    ("嘉实", "嘉实基金"),
    ("博时", "博时基金"),
    ("广发", "广发基金"),
    ("富国", "富国基金"),
    ("招商", "招商基金"),
    ("天弘", "天弘基金"),
    ("工银瑞信", "工银瑞信基金"),
    ("华安", "华安基金"),
    ("华泰柏瑞", "华泰柏瑞基金"),
    ("国泰", "国泰基金"),
    ("中欧", "中欧基金"),
    ("景顺长城", "景顺长城基金"),
    ("鹏华", "鹏华基金"),
    ("汇添富", "汇添富基金"),
    ("兴证全球", "兴证全球基金"),
    ("交银施罗德", "交银施罗德基金"),
    ("银华", "银华基金"),
    ("万家", "万家基金"),
    ("前海开源", "前海开源基金"),
    ("建信", "建信基金"),
    ("农银汇理", "农银汇理基金"),
    ("民生加银", "民生加银基金"),
    ("长城", "长城基金"),
    ("国投瑞银", "国投瑞银基金"),
    ("中信保诚", "中信保诚基金"),
    ("申万菱信", "申万菱信基金"),
    ("信达澳亚", "信达澳亚基金"),
    ("中银", "中银基金"),
    ("中海", "中海基金"),
    ("上投摩根", "上投摩根基金"),
]


def _extract_company(name: str) -> str:
    """从基金名称中尝试提取基金公司。"""
    for prefix, full_name in _FUND_COMPANY_PREFIXES:
        if name.startswith(prefix):
            return full_name
    return "-"


def _fetch_basic_info(code: str) -> dict[str, str]:
    """从 akshare 获取基金基本信息（规模、成立日期、基金经理等）。

    优先使用东方财富 fund_individual_info_em（更稳定），
    失败时回退到雪球 fund_individual_basic_info_xq。
    """
    cache_key = f"basic:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    info: dict[str, str] = {}

    # 方案1: 东方财富数据源（列名更规范，无中文编码问题）
    try:
        df = _call_akshare(ak.fund_individual_info_em, symbol=code, timeout=5)
        if not df.empty:
            for _, row in df.iterrows():
                key = str(row.get("item", row.iloc[0])).strip()
                val = str(row.get("value", row.iloc[1])).strip()
                info[key] = val
            if info:
                _set_cache(cache_key, info)
                return info
    except Exception:
        pass

    # 方案2: 雪球数据源（备用）
    try:
        df = _call_akshare(ak.fund_individual_basic_info_xq, symbol=code, timeout=5)
        for _, row in df.iterrows():
            k = str(row.get("item", "")).strip()
            v = str(row.get("value", "")).strip()
            info[k] = v
    except Exception:
        pass

    _set_cache(cache_key, info)
    return info


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


# -----------------------------------------------------------------------------
# Real holdings & sectors (from quarterly reports)
# -----------------------------------------------------------------------------

_HOLDINGS_CACHE_TTL = 86400  # 24 小时（季报数据不常变）


def _fetch_real_holdings(code: str) -> list[TopHolding] | None:
    """从 akshare 获取基金最新季报的十大持仓。失败时返回 None。"""
    cache_key = f"holdings:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached if cached else None  # 空列表也缓存

    try:
        df = _call_akshare(ak.fund_portfolio_hold_em, symbol=code, date="2024")
        if df.empty:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        # 取最新季度的数据
        latest_quarter = df["季度"].iloc[0]
        qtr_df = df[df["季度"] == latest_quarter].head(10)

        holdings: list[TopHolding] = []
        for _, row in qtr_df.iterrows():
            holdings.append(
                TopHolding(
                    name=str(row.get("股票名称", "")).strip(),
                    code=str(row.get("股票代码", "")).strip() if pd.notna(row.get("股票代码")) else None,
                    weight=float(row.get("占净值比例", 0) or 0),
                    change_pct=0.0,  # 季报不含当日涨跌
                )
            )
        _set_cache(cache_key, holdings, _HOLDINGS_CACHE_TTL)
        return holdings if holdings else None
    except Exception as exc:
        logger.warning("Real holdings fetch failed for %s: %s", code, exc)
        _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
        return None


def _fetch_real_sectors(code: str) -> list[Sector] | None:
    """从 akshare 获取基金最新季报的行业配置。失败时返回 None。"""
    cache_key = f"sectors:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached if cached else None

    try:
        df = _call_akshare(ak.fund_portfolio_industry_allocation_em, symbol=code, date="2024")
        if df.empty:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        # 列名检测：akshare 返回 序号/行业名称/占净值比例/市值/截止时间
        name_col = None
        for candidate in ("行业名称", "行业", "名称", "行业类别"):
            if candidate in df.columns:
                name_col = candidate
                break

        weight_col = None
        for candidate in ("占净值比例", "比例", "占比", "比例(%)"):
            if candidate in df.columns:
                weight_col = candidate
                break

        if name_col is None or weight_col is None:
            logger.warning("Sector columns not found for %s, available: %s", code, list(df.columns))
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        colors = ["#171717", "#0071e3", "#6e6e73", "#00a550", "#ff9500",
                   "#ff3b30", "#af52de", "#34c759", "#5856d6", "#d1d1d6"]
        sectors: list[Sector] = []
        for i, (_, row) in enumerate(df.iterrows()):
            name = str(row[name_col]).strip()
            if not name or name == "nan":
                continue
            try:
                weight = float(row[weight_col])
            except (ValueError, TypeError):
                continue
            if weight <= 0:
                continue
            sectors.append(
                Sector(
                    name=name,
                    weight=weight,
                    color=colors[i % len(colors)],
                )
            )
        # Merge duplicate sector names (akshare may return same sector at different sub-levels)
        merged: dict[str, tuple[float, str]] = {}
        for s in sectors:
            if s.name in merged:
                prev_weight, prev_color = merged[s.name]
                merged[s.name] = (prev_weight + s.weight, prev_color)
            else:
                merged[s.name] = (s.weight, s.color)
        # 统一成百分比。部分数据源会返回小数（0.3996），也可能因为
        # 行业层级重复返回而导致合计大于 100%；两种情况都要在这里修正，
        # 不能把原始异常值直接展示给用户。
        total_weight = sum(weight for weight, _ in merged.values())
        if total_weight <= 0:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None
        multiplier = 100.0 if total_weight <= 1.05 else 1.0
        scale = (100.0 / total_weight) if total_weight > 100.5 else 1.0
        sectors = [
            Sector(name=name, weight=round(weight * multiplier * scale, 2), color=color)
            for name, (weight, color) in merged.items()
        ]
        sectors.sort(key=lambda s: s.weight, reverse=True)
        top = sectors[:10]
        remainder = round(100.0 - sum(s.weight for s in top), 2)
        if remainder > 0.05:
            other = next((sector for sector in top if sector.name == "其他"), None)
            if other is not None:
                other.weight = round(other.weight + remainder, 2)
            else:
                top.append(Sector(name="其他", weight=remainder, color=colors[9]))
        sectors = top
        _set_cache(cache_key, sectors, _HOLDINGS_CACHE_TTL)
        return sectors if sectors else None
    except Exception as exc:
        logger.warning("Real sectors fetch failed for %s: %s", code, exc)
        _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
        return None


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


_RANKINGS_LOCK = Lock()
_RANKINGS_RETRY_AT = 0.0
_OPEN_RANK_LOCK = Lock()


def _open_rank_frame() -> pd.DataFrame:
    # Share the slow source with startup enrichment. Keep the lock until the
    # actual request finishes: a timed-out wrapper cannot cancel its worker.
    with _OPEN_RANK_LOCK:
        cached = _get_cache("open_rank_frame")
        if cached is not None:
            return cached
        frame = ak.fund_open_fund_rank_em()
        if not frame.empty:
            _set_cache("open_rank_frame", frame, _LIST_TTL_SECONDS)
        return frame


def rankings(limit: int = 10) -> list[FundSummary]:
    """Serve a shared snapshot immediately while one worker refreshes it."""
    global _RANKINGS_RETRY_AT
    entry = _CACHE.get("rankings")  # Retain expired successful snapshots.
    snapshot = entry[0] if entry else sorted(
        _default_fund_list(), key=lambda f: f.one_year_return, reverse=True
    )
    if (entry is None or time.time() >= entry[1]) and time.monotonic() >= _RANKINGS_RETRY_AT:
        if _RANKINGS_LOCK.acquire(blocking=False):
            # Recheck after acquiring: another worker may have just finished.
            entry = _CACHE.get("rankings")
            if (entry is None or time.time() >= entry[1]) and time.monotonic() >= _RANKINGS_RETRY_AT:
                try:
                    Thread(target=_refresh_rankings, name="fund-rankings-refresh", daemon=True).start()
                except Exception:
                    _RANKINGS_LOCK.release()
                    raise
            else:
                _RANKINGS_LOCK.release()
    return snapshot[:limit]


def _refresh_rankings() -> None:
    global _RANKINGS_RETRY_AT
    try:
        fresh = _fetch_rankings()
        if fresh:
            _set_cache("rankings", fresh, _LIST_TTL_SECONDS)
    except Exception:
        logger.warning("Rankings refresh failed; retaining snapshot", exc_info=True)
    finally:
        _RANKINGS_RETRY_AT = time.monotonic() + 60
        _RANKINGS_LOCK.release()


def _fetch_rankings() -> list[FundSummary]:
    # Run on the single daemon worker, without orphaned timeout threads.
    frames = []
    for fetch in (_open_rank_frame, ak.fund_exchange_rank_em):
        try:
            frames.append(fetch())
        except Exception as exc:
            logger.warning("Rankings source failed: %s", exc)
    open_df, etf_df = (frames + [pd.DataFrame(), pd.DataFrame()])[:2]
    results: list[FundSummary] = []
    for df in (open_df, etf_df):
        if df.empty:
            continue
        for _, row in df.iterrows():
            code = str(row.get("基金代码", "")).strip()
            name = str(row.get("基金简称", "")).strip()
            raw_type = str(row.get("类型", "")).strip() if "类型" in df.columns else ""
            ftype = _simplify_type(raw_type) if raw_type else ("ETF" if _is_etf_code(code) else "混合型")
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
    return unique


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

    # 1. 从基金列表获取基金名称和类型
    funds = _load_fund_list()
    summary = next((f for f in funds if f.code == upper), None)

    if summary is None:
        # 基金不在缓存列表中（可能是 akshare 不可用导致默认列表不完整）。
        # 尝试直接从 akshare 获取 NAV 数据来构建基本信息。
        name = f"基金{upper}"
        ftype = "混合型"  # 保守默认
        company = "-"
        enrichment = {}
        summary_nav = 1.0
        summary_one_year = 0.0
        # 尝试从 enrichment cache 中查找
        try:
            enrich = _build_enrichment_lookup()
            if upper in enrich:
                enrichment = enrich[upper]
        except Exception:
            pass
    else:
        name = summary.name
        ftype = summary.type
        company = _extract_company(name)
        enrichment = {}
        summary_nav = summary.nav if summary.nav > 0 else 1.0
        summary_one_year = summary.one_year_return

    # 2. 判断是否 ETF 并获取历史净值
    #    统一以代码前缀为唯一真源（不依赖数据源类型字段，数据源可能误标）。
    is_etf = _is_etf_code(upper)
    if is_etf:
        ftype = "ETF"  # 覆盖类型，确保前端能进入 K 线逻辑

    # 3. 并行获取净值历史、真实持仓、行业分布、基本信息。
    #    四者互不依赖，串行会放大 akshare 慢网络下的等待时间；并行后整体
    #    耗时趋近最慢的一个请求（各请求内部已带超时与缓存，失败会回退默认值）。
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _f_nav = (
            _ex.submit(_fetch_etf_history, upper)
            if is_etf
            else _ex.submit(_fetch_nav_history, upper)
        )
        _f_sectors = _ex.submit(_fetch_real_sectors, upper)
        _f_holdings = _ex.submit(_fetch_real_holdings, upper)
        _f_basic = _ex.submit(_fetch_basic_info, upper)
        nav_df = _f_nav.result()
        sectors_raw = _f_sectors.result()
        holdings_raw = _f_holdings.result()
        basic_info = _f_basic.result()

    # 4. 计算当前净值与涨跌幅（基于真实净值数据）
    if not nav_df.empty:
        latest_nav = float(nav_df["单位净值"].iloc[-1])
        if len(nav_df) >= 2:
            prev_nav = float(nav_df["单位净值"].iloc[-2])
            change_pct = (latest_nav - prev_nav) / prev_nav * 100
        else:
            change_pct = 0.0
    else:
        latest_nav = enrichment.get("nav", summary_nav)
        change_pct = enrichment.get("change_pct", 0.0)

    returns = _returns_from_nav(nav_df) if not nav_df.empty else FundReturns(
        daily=0.0, weekly=0.0, monthly=0.0, yearly=enrichment.get("one_year_return", summary_one_year)
    )
    metrics = _metrics_from_nav(nav_df, ftype)

    # 5. 真实持仓与行业分布（季报数据），失败时回退到类型默认值
    sectors = sectors_raw or _default_sectors(ftype)
    top_holdings = holdings_raw or _default_top_holdings(ftype)
    fund_size = basic_info.get("基金规模", basic_info.get("规模", basic_info.get("资产规模", "-")))
    if fund_size in ("", "nan", "<NA>", "None"):
        fund_size = "-"
    inception = basic_info.get("成立日期", basic_info.get("成立时间", basic_info.get("成 立 日", "暂无数据")))
    if inception in ("", "nan", "<NA>", "None"):
        inception = "暂无数据"
    else:
        inception = inception[:10] if len(inception) >= 10 else inception
    manager = basic_info.get("基金经理", basic_info.get("基金经理人", basic_info.get("现任基金经理", "暂无数据")))
    if manager in ("", "nan", "<NA>", "None"):
        manager = "暂无数据"
    # 基金评级（如果数据源提供）
    rating_str = basic_info.get("评级", basic_info.get("基金评级", ""))
    try:
        rating = int(float(rating_str)) if rating_str and rating_str not in ("nan", "<NA>") else 1
        rating = max(1, min(5, rating))
    except (ValueError, TypeError):
        rating = 1

    return FundDetail(
        code=upper,
        name=name,
        company=company,
        type=ftype,
        nav=round(latest_nav, 4),
        change_pct=round(change_pct, 2),
        one_year_return=round(returns.yearly, 4),
        risk_level=metrics.risk_level,
        size=fund_size,
        heat=_heat_score(name, ftype),
        inception_date=inception,
        returns=returns,
        metrics=metrics,
        sectors=sectors,
        tags=_tags_for(name, ftype),
        description=f"{name}是一只{ftype}基金。" if summary is None else f"{name}是一只{ftype}基金。",
        manager=manager,
        rating=rating,
        top_holdings=top_holdings,
        investment_style=_style_for_type(ftype),
    )


def nav_history(code: str) -> pd.DataFrame:
    """返回该基金可用的历史净值/价格 DataFrame。

    通过代码前缀直接判断 ETF/非 ETF（与 market_service.kline 一致），
    避免为确定类型而触发一次完整的 get_by_code()（含重仓/行业/基本信息
    等多重 akshare 调用）。
    """
    upper = code.strip().upper()
    if upper.startswith(("51", "15", "56", "58", "16")) and len(upper) == 6:
        return _fetch_etf_history(upper)
    return _fetch_nav_history(upper)
