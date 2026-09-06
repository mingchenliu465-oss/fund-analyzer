"""市场数据服务：K 线、指数行情、市场状态。"""

from __future__ import annotations

import logging
import time
import time
from datetime import datetime, timedelta
from threading import Lock, Thread

import akshare as ak
import pandas as pd

from models.market import KlinePoint, MarketIndex, MarketStatus, NavPeriod
from services.fund_service import _CACHE, _call_akshare, _get_cache, _set_cache

logger = logging.getLogger(__name__)


# 首页展示的主要宽基指数。代码沿用 AkShare/Sina 的市场前缀格式，既可
# 作为稳定路由参数，也可直接用于 stock_zh_index_daily 拉取历史行情。
_DEFAULT_INDEX_CODES = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "沪深300": "sh000300",
    "创业板指": "sz399006",
    "中证500": "sh000905",
    "中证全债": "H11001",
}

_DEFAULT_INDICES = [
    MarketIndex(code="sh000001", name="上证指数", value="3,250.00", change=0.0, up=True),
    MarketIndex(code="sz399001", name="深证成指", value="10,500.00", change=0.0, up=True),
    MarketIndex(code="sh000300", name="沪深300", value="3,900.00", change=0.0, up=True),
    MarketIndex(code="sz399006", name="创业板指", value="2,050.00", change=0.0, up=True),
    MarketIndex(code="sh000905", name="中证500", value="5,700.00", change=0.0, up=True),
    MarketIndex(code="H11001", name="中证全债", value="248.00", change=0.0, up=True),
]

_INDICES_REFRESH_LOCK = Lock()
_INDICES_RETRY_AT = 0.0


def _is_index(code: str) -> bool:
    return code.strip().lower() in {item.lower() for item in _DEFAULT_INDEX_CODES.values()}


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


# 场内 ETF 全量历史窗口（天）：约 15 年，覆盖绝大多数场内 ETF 全部历史。
# kline 返回全量数据，时间范围由前端"初始可视窗口"控制，缩小图表即可看到更早历史。
_ETF_FULL_DAYS = 5475


def _etf_kline(code: str, period: NavPeriod) -> list[KlinePoint]:
    from services import fund_service

    df = fund_service._fetch_etf_history(code, days=_ETF_FULL_DAYS)
    return _resample_to_kline(df, period)


