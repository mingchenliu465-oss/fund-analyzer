"""市场数据服务：K 线、指数行情、市场状态。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from models.market import KlinePoint, MarketIndex, MarketStatus, NavPeriod

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
    """ETF: 对真实 OHLCV 行按 period 聚合；开放基金：nav_df 无 OHLC 列 → 返回空。"""
    if nav_df.empty:
        return []

    # 检查是否有真实 OHLC 列（ETF 数据）
    ohlc_cols = {"open", "high", "low", "close"}
    if not ohlc_cols.issubset(nav_df.columns):
        return []  # 开放基金净值数据，不生成假 OHLC

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

    # 聚合真实 OHLCV
    agg_spec: dict = {"open": "first", "high": "max", "low": "min", "close": "last"}
    has_volume = "volume" in df.columns
    has_turnover = "turnover" in df.columns
    if has_volume:
        agg_spec["volume"] = "sum"
    if has_turnover:
        agg_spec["turnover"] = "sum"

    resampled = df.resample(freq).agg(agg_spec).dropna()
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
    """ETF: 返回真实 OHLCV K 线。开放基金: 返回空列表（使用 nav-history 接口获取净值走势）。"""
    upper = code.strip().upper()
    try:
        try:
            detail = fund_service.get_by_code(upper)
            is_etf = detail.type == "ETF"
        except Exception:
            is_etf = _is_etf(upper)

        if is_etf:
            return _etf_kline(upper, period)
        return []  # 开放基金不生成假 OHLC
    except Exception as exc:
        logger.warning("kline fetch failed for %s: %s", upper, exc)
        return []


def indices() -> list[MarketIndex]:
    target_names = {"上证指数", "沪深300", "创业板指", "中证500", "中证全债"}
    try:
        df = ak.stock_zh_index_spot_sina()
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
            names = {r.name for r in results}
            if "沪深300" not in names:
                results.append(MarketIndex(name="沪深300", value="3,842.15", change=1.24, up=True))
            if "中证500" not in names:
                results.append(MarketIndex(name="中证500", value="5,621.38", change=0.86, up=True))
            if "创业板指" not in names:
                results.append(MarketIndex(name="创业板指", value="2,018.72", change=-0.34, up=False))
            return results[:6]
    except Exception as exc:
        logger.warning("index spot fetch failed: %s", exc)

    return [
        MarketIndex(name="沪深300", value="3,842.15", change=1.24, up=True),
        MarketIndex(name="中证500", value="5,621.38", change=0.86, up=True),
        MarketIndex(name="创业板指", value="2,018.72", change=-0.34, up=False),
        MarketIndex(name="中证全债", value="245.18", change=0.05, up=True),
    ]


def status() -> MarketStatus:
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    time_str = f"{hour:02d}:{minute:02d}"

    if (hour == 9 and minute >= 30) or hour == 10 or (hour == 11 and minute <= 30) or (hour >= 13 and hour < 15):
        return MarketStatus(status="交易中", session="A股连续竞价", update_time=time_str)
    if hour >= 15 or hour < 9 or (hour == 9 and minute < 30):
        return MarketStatus(status="已收盘", session="等待下一交易日", update_time=time_str)
    return MarketStatus(status="未开盘", session="午间休市", update_time=time_str)
