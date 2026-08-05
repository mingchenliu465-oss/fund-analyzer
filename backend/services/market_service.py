"""市场数据服务：K 线、指数行情、市场状态。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from models.market import KlinePoint, MarketIndex, MarketStatus, NavPeriod
from services.fund_service import _call_akshare, _get_cache, _set_cache

logger = logging.getLogger(__name__)


def _period_to_days(period: NavPeriod) -> int:
    return {
        NavPeriod.FIVE_DAY: 7,
        NavPeriod.TEN_DAY: 14,
        NavPeriod.TWENTY_DAY: 30,
        NavPeriod.DAILY: 60,
        NavPeriod.WEEKLY: 180,
        NavPeriod.MONTHLY: 730,
        NavPeriod.YEARLY: 1825,
        NavPeriod.ONE_MONTH: 30,
        NavPeriod.THREE_MONTH: 90,
        NavPeriod.SIX_MONTH: 180,
        NavPeriod.ONE_YEAR: 365,
        NavPeriod.THREE_YEAR: 1095,
    }[period]


def _is_etf(code: str) -> bool:
    code = code.strip()
    return code.startswith(("51", "15", "56", "58", "16")) and len(code) == 6


def _format_date(dt: datetime, period: NavPeriod) -> str:
    if period in (NavPeriod.MONTHLY, NavPeriod.YEARLY, NavPeriod.ONE_YEAR, NavPeriod.THREE_YEAR):
        return dt.strftime("%Y-%m")
    return dt.strftime("%Y-%m-%d")


def _resample_to_kline(nav_df: pd.DataFrame, period: NavPeriod) -> list[KlinePoint]:
    """将净值/OHLCV 数据转为 K线点。

    ETF：有真实 OHLCV 列，按 period 聚合。
    开放基金：仅有单位净值列，生成伪 K 线（open≈close≈nav，无成交量），
    前端 K 线图会正常渲染为走势线。
    """
    if nav_df.empty:
        return []

    df = nav_df.copy()
    df["净值日期"] = pd.to_datetime(df["净值日期"])
    df = df.set_index("净值日期").sort_index()

    freq_map = {
        NavPeriod.FIVE_DAY: "D",
        NavPeriod.TEN_DAY: "D",
        NavPeriod.TWENTY_DAY: "D",
        NavPeriod.DAILY: "D",
        NavPeriod.WEEKLY: "W",
        NavPeriod.MONTHLY: "ME",
        NavPeriod.YEARLY: "YE",
        NavPeriod.ONE_MONTH: "D",
        NavPeriod.THREE_MONTH: "W",
        NavPeriod.SIX_MONTH: "W",
        NavPeriod.ONE_YEAR: "ME",
        NavPeriod.THREE_YEAR: "QE",
    }
    freq = freq_map[period]

    has_ohlc = {"open", "high", "low", "close"}.issubset(df.columns)

    if has_ohlc:
        # ETF: 聚合真实 OHLCV
        agg_spec: dict = {"open": "first", "high": "max", "low": "min", "close": "last"}
        has_volume = "volume" in df.columns
        has_turnover = "turnover" in df.columns
        if has_volume:
            agg_spec["volume"] = "sum"
        if has_turnover:
            agg_spec["turnover"] = "sum"
        resampled = df.resample(freq).agg(agg_spec).dropna()
    else:
        # 开放基金: 基于单位净值生成伪 OHLC（走势线模式）
        nav_series = df["单位净值"].astype(float)
        resampled = nav_series.resample(freq).ohlc()
        resampled["volume"] = 0.0
        resampled["turnover"] = 0.0
        resampled = resampled.dropna()
        has_volume = True
        has_turnover = True

    points: list[KlinePoint] = []
    for dt, row in resampled.iterrows():
        points.append(
            KlinePoint(
                date=_format_date(dt, period),
                open=round(float(row["open"]), 4),
                high=round(float(row["high"]), 4),
                low=round(float(row["low"]), 4),
                close=round(float(row["close"]), 4),
                volume=round(float(row["volume"]), 0) if has_volume and pd.notna(row.get("volume")) else None,
                turnover=round(float(row["turnover"]), 2) if has_turnover and pd.notna(row.get("turnover")) else None,
            )
        )
    return points


def _etf_kline(code: str, period: NavPeriod) -> list[KlinePoint]:
    from services import fund_service

    days = _period_to_days(period)
    df = fund_service._fetch_etf_history(code, days=days)
    return _resample_to_kline(df, period)


def kline(code: str, period: NavPeriod = NavPeriod.DAILY) -> list[KlinePoint]:
    """返回基金的 K 线数据。

    ETF: 真实 OHLCV 数据（含成交量）。
    开放基金: 基于净值的伪 K 线（走势线模式，无成交量），前端正常渲染。

    通过代码前缀判断 ETF/非 ETF，不触发 get_by_code() 避免冗余 akshare 调用。
    """
    from services import fund_service

    upper = code.strip().upper()

    # 通过代码前缀直接判断是否 ETF，无需调 get_by_code()
    if _is_etf(upper):
        return _etf_kline(upper, period)

    # 开放基金: 获取净值历史，转为 K 线格式
    try:
        nav_df = fund_service._fetch_nav_history(upper)
        days = _period_to_days(period)
        cutoff = datetime.now() - timedelta(days=days)
        nav_df = nav_df[nav_df["净值日期"] >= cutoff]
        return _resample_to_kline(nav_df, period)
    except Exception as exc:
        logger.warning("kline fetch failed for %s: %s", upper, exc)
        return []


def indices() -> list[MarketIndex]:
    # 市场指数缓存 2 分钟（盘中可能微调，但避免每次都请求）
    cache_key = "market_indices"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    target_names = {"上证指数", "沪深300", "创业板指", "中证500", "中证全债"}
    try:
        df = _call_akshare(ak.stock_zh_index_spot_sina, timeout=6)
        df = df.rename(
            columns={
                "代码": "code",
                "名称": "name",
                "最新价": "price",
                "涨跌幅": "change_pct",
            }
        )
        results: list[MarketIndex] = []
        for _, row in df.iterrows():
            name = str(row["name"])
            if name not in target_names and name not in {"深证成指", "科创50", "上证50"}:
                continue
            price = float(row["price"]) if pd.notna(row["price"]) else 0.0
            change = float(row["change_pct"]) if pd.notna(row["change_pct"]) else 0.0
            results.append(
                MarketIndex(
                    name=name,
                    value=f"{price:,.2f}",
                    change=round(change, 2),
                    up=change >= 0,
                )
            )
        if results:
            _set_cache(cache_key, results, ttl=120)  # 2 分钟缓存
            return results
    except Exception as exc:
        logger.warning("indices fetch failed: %s", exc)

    # 数据源暂时不可用，返回空（不伪造数据）
    _set_cache(cache_key, [], ttl=120)  # 失败时也缓存空结果，避免频繁重试
    return []


def status() -> MarketStatus:
    now = datetime.now()
    current = now.time()

    morning_start = current.replace(hour=9, minute=30, second=0)
    morning_end = current.replace(hour=11, minute=30, second=0)
    afternoon_start = current.replace(hour=13, minute=0, second=0)
    afternoon_end = current.replace(hour=15, minute=0, second=0)

    if morning_start <= current <= morning_end or afternoon_start <= current <= afternoon_end:
        status_str = "交易中"
        session = "continuous"
    elif current < morning_start:
        status_str = "未开盘"
        session = "pre"
    elif morning_end < current < afternoon_start:
        status_str = "午间休市"
        session = "lunch"
    else:
        status_str = "已收盘"
        session = "post"

    return MarketStatus(
        status=status_str,
        session=session,
        update_time=now.strftime("%H:%M:%S"),
    )
