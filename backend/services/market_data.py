"""统一行情 Provider、显式降级和跨源核验。

只处理指数与 ETF 二级市场行情，不把成交价当成基金累计净值。
iFinD 的服务端传输实现必须由部署方依据官方文档注入；当前会话插件通道
不是项目后端凭据，不能在运行时代用。没有开关、凭据或传输实现时返回
Blocked，并由调用方披露真实降级来源。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Protocol

import pandas as pd

from models.market import NavPeriod
from services import fund_service, market_service

OHLC_COLUMNS = ["open", "high", "low", "close"]
INDEX_CODES = {
    "000001.SH": "sh000001",
    "399001.SZ": "sz399001",
    "000300.SH": "sh000300",
    "399006.SZ": "sz399006",
    "000905.SH": "sh000905",
}
IFIND_FUND_NAV_DETAIL = (
    "当前服务端 Adapter 只定义指数与 ETF 日线能力；尚未取得并验证基金累计净值、"
    "分红及复权接口，基金累计净值接入保持 Blocked。现有基金净值仍使用原数据源。"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PriceHistory:
    ticker: str
    provider: str
    source: str
    status: str
    frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    note: str = ""
    fallback_from: str | None = None
    generated_at: datetime = field(default_factory=utc_now)


class MarketDataProvider(Protocol):
    name: str
    label: str

    def status(self) -> dict: ...

    def daily_history(self, ticker: str, start: date, end: date) -> PriceHistory: ...


def normalize_price_frame(raw: pd.DataFrame, ticker: str, start: date, end: date) -> pd.DataFrame:
    """规范化真实 OHLCV；不插值、不前向填充、不生成缺失交易日。"""
    columns = ["净值日期", *OHLC_COLUMNS, "volume", "turnover"]
    if raw is None or raw.empty:
        return pd.DataFrame(columns=columns)
    frame = raw.copy().rename(
        columns={
            "time": "净值日期",
            "date": "净值日期",
            "日期": "净值日期",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "amount": "turnover",
            "成交额": "turnover",
            "成交金额": "turnover",
        }
    )
    if "thscode" in frame.columns:
        frame = frame[frame["thscode"].astype(str).str.upper() == ticker.upper()]
    if "净值日期" not in frame.columns or not set(OHLC_COLUMNS).issubset(frame.columns):
        return pd.DataFrame(columns=columns)
    frame["净值日期"] = pd.to_datetime(frame["净值日期"], errors="coerce")
    for column in (*OHLC_COLUMNS, "volume", "turnover"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["净值日期", *OHLC_COLUMNS])
    frame = frame[(frame[OHLC_COLUMNS] > 0).all(axis=1)]
    frame = frame.drop_duplicates(subset=["净值日期"], keep="last").sort_values("净值日期")
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    frame = frame[(frame["净值日期"] >= start_ts) & (frame["净值日期"] <= end_ts)]
    for column in ("volume", "turnover"):
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[columns].reset_index(drop=True)


class AkshareMarketDataProvider:
    name = "akshare"
    label = "现有 AkShare 行情源"

    def status(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "status": "available",
            "enabled": True,
            "capabilities": ["index_daily", "etf_daily", "cross_validation_primary"],
            "detail": "保留原有指数与 ETF 行情链路；单次请求失败不代表 Provider 被移除。",
        }

    def daily_history(self, ticker: str, start: date, end: date) -> PriceHistory:
        ticker = ticker.strip().upper()
        source = "指数历史行情（经 akshare 获取）"
        try:
            if ticker in INDEX_CODES:
                points = market_service.index_kline(INDEX_CODES[ticker], NavPeriod.DAILY)
                raw = pd.DataFrame(
                    [
                        {
                            "净值日期": point.date,
                            "open": point.open,
                            "high": point.high,
                            "low": point.low,
                            "close": point.close,
                            "volume": point.volume,
                            "turnover": point.turnover,
                        }
                        for point in points
                    ]
                )
            else:
                code, separator, suffix = ticker.partition(".")
                if not separator or suffix not in {"SH", "SZ"} or not fund_service._is_etf_code(code):
                    return PriceHistory(
                        ticker, self.name, source, "unsupported",
                        note="该代码不在已验证的指数或 ETF 名录中，未猜测证券身份。",
                    )
                source = "ETF 二级市场行情（经 akshare 获取）"
                days = max(365, (date.today() - start).days + 30)
                raw = fund_service._fetch_etf_price_history(code, days=days)
        except Exception as exc:
            return PriceHistory(
                ticker, self.name, source, "unavailable",
                note=f"现有行情源请求失败（{type(exc).__name__}）；未生成替代行情。",
            )
        frame = normalize_price_frame(raw, ticker, start, end)
        return PriceHistory(
            ticker,
            self.name,
            source,
            "available" if not frame.empty else "unavailable",
            frame,
            "按真实日期返回，未插值或前向填充。" if not frame.empty else "所选区间没有可用真实行情。",
        )


IFindTransport = Callable[[str, date, date, str], pd.DataFrame]


class IFindMarketDataProvider:
    name = "ifind"
    label = "同花顺 iFinD 服务端 Adapter"

    def __init__(self, transport: IFindTransport | None = None):
        # transport 是部署方按官方文档实现的服务端扩展点；不内置猜测的 URL 或协议。
        self.transport = transport

    @staticmethod
    def _enabled() -> bool:
        return os.getenv("IFIND_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}

    def status(self) -> dict:
        enabled = self._enabled()
        credential_present = bool(os.getenv("IFIND_ACCESS_TOKEN", "").strip())
        if not enabled:
            status, detail = "blocked", "功能开关 IFIND_ENABLED 未启用；当前使用现有行情源。"
        elif not credential_present:
            status, detail = "blocked", "功能开关已启用，但服务端缺少 IFIND_ACCESS_TOKEN；凭据未写入代码或前端。"
        elif self.transport is None:
            status, detail = "blocked", "凭据已配置，但尚未注入经官方文档验证的服务端传输实现；不会猜测接口地址。"
        else:
            status, detail = "available", "服务端开关、凭据和传输实现均已配置；仅限指数与 ETF 日线。"
        return {
            "name": self.name,
            "label": self.label,
            "status": status,
            "enabled": enabled,
            "capabilities": ["index_daily", "etf_daily", "cross_validation_secondary"],
            "detail": detail,
        }

    def daily_history(self, ticker: str, start: date, end: date) -> PriceHistory:
        ticker = ticker.strip().upper()
        source = "指数或 ETF 日线（iFinD 服务端 Adapter）"
        state = self.status()
        if state["status"] != "available":
            return PriceHistory(ticker, self.name, source, "blocked", note=state["detail"])
        try:
            token = os.getenv("IFIND_ACCESS_TOKEN", "").strip()
            raw = self.transport(ticker, start, end, token)  # type: ignore[misc]
        except Exception as exc:
            # 异常可能含请求头；只记录异常类型，绝不把响应、URL 或凭据写入日志/响应。
            return PriceHistory(
                ticker, self.name, source, "unavailable",
                note=f"iFinD 请求失败（{type(exc).__name__}）；未输出凭据或生成替代数据。",
            )
        frame = normalize_price_frame(raw, ticker, start, end)
        return PriceHistory(
            ticker,
            self.name,
            source,
            "available" if not frame.empty else "unavailable",
            frame,
            "iFinD 真实日线；按共同日期参与核验，不插值。" if not frame.empty else "iFinD 在所选区间未返回有效 OHLC。",
        )


def history_with_fallback(ticker: str, start: date, end: date) -> PriceHistory:
    """iFinD 优先；任何不可用都显式降级，来源字段只写实际提供者。"""
    ifind = IFindMarketDataProvider()
    enhanced = ifind.daily_history(ticker, start, end)
    if enhanced.status == "available":
        return enhanced
    primary = AkshareMarketDataProvider().daily_history(ticker, start, end)
    primary.fallback_from = "ifind"
    primary.note = f"iFinD 未用于本次数据（{enhanced.status}）：{enhanced.note} 实际来源：{primary.source}。{primary.note}"
    return primary


def provider_registry_status() -> dict:
    ifind = IFindMarketDataProvider().status()
    return {
        "active_provider": "ifind" if ifind["status"] == "available" else "akshare",
        "providers": [AkshareMarketDataProvider().status(), ifind],
        "fund_accumulated_nav_status": "blocked",
        "fund_accumulated_nav_detail": IFIND_FUND_NAV_DETAIL,
        "generated_at": utc_now(),
    }


def compare_history(primary: PriceHistory, secondary: PriceHistory) -> dict:
    """按真实共同日期比较收盘价；缺失日期只披露，绝不补齐。"""
    generated_at = utc_now()
    base = {
        "ticker": primary.ticker,
        "primary_source": primary.source,
        "secondary_source": secondary.source,
        "matched_samples": 0,
        "primary_only_dates": 0,
        "secondary_only_dates": 0,
        "max_difference_pct": None,
        "differences": [],
        "generated_at": generated_at,
    }
    if primary.status != "available" or secondary.status != "available":
        return {
            **base,
            "status": "blocked",
            "note": f"跨源核验未执行：主源 {primary.status}，核验源 {secondary.status}。{secondary.note}",
        }

    left = primary.frame.set_index("净值日期")
    right = secondary.frame.set_index("净值日期")
    joined = left[["close"]].join(right[["close"]], how="inner", suffixes=("_primary", "_secondary")).dropna()
    left_dates, right_dates = set(left.index), set(right.index)
    rows: list[dict] = []
    for day, row in joined.iterrows():
        first, second = float(row["close_primary"]), float(row["close_secondary"])
        difference = second - first
        difference_pct = abs(difference) / first
        status = "abnormal" if difference_pct >= 0.02 else "warning" if difference_pct >= 0.005 else "normal"
        rows.append(
            {
                "date": day.date().isoformat(),
                "primary_close": round(first, 6),
                "secondary_close": round(second, 6),
                "difference": round(difference, 6),
                "difference_pct": round(difference_pct, 8),
                "status": status,
            }
        )
    rows.sort(key=lambda item: item["difference_pct"], reverse=True)
    max_difference = max((item["difference_pct"] for item in rows), default=None)
    overall = "normal"
    if any(item["status"] == "abnormal" for item in rows):
        overall = "abnormal"
    elif any(item["status"] == "warning" for item in rows):
        overall = "warning"
    if joined.empty:
        overall = "missing"
    return {
        **base,
        "status": overall,
        "matched_samples": len(joined),
        "primary_only_dates": len(left_dates - right_dates),
        "secondary_only_dates": len(right_dates - left_dates),
        "max_difference_pct": max_difference,
        "differences": rows[:20],
        "note": "按共同日期比较未复权/同一口径收盘价；差异达到 0.5% 为警告、2% 为异常，只作为复核线索。最多列示差异最大的 20 条。",
    }


def cross_source_check(ticker: str, start: date, end: date) -> dict:
    primary = history_with_fallback(ticker, start, end)
    secondary = IFindMarketDataProvider().daily_history(ticker, start, end)
    return {
        "ticker": ticker.upper(),
        "start_date": start,
        "end_date": end,
        **compare_history(primary, secondary),
    }