def _index_kline(code: str, period: NavPeriod) -> list[KlinePoint]:
    """获取指数真实 OHLCV 历史并按日/周/月周期聚合。

    新浪接口覆盖首页所列沪深指数；东方财富作为备用数据源，并为中证
    系列代码做 csi 前缀转换。两者都不可用时返回空列表，由前端明确展示
    “历史行情暂不可用”，避免把指数误当作开放式基金或伪造走势。
    """
    symbol = code.strip().lower()
    cache_key = f"index_kline:{symbol}:{period.value}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    if symbol == "h11001":
        df = _fetch_bond_index_history()
    else:
        df = pd.DataFrame()
        try:
            df = _call_akshare(
                ak.stock_zh_index_daily_em,
                symbol=symbol,
                start_date="19900101",
                end_date="20500101",
                timeout=10,
            )
        except Exception as exc:
            logger.warning("eastmoney index history failed for %s: %s", symbol, exc)

        if df.empty:
            try:
                df = _call_akshare(ak.stock_zh_index_daily, symbol=symbol, timeout=10)
            except Exception as exc:
                logger.warning("sina index history failed for %s: %s", symbol, exc)

    if df.empty:
        _set_cache(cache_key, [], ttl=120)
        return []

    df = df.rename(
        columns={
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
    required = {"净值日期", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        logger.warning("index history columns incomplete for %s: %s", symbol, list(df.columns))
        _set_cache(cache_key, [], ttl=120)
        return []

    for column in ("open", "high", "low", "close", "volume", "turnover"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["净值日期"] = pd.to_datetime(df["净值日期"], errors="coerce")
    df = df.dropna(subset=["净值日期", "open", "high", "low", "close"])

    points = _resample_to_kline(df, period)
    _set_cache(cache_key, points, ttl=300)
    return points


def _fetch_bond_index_history() -> pd.DataFrame:
    """获取中证全债 H11001 历史并规范化为统一 OHLC 字段。"""
    cache_key = "index_history:H11001"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached.copy()

    end = datetime.now()
    start = end - timedelta(days=_ETF_FULL_DAYS)
    try:
        df = _call_akshare(
            ak.stock_zh_index_hist_csindex,
            symbol="H11001",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            timeout=12,
        )
    except Exception as exc:
        logger.warning("csindex bond history failed for H11001: %s", exc)
        return pd.DataFrame()

    if df.empty:
        return df

    df = df.rename(
        columns={
            "日期": "净值日期",
            "收盘": "close",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "涨跌幅": "change_pct",
            "成交量": "volume",
            "成交金额": "turnover",
        }
    )
    df["净值日期"] = pd.to_datetime(df["净值日期"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    for column in ("open", "high", "low"):
        if column not in df.columns:
            df[column] = df["close"]
        else:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(df["close"])
    for column in ("change_pct", "volume", "turnover"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["净值日期", "close"]).sort_values("净值日期").reset_index(drop=True)
    _set_cache(cache_key, df, ttl=600)
    return df.copy()


def index_kline(code: str, period: NavPeriod = NavPeriod.DAILY) -> list[KlinePoint]:
    """指数专用历史接口，显式校验代码，避免与六位基金代码混淆。"""
    if not _is_index(code):
        return []
    return _index_kline(code, period)


def kline(
    code: str,
    period: NavPeriod = NavPeriod.DAILY,
    range_: str = "1Y",
) -> list[KlinePoint]:
    """返回基金的 K 线/净值走势数据（返回全量历史）。

    - period：聚合粒度（日K/周K/月K，也向后兼容 1M/3M/1Y 等旧值）
    - range_：保留参数（向后兼容），后端不再用它截断；时间范围由前端
      "初始可视窗口"控制，用户缩小图表即可看到更早历史（修复缩放问题）。

    ETF: 真实 OHLCV 数据（含成交量）。
    开放基金: 基于净值重采样的折线点（open≈high≈low≈close≈nav，无成交量），
              前端应按"净值走势"（折线/面积）渲染，而非实体 K 线。

    通过代码前缀判断 ETF/非 ETF，不触发 get_by_code() 避免冗余 akshare 调用。
    """
    from services import fund_service

    upper = code.strip().upper()

    # 指数代码带市场前缀（sh/sz）；先于 ETF/开放基金判断，避免误走基金净值接口。
    if _is_index(code):
        return _index_kline(code, period)

    # 通过代码前缀直接判断是否 ETF，无需调 get_by_code()
    if _is_etf(upper):
        return _etf_kline(upper, period)

    # 开放基金: 获取全量净值历史，按周期聚合为折线点
    try:
        nav_df = fund_service._fetch_nav_history(upper)
        return _resample_to_kline(nav_df, period)
    except Exception as exc:
        logger.warning("kline fetch failed for %s: %s", upper, exc)
        return []


def _fetch_indices() -> list[MarketIndex]:
    """同步获取真实指数行情；仅在后台刷新线程中调用。"""
    target_names = {"上证指数", "深证成指", "沪深300", "创业板指", "中证500"}
    try:
        df = _call_akshare(ak.stock_zh_index_spot_sina, timeout=12)
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
            if name not in target_names:
                continue
            price = float(row["price"]) if pd.notna(row["price"]) else 0.0
            change = float(row["change_pct"]) if pd.notna(row["change_pct"]) else 0.0
            results.append(
                MarketIndex(
                    code=_DEFAULT_INDEX_CODES.get(name, str(row.get("code", "")).strip()),
                    name=name,
                    value=f"{price:,.2f}",
                    change=round(change, 2),
                    up=change >= 0,
                )
            )
        # 新浪快照不包含中证全债，使用中证官网 H11001 最近交易日补齐。
        try:
            bond_df = _fetch_bond_index_history()
            if not bond_df.empty:
                latest = bond_df.iloc[-1]
                latest_close = float(latest["close"])
                if pd.notna(latest.get("change_pct")):
                    bond_change = float(latest["change_pct"])
                elif len(bond_df) >= 2 and float(bond_df.iloc[-2]["close"]) != 0:
                    bond_change = (latest_close / float(bond_df.iloc[-2]["close"]) - 1) * 100
                else:
                    bond_change = 0.0
                results.append(
                    MarketIndex(
                        code="H11001",
                        name="中证全债",
                        value=f"{latest_close:,.2f}",
                        change=round(bond_change, 2),
                        up=bond_change >= 0,
                    )
                )
        except Exception as exc:
            logger.warning("bond index snapshot failed: %s", exc)

        if results:
            # 按名称去重（保留首次出现的实时数据），避免同名指数导致前端
            # React key 冲突（如"沪深300"在接口数据与解析中可能重复命中）
            seen: set[str] = set()
            unique: list[MarketIndex] = []
            for item in results:
                if item.name not in seen:
                    seen.add(item.name)
                    unique.append(item)
            display_order = {name: index for index, name in enumerate(_DEFAULT_INDEX_CODES)}
            unique.sort(key=lambda item: display_order.get(item.name, len(display_order)))
            return unique
    except Exception as exc:
        logger.warning("indices fetch failed: %s", exc)

    return []


def _refresh_indices() -> None:
    """后台刷新行情；锁可防止冷启动并发请求重复访问外部数据源。"""
    try:
        fresh = _fetch_indices()
        if fresh:
            _set_cache("market_indices", fresh, ttl=120)
    finally:
        global _INDICES_RETRY_AT
        _INDICES_RETRY_AT = time.monotonic() + 30
        _INDICES_REFRESH_LOCK.release()


def indices() -> list[MarketIndex]:
    """立即返回可展示行情，并在缓存缺失时后台刷新真实数据。

    首页首屏不应被 AkShare/Sina 的网络延迟阻塞。冷启动先返回参考快照，
    后台刷新完成后，下一次 React Query 更新即可取得真实行情。
    """
    entry = _CACHE.get("market_indices")
    snapshot = entry[0] if entry else _DEFAULT_INDICES
    if (entry is None or time.time() >= entry[1]) and time.monotonic() >= _INDICES_RETRY_AT:
        if _INDICES_REFRESH_LOCK.acquire(blocking=False):
            entry = _CACHE.get("market_indices")
            if (entry is None or time.time() >= entry[1]) and time.monotonic() >= _INDICES_RETRY_AT:
                try:
                    Thread(target=_refresh_indices, name="market-indices-refresh", daemon=True).start()
                except Exception:
                    _INDICES_REFRESH_LOCK.release()
                    raise
            else:
                _INDICES_REFRESH_LOCK.release()
    return snapshot



def status() -> MarketStatus:
    now = datetime.now()
    current = now.time()

    morning_start = current.replace(hour=9, minute=30, second=0)
    morning_end = current.replace(hour=11, minute=30, second=0)
    afternoon_start = current.replace(hour=13, minute=0, second=0)
    afternoon_end = current.replace(hour=15, minute=0, second=0)

    if (morning_start <= current < morning_end) or (afternoon_start <= current < afternoon_end):
        status_str = "交易中"
        session = "A股连续竞价"
    elif current < morning_start:
        status_str = "未开盘"
        session = "等待开盘"
    elif morning_end <= current < afternoon_start:
        status_str = "午间休市"
        session = "午间休市"
    else:
        status_str = "已收盘"
        session = "等待下一交易日"

    return MarketStatus(
        status=status_str,
        session=session,
        update_time=now.strftime("%H:%M:%S"),
    )
