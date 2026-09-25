"""基金数据服务。

使用 akshare 从东方财富、天天基金、雪球等公开接口获取国内基金数据，
并通过内存 TTL 缓存降低调用频率。数据缺失时保留缺失语义，不使用默认数值
伪装成真实金融事实。
"""

from __future__ import annotations

import bisect
import logging
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Lock, Thread
from typing import Any, Callable, TypeVar

import akshare as ak
import pandas as pd

from models.fund import FundDetail, FundMetrics, FundReturns, FundSummary, Sector, TopHolding

logger = logging.getLogger(__name__)


def _optional_float(value: Any) -> float | None:
    """Convert a source value without turning missing data into zero."""
    if value is None or pd.isna(value):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if pd.notna(parsed) else None

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

_AKSHARE_TIMEOUT = 3  # 交互请求快速失败并回退缓存，避免页面长时间无响应

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
# 数据新鲜度（freshness）：过期数据不得冒充当前数据
# -----------------------------------------------------------------------------

_TRADE_CALENDAR_TTL = 86400  # 交易日历一年变一次，缓存一天足够
_TRADE_CALENDAR_EMPTY_TTL = 600  # 取不到时短缓存，避免每次请求打穿数据源

NAV_STATUS_FRESH = "fresh"
NAV_STATUS_STALE = "stale"
NAV_STATUS_INACTIVE = "inactive"
NAV_STATUS_UNAVAILABLE = "unavailable"
NAV_STATUS_UNKNOWN = "unknown"

# 场外基金净值按 T-1 披露属于正常（当日净值要收盘后才计算、次日公告），
# 因此容忍 1 个交易日的滞后；超过就算 stale。
_NAV_STALE_TOLERANCE_TRADING_DAYS = 1
# 超过约 1 年没有任何净值，基本可判定该基金已终止/合并。
# **这是基于"最后观察日 + 交易日历"的启发式判定，不是退市日期声明** ——
# 数据源不提供可靠的退市日期，因此绝不凭空声称具体终止日。
_NAV_INACTIVE_TRADING_DAYS = 250


def _trade_calendar() -> list["date"]:
    """真实交易日历（含周末与法定节假日），升序去重。

    来源 `ak.tool_trade_date_hist_sina()`（实测 8,797 条，覆盖到 2026-12-31）。
    取不到时返回空列表 —— 调用方必须把"无法判定"当成 unknown，不得当成 fresh。
    """
    cache_key = "trade_calendar"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        df = _call_akshare(ak.tool_trade_date_hist_sina, timeout=20)
        if df is None or df.empty or "trade_date" not in df.columns:
            raise ValueError("empty trade calendar")
        days = sorted({pd.Timestamp(value).date() for value in df["trade_date"] if pd.notna(value)})
        if not days:
            raise ValueError("no usable trade dates")
        _set_cache(cache_key, days, _TRADE_CALENDAR_TTL)
        logger.info("Trade calendar loaded: %d days, last=%s", len(days), days[-1])
        return days
    except Exception as exc:
        logger.warning("Trade calendar unavailable: %s", exc)
        _set_cache(cache_key, [], _TRADE_CALENDAR_EMPTY_TTL)
        return []


def latest_trading_day(today: "date | None" = None) -> "date | None":
    """最近一个**已发生**的有效交易日；日历不可用时返回 None（不猜）。

    用二分查找而不是线性扫描：本函数会被**逐行**调用（基金列表 2.7 万行、
    排行榜 2 万行），而日历有近 9000 天。线性扫描会让冷启动多花几十秒。
    """
    days = _trade_calendar()
    if not days:
        return None
    reference = today or datetime.now().date()
    index = bisect.bisect_right(days, reference)
    return days[index - 1] if index > 0 else None


def _to_date(value: Any) -> "date | None":
    """把净值日期/日期字符串统一成 date；无法解析返回 None。"""
    if value is None:
        return None
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def _trading_days_behind(observed: "date", today: "date | None" = None) -> int | None:
    """观测日之后到最近交易日之间的交易日数量（0 表示就是最近交易日）。

    返回 None 表示交易日历不可用、无法判定 —— 调用方不得当成 0（fresh）。

    同样用二分查找：等价于统计 (observed, latest] 区间内的交易日个数。
    """
    latest = latest_trading_day(today)
    if latest is None:
        return None
    if observed >= latest:
        return 0
    days = _trade_calendar()
    return bisect.bisect_right(days, latest) - bisect.bisect_right(days, observed)


def nav_data_status(observation: Any, today: "date | None" = None) -> str:
    """判断一份净值观测值的新鲜度。

    状态模型（互斥，绝不混成一个 0）：
        fresh       观测日就是最近交易日，或滞后在容差内（场外基金 T-1 属正常）
        stale       数据存在，但明显早于最近交易日
        inactive    长期没有新净值（>= 250 个交易日），判定为已终止候选
        unavailable 没有任何可靠观测值
        unknown     有观测值，但交易日历不可用，无法判定 —— 不得当作 fresh
    """
    observed = _to_date(observation)
    if observed is None:
        return NAV_STATUS_UNAVAILABLE

    behind = _trading_days_behind(observed, today)
    if behind is None:
        return NAV_STATUS_UNKNOWN
    if behind <= _NAV_STALE_TOLERANCE_TRADING_DAYS:
        return NAV_STATUS_FRESH
    if behind >= _NAV_INACTIVE_TRADING_DAYS:
        return NAV_STATUS_INACTIVE
    return NAV_STATUS_STALE


def is_current_nav(observation: Any, today: "date | None" = None) -> bool:
    """该观测值能否当作"当前净值"使用。只有 fresh 才算。"""
    return nav_data_status(observation, today) == NAV_STATUS_FRESH


# -----------------------------------------------------------------------------
# Fund list
# -----------------------------------------------------------------------------

_FUND_LIST_SNAPSHOT: list[FundSummary] | None = None

# 基金列表加载锁：warmup 与并发请求同时触发时会重复调用慢接口（fund_name_em
# 实测 16s+），导致双双超时回退默认快照。用锁实现单飞（single-flight），
# 并发调用排队等待，第一个加载完成后其余直接命中缓存。
_FUND_LIST_LOCK = Lock()


def _build_enrichment_lookup() -> dict[str, dict[str, float | None]]:
    """从 akshare 排行榜获取真实净值/收益率数据，构建 code → 数据的查找表。
    缓存 60 分钟，因为排行榜数据每天只更新一次。
    """
    cache_key = "enrichment_lookup"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    lookup: dict[str, dict[str, Any]] = {}
    try:
        df = _call_akshare(_open_rank_frame, timeout=30)
        for _, row in df.iterrows():
            code = str(row.get("基金代码", "")).strip()
            if not code:
                continue
            nav = _optional_float(row.get("单位净值"))
            change = _optional_float(row.get("日增长率"))
            raw_ret = _optional_float(row.get("近1年"))
            ret_1y = raw_ret / 100 if raw_ret is not None else None
            # 排行榜自带 `日期` 列（实测格式 2026-09-18）。必须保留它：没有
            # 观测日，nav 就会被当成"当前净值"，而榜单快照本身可能是旧的。
            observed = _to_date(row.get("日期"))
            lookup[code] = {
                "nav": nav,
                "change_pct": change,
                "one_year_return": ret_1y,
                "nav_date": observed.isoformat() if observed else None,
                "nav_status": nav_data_status(observed),
            }
        _set_cache(cache_key, lookup, ttl=3600)  # 1 小时
        logger.info("Enrichment lookup built: %d funds", len(lookup))
    except Exception as exc:
        logger.warning("Failed to build enrichment lookup: %s", exc)
        _set_cache(cache_key, {}, ttl=600)  # 失败时缓存空结果 10 分钟
    return lookup


def _load_fund_list() -> list[FundSummary]:
    """从 akshare 拉取全部基金列表，用排行榜数据丰富后缓存。

    失败时返回空列表：绝不返回硬编码的替代基金池（那会让用户看到
    真实代码 + 伪造净值的基金）。
    """
    cached = _get_cache("fund_list")
    if cached is not None:
        return cached

    with _FUND_LIST_LOCK:
        # 双重检查：排队等待期间可能已被其他线程（含启动预热）加载完成
        cached = _get_cache("fund_list")
        if cached is not None:
            return cached

        try:
            # fund_name_em 全市场列表较大（实测 12-24s），默认 12s 超时会被误掐断
            # 导致只能回退默认快照；这里单独放宽到 45s。
            #
            # ETF 名录**不能**和这两个大请求并发取：三者都是东方财富上游，
            # 同时发起会互相拖慢（实测 fund_etf_fund_daily_em 单独 1.55s、
            # 并发时 20.58s，被拖慢 13 倍），而它的超时是 30s —— 于是每次冷启动
            # 都稳定超时（实测 3/3 在 30.04s 被掐断），并被缓存成**空名录** 600 秒。
            # 空名录的后果是真实 ETF 被判为非 ETF：K 线返回空、类型被标成"股票型"。
            #
            # 实测串行与并发的总耗时几乎相同（21.5s vs 20.6s），并发没有收益，
            # 因此把名录挪到这两个请求之后再取，不再与它们争抢上游。
            with ThreadPoolExecutor(max_workers=2) as _ex:
                _f_list = _ex.submit(_call_akshare, ak.fund_name_em, timeout=45)
                _f_enrich = _ex.submit(_build_enrichment_lookup)
                df = _f_list.result()
                enrichment = _f_enrich.result()
            # 名录在这里预取：`_is_etf_code()` 依赖它，若等到下面的逐行循环里
            # 首次调用，会在持 _FUND_LIST_LOCK 的情况下串行等一次网络。
            _etf_registry()

            df = df.drop_duplicates(subset=["基金代码"], keep="first")

            funds: list[FundSummary] = []
            for _, row in df.iterrows():
                code = str(row["基金代码"]).strip()
                name = str(row["基金简称"]).strip()
                raw_ftype = str(row["基金类型"]).strip()
                enriched = enrichment.get(code, {})
                # 场内 ETF 用真实名录覆盖类型，避免数据源把 ETF 与 LOF 都标成
                # "指数型-股票"而无法区分（实测 159915/161725/160632 三者同标签）。
                ftype = "ETF" if _is_etf_code(code) else _simplify_type(raw_ftype)

                funds.append(
                    FundSummary(
                        code=code,
                        name=name,
                        company=_extract_company(name),
                        type=ftype,
                        nav=(round(enriched["nav"], 4) if enriched.get("nav") is not None else None),
                        nav_date=enriched.get("nav_date"),
                        nav_status=enriched.get("nav_status"),
                        change_pct=(round(enriched["change_pct"], 2) if enriched.get("change_pct") is not None else None),
                        one_year_return=(round(enriched["one_year_return"], 4) if enriched.get("one_year_return") is not None else None),
                        # 列表级没有真实波动率可用于推导等级：返回 None，而不是
                        # 按基金类型查表猜一个等级。
                        risk_level=None,
                        size="-",
                        heat=None,
                    )
                )
            _set_cache("fund_list", funds, _LIST_TTL_SECONDS)
            enriched_count = sum(1 for f in funds if f.nav is not None and f.nav > 0)
            logger.info("Fund list loaded: %d total, %d enriched with real data", len(funds), enriched_count)
            return funds
        except Exception as exc:
            logger.warning("akshare fund_name_em failed: %s (returning empty list)", exc)
            return []


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
    # Preserve an unrecognised source type instead of silently relabelling it
    # as a different fund category.
    return raw or "未知"


# -----------------------------------------------------------------------------
# ETF registry：场内 ETF 的权威名录（身份 + 真实净值 + 市价 + 折价率）
# -----------------------------------------------------------------------------

_ETF_REGISTRY_TTL = 86400  # 场内 ETF 名录一天变一次
_ETF_REGISTRY_EMPTY_TTL = 600  # 取不到名录时短缓存，避免每次请求都打穿数据源
_ETF_NAV_COLUMN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(单位净值|累计净值)$")


def _optional_percent(value: Any) -> float | None:
    """解析带 `%` 的字符串字段（如 '-0.06%'），返回百分数（-0.06）。

    本项目约定 `*_pct` 字段本身就是百分数（前端 formatPercentValue 直接追加
    `%`），所以这里剥掉符号后原样返回，不再除以 100。

    必须单独处理：`fund_etf_fund_daily_em()` 的所有列都是字符串，
    `折价率` 形如 '-0.06%'，直接 float() 会失败并被静默丢成 None。
    """
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text or text in ("nan", "<NA>", "None", "-", "--"):
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if pd.notna(parsed) else None


def _etf_registry() -> dict[str, dict[str, Any]]:
    """场内 ETF 权威名录：code -> 真实净值 / 市价 / 折价率。

    来源 `ak.fund_etf_fund_daily_em()`（实测 1,660 只，类型全部为"指数型-*"）。
    净值列名带日期前缀，形如 `2026-09-18-单位净值`，取最新一天。

    这是"某只基金是不是场内 ETF"的唯一真源。两种看起来可行的替代方案都实测失败：
      1. 代码前缀：519066（汇添富蓝筹稳健，场外混合型）以 51 开头，
         162411/160632/161725（LOF）以 16 开头，全部被误判成 ETF。
      2. `基金类型` 字段：159915（真 ETF）与 161725/160632（LOF）在
         fund_name_em 里都是"指数型-股票"，无法区分。

    `市价` 与 `折价率` 单独存放，不与净值混用：ETF 二级市场价格会相对净值
    折溢价（510300 实测 市价 4.5820 / 单位净值 4.5793 / 折价率 -0.06%）。
    """
    cache_key = "etf_registry"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    registry: dict[str, dict[str, Any]] = {}
    try:
        df = _call_akshare(ak.fund_etf_fund_daily_em, timeout=30)
        if df is None or df.empty or "基金代码" not in df.columns:
            raise ValueError("fund_etf_fund_daily_em returned no usable rows")

        dated: dict[str, dict[str, str]] = {}
        for column in df.columns:
            match = _ETF_NAV_COLUMN_RE.match(str(column))
            if match:
                dated.setdefault(match.group(1), {})[match.group(2)] = str(column)
        if not dated:
            raise ValueError("no date-prefixed NAV columns in fund_etf_fund_daily_em")
        latest_date = max(dated)
        unit_col = dated[latest_date].get("单位净值")
        cumulative_col = dated[latest_date].get("累计净值")

        for _, row in df.iterrows():
            code = str(row.get("基金代码", "")).strip()
            if not code:
                continue
            registry[code] = {
                "name": str(row.get("基金简称", "")).strip(),
                "type": str(row.get("类型", "")).strip(),
                "nav_date": latest_date,
                "unit_nav": _optional_float(row.get(unit_col)) if unit_col else None,
                "cumulative_nav": _optional_float(row.get(cumulative_col)) if cumulative_col else None,
                "market_price": _optional_float(row.get("市价")),
                # 折价率源数据是 '-0.06%' 这样的字符串，必须按百分数解析；
                # 用 _optional_float 会静默变成 None，把真实的折溢价信息丢掉。
                "discount_rate": _optional_percent(row.get("折价率")),
            }
        _set_cache(cache_key, registry, _ETF_REGISTRY_TTL)
        logger.info("ETF registry loaded: %d funds @ %s", len(registry), latest_date)
    except Exception as exc:
        logger.warning("ETF registry unavailable: %s", exc)
        _set_cache(cache_key, {}, _ETF_REGISTRY_EMPTY_TTL)
    return registry


def _is_etf_code(code: str) -> bool:
    """按**真实场内 ETF 名录**判定，不用代码前缀猜测。

    名录不可用时返回 False（保守），不猜。此时 ETF 会走场外净值路径：实测
    `fund_open_fund_info_em` 对 ETF 同样返回真实净值（510300 与
    `fund_etf_fund_info_em` 的序列逐行一致），所以净值/收益仍然正确；受影响的
    只有 K 线（无 OHLC 时返回空列表，前端显示"暂不可用"），属于诚实的降级，
    好过用前缀猜出一个 LOF 的市场价冒充基金净值。
    """
    return str(code).strip() in _etf_registry()


# 年化波动率 → 风险等级。
# **这是项目内部口径，不是监管评级、也不是综合评分**：唯一输入是真实计算出
# 来的年化波动率（`returns.std() * sqrt(252)`，收益序列为累计净值口径）。
# 不做基金类型查表，不产出 0-100 分数，缺失波动率时返回 None。
_VOLATILITY_LEVEL_BANDS: tuple[tuple[float, str], ...] = (
    (0.05, "低"),
    (0.12, "中低"),
    (0.18, "中"),
    (0.25, "中高"),
)


def risk_level_from_volatility(volatility: float | None) -> str | None:
    """由**真实年化波动率**推导风险等级；波动率不可用时返回 None（不猜）。

    说明：分档阈值是本项目自行约定的口径，必须与波动率一同展示，供使用者
    自行判断；它不代表任何监管或第三方评级。
    """
    if volatility is None:
        return None
    for upper, level in _VOLATILITY_LEVEL_BANDS:
        if volatility < upper:
            return level
    return "高"


# -----------------------------------------------------------------------------
# Net value history
# -----------------------------------------------------------------------------


_NAV_COLUMNS = ["净值日期", "单位净值", "累计净值", "日增长率"]


def _fetch_nav_history(code: str) -> pd.DataFrame:
    """获取场外基金历史净值 DataFrame，列：净值日期、单位净值、累计净值、日增长率。

    **必须同时取到累计净值**：单位净值在除息日被扣减分红，用它计算收益会把
    "分红"误算成"亏损"。实测 161725 用单位净值算出的累计收益是 -47%，
    用累计净值是 +124%（最大回撤 -69.88% vs -36.01%）。000001 差 257pp、
    519066 差 133pp —— 且 110022/000961 差 0，抽查时看不出问题。

    累计净值缺失的行直接丢弃并记录条数：不做任何替代，也不静默回退到单位净值。
    取不到时返回空的同结构 DataFrame —— 不生成任何替代净值序列。
    """
    cache_key = f"nav:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    try:
        unit = _call_akshare(
            ak.fund_open_fund_info_em, symbol=code, indicator="单位净值走势", period="成立来"
        )
        unit = unit.dropna(subset=["净值日期", "单位净值"])
        unit["净值日期"] = pd.to_datetime(unit["净值日期"])
        unit["单位净值"] = pd.to_numeric(unit["单位净值"], errors="coerce")
        unit = unit.dropna(subset=["单位净值"])

        cumulative = _call_akshare(
            ak.fund_open_fund_info_em, symbol=code, indicator="累计净值走势", period="成立来"
        )
        cumulative = cumulative.dropna(subset=["净值日期", "累计净值"])
        cumulative["净值日期"] = pd.to_datetime(cumulative["净值日期"])
        cumulative["累计净值"] = pd.to_numeric(cumulative["累计净值"], errors="coerce")
        cumulative = cumulative.dropna(subset=["累计净值"])
        cumulative = cumulative.drop_duplicates(subset=["净值日期"], keep="last")

        df = unit.merge(cumulative[["净值日期", "累计净值"]], on="净值日期", how="left")
        missing = int(df["累计净值"].isna().sum())
        if missing:
            logger.warning(
                "nav history %s: dropping %d/%d rows without cumulative NAV",
                code, missing, len(df),
            )
        df = df.dropna(subset=["累计净值"])
        df = df.sort_values("净值日期").reset_index(drop=True)
        df = df[_NAV_COLUMNS]
        _set_cache(cache_key, df, ttl=3600)  # 1 小时，净值日内不变
        return df
    except Exception as exc:
        logger.warning("nav history fetch failed for %s: %s", code, exc)
        return pd.DataFrame(columns=_NAV_COLUMNS)


def total_return_series(df: pd.DataFrame) -> pd.Series:
    """返回一切收益/风险计算必须使用的「总收益基准」序列。

    唯一正确基准是 **累计净值**。两个实测反例：
      * 除息日：单位净值被扣掉分红。161725 用单位净值算出累计收益 -47.17%，
        用累计净值是 +124.44%（最大回撤 -69.88% vs -36.01%）。
      * 份额折算：ETF 单位净值会跳空。510300 在 2012-05-11 从 1.007 跳到
        2.637，单位净值口径总收益 +354.75%，累计净值口径 +101.10%
        （该日"日增长率 -2.86%"与累计净值一致，证明累计净值才是真实收益）。

    **不接受市价帧**（含 close 但没有累计净值）：二级市场成交价不是基金净值，
    两者会相对折溢价（510300 实测 市价 4.5820 vs 单位净值 4.5793）。让它们
    互相顶替，就是把"市场价"包装成"基金收益"。
    """
    if df is None or df.empty:
        raise ValueError("净值数据为空，无法确定收益基准")
    if "累计净值" not in df.columns:
        raise ValueError(
            "缺少累计净值列，无法计算总收益"
            "（不能用单位净值或二级市场市价替代：除息日/份额折算会被误算为盈亏）"
        )
    basis = pd.to_numeric(df["累计净值"], errors="coerce")
    if basis.notna().sum() < 2:
        raise ValueError("累计净值数据不足，无法计算总收益")
    return basis


def _etf_sina_symbol(code: str) -> str:
    """510300 → sh510300, 159915 → sz159915

    这里用前缀只是为了拼交易所前缀（新浪接口需要 sh/sz），**不用于判定
    "是不是 ETF"** —— 那个判断由 `_is_etf_code()` 查真实名录完成。拼错前缀
    最多导致该数据源取不到数据，不会让别的品种冒充 ETF。
    """
    code = code.strip()
    if code.startswith(("51", "56", "58")):
        return f"sh{code}"
    if code.startswith(("15", "16")):
        return f"sz{code}"
    return f"sh{code}"  # 默认上海


# 场内 ETF 的**二级市场行情**列表：只有成交价与成交量，没有任何净值字段。
_ETF_PRICE_COLUMNS = ["净值日期", "open", "high", "low", "close", "volume", "turnover"]


def _fetch_etf_price_history(code: str, days: int = 730) -> pd.DataFrame:
    """获取场内 ETF 的**二级市场行情**（OHLCV）。

    这里返回的是市场成交价，**不是基金净值**。两者是不同的东西：ETF 会相对
    净值折溢价（510300 实测 市价 4.5820 / 单位净值 4.5793 / 折价率 -0.06%）。
    因此本函数**绝不写入 `单位净值` 列**：一旦写入，下游就会把市场价当成基金
    净值去算收益、波动率、最大回撤。

    基金净值一律由 `_fetch_nav_history()` 提供（实测它对 ETF 同样返回真实净值）。

    复权口径：新浪源返回不复权行情，因此东方财富备用源固定用 `adjust=""`
    （不复权）。原实现备用源用 `qfq`（前复权），会让主备源切换时同一天的
    收盘价含义不同、序列基准跳变；而且前复权用到未来分红信息，本身也不该
    出现在"历史成交价"里。

    取不到时返回空的同结构 DataFrame —— 不生成任何替代行情。
    """
    cache_key = f"etfprice:{code}:{days}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    empty_df = pd.DataFrame(columns=_ETF_PRICE_COLUMNS)

    # ── 方案1: 新浪数据源（稳定，返回 date/open/high/low/close/volume/amount）──
    try:
        sina_sym = _etf_sina_symbol(code)
        df = _call_akshare(ak.fund_etf_hist_sina, symbol=sina_sym)
        if not df.empty and "date" in df.columns:
            df = df.rename(columns={
                "date": "净值日期",
                "amount": "turnover",
            })
            for column in ("open", "high", "low", "close", "volume", "turnover"):
                if column in df.columns:
                    df[column] = pd.to_numeric(df[column], errors="coerce")
            df["净值日期"] = pd.to_datetime(df["净值日期"])
            df = df.dropna(subset=["净值日期", "open", "high", "low", "close"])
            df = df[df["净值日期"] >= datetime.now() - timedelta(days=days)]
            df = df.sort_values("净值日期").reset_index(drop=True)
            if not df.empty:
                df = df[[c for c in _ETF_PRICE_COLUMNS if c in df.columns]]
                _set_cache(cache_key, df, ttl=7200)  # 2 小时
                return df
    except Exception as exc:
        logger.warning("sina etf price history failed for %s: %s", code, exc)

    # ── 方案2: 东方财富数据源（备用，同样不复权）──
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = _call_akshare(
            ak.fund_etf_hist_em,
            symbol=code,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="",  # 不复权：与新浪源口径一致，且不使用未来分红信息
        )
        if df is None or df.empty:
            return empty_df
        df = df.rename(columns={
            "日期": "净值日期",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "turnover",
        })
        for column in ("open", "high", "low", "close", "volume", "turnover"):
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")
        df["净值日期"] = pd.to_datetime(df["净值日期"])
        df = df.dropna(subset=["净值日期", "open", "high", "low", "close"])
        df = df.sort_values("净值日期").reset_index(drop=True)
        df = df[[c for c in _ETF_PRICE_COLUMNS if c in df.columns]]
        _set_cache(cache_key, df, ttl=7200)  # 2 小时
        return df
    except Exception as exc:
        logger.warning("eastmoney etf price history failed for %s: %s", code, exc)
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
        return ""
    return date_str[:10]


def _returns_from_nav(nav_df: pd.DataFrame) -> FundReturns:
    """基于净值序列计算日/周/月/年收益。

    收益一律以 **累计净值** 为基准（见 `total_return_series`）：单位净值在除息日
    下跌，用它计算会把分红记成亏损。

    净值点不足 2 个时没有可比较的前值，拒绝计算 —— 不返回 0 冒充收益。
    """
    if len(nav_df) < 2:
        raise ValueError("净值数据不足，无法计算收益")

    basis = total_return_series(nav_df)
    dates = nav_df["净值日期"]
    latest = float(basis.iloc[-1])

    def _pct_for_days(days: int) -> float | None:
        target = dates.iloc[-1] - timedelta(days=days)
        past = basis[dates <= target]
        if past.empty:
            return None
        past_nav = _optional_float(past.iloc[-1])
        return (latest - past_nav) / past_nav if past_nav and past_nav > 0 else None

    previous = _optional_float(basis.iloc[-2])
    if previous is None or previous <= 0 or latest <= 0:
        raise ValueError("净值数据包含无效值，无法计算收益")
    daily = (latest - previous) / previous
    weekly = _pct_for_days(7)
    monthly = _pct_for_days(30)
    yearly = _pct_for_days(365)

    return FundReturns(daily=daily, weekly=weekly, monthly=monthly, yearly=yearly)


def _metrics_from_nav(nav_df: pd.DataFrame, ftype: str) -> FundMetrics:
    """基于净值序列计算风险指标。

    波动率/回撤/夏普同样以 **累计净值** 为基准：单位净值的除息跳水会同时虚增
    波动率和最大回撤（实测 161725 的最大回撤从 -36.01% 被夸大到 -69.88%）。

    净值点少于 3 个（即不足 2 个收益率样本）时统计量无定义，直接报错 ——
    绝不返回凭空设定的 volatility=0.02 / beta=0.5 / max_drawdown=0.0。
    """
    if len(nav_df) < 3:
        raise ValueError("净值数据不足，无法计算风险指标")

    nav = total_return_series(nav_df).astype(float).values
    returns = nav[1:] / nav[:-1] - 1
    if len(returns) < 2:
        raise ValueError("净值数据不足，无法计算波动率")

    # 年化波动率（按 252 个交易日）
    volatility = float(returns.std() * (252**0.5))

    # 最大回撤
    peak = nav[0]
    max_dd = 0.0
    for v in nav:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    # 夏普：无风险利率按 2% 年化。
    # 注意 excess.std() == 0 时夏普无定义（分母为 0），必须返回 None ——
    # 之前返回 0.0 是"缺数据变成 0"，会把"算不出来"伪装成"风险调整后收益为 0"。
    risk_free_daily = 0.02 / 252
    excess = returns - risk_free_daily
    sharpe = (
        round(float(excess.mean() / excess.std() * (252**0.5)), 2)
        if excess.std() > 0
        else None
    )

    return FundMetrics(
        max_drawdown=-max_dd,
        volatility=volatility,
        sharpe=sharpe,
        # 风险等级只由真实年化波动率推导（见 risk_level_from_volatility）。
        risk_level=risk_level_from_volatility(volatility),
        # risk_score 不存在可复现的数学定义（输入指标、权重、阈值均无依据），
        # 因此一律不可用。绝不为保留字段而编一个 0-100 的分数。
        # 真实风险信息由 volatility / max_drawdown / sharpe 承载。
        risk_score=None,
        alpha=None,
        beta=None,
        sortino=None,
        information_ratio=None,
    )


# -----------------------------------------------------------------------------
# Real holdings & sectors (from quarterly reports)
# -----------------------------------------------------------------------------

_HOLDINGS_CACHE_TTL = 86400  # 24 小时（季报数据不常变）
# 抓取**失败**时只能短缓存：一次网络抖动若按 24 小时缓存空结果，会让这只基金的
# 重仓/行业整整一天都是空的（而数据其实拿得到）。空结果本身也可能是合法稳态
# （例如股票持仓为空的债基），所以只有异常路径用短 TTL。
_HOLDINGS_FAILURE_TTL = 300  # 5 分钟
_HOLDINGS_AS_OF: dict[str, str | None] = {}
_SECTORS_AS_OF: dict[str, str | None] = {}

# 天天基金返回的季度标签形如 "2026年2季度股票投资明细"；行业配置的截止时间是
# 日期字符串 "2026-06-30"。两种都要能解析成可比较的报告期。
_QUARTER_LABEL_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*季度|(\d{4})\s*[Qq]\s*(\d)")


def _report_period_sort_key(label: Any) -> tuple[int, int]:
    """把报告期标签解析成可排序的 (年, 季)；无法解析时返回 (0, 0)。

    报告期是"这个数字属于哪个时点"的唯一依据。用 DataFrame 的行序当"最新"
    是错的：上游把多个季度放在同一个 frame 里，行序并不保证最新在前。
    """
    text = "" if label is None else str(label).strip()
    if not text:
        return (0, 0)

    match = _QUARTER_LABEL_RE.search(text)
    if match:
        year, quarter = (
            (match.group(1), match.group(2))
            if match.group(1) is not None
            else (match.group(3), match.group(4))
        )
        try:
            return (int(year), int(quarter))
        except (TypeError, ValueError):
            return (0, 0)

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.notna(parsed):
        return (int(parsed.year), (int(parsed.month) - 1) // 3 + 1)
    return (0, 0)


def _latest_report_period(labels: "pd.Series", code: str, what: str) -> Any | None:
    """从一组报告期标签里取最新的一期；无法判定时返回 None（不猜）。"""
    candidates = [value for value in labels.dropna().unique().tolist() if str(value).strip()]
    if not candidates:
        return None
    latest = max(candidates, key=lambda value: (_report_period_sort_key(value), str(value)))
    if _report_period_sort_key(latest) == (0, 0):
        logger.warning(
            "%s %s: unparsable report periods %s; refusing to guess the newest one",
            what, code, candidates[:5],
        )
        return None
    return latest


def _fetch_real_holdings(code: str) -> list[TopHolding] | None:
    """从 akshare 获取基金**最新报告期**的前十大持仓。失败时返回 None。

    上游 `fund_portfolio_hold_em(date="")` 会一次性返回最新年度内的**所有季度**，
    且行序不保证最新在前（实测 000001 的 frame 第一组是 "2026年1季度"，而
    "2026年2季度" 才是最新）。因此必须按报告期解析排序，不能取 iloc[0] ——
    否则页面展示的是过期一个季度的持仓（中际旭创 4.31% vs 实际 6.45%），
    并把 as_of 也标成旧季度。
    """
    cache_key = f"holdings:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached if cached else None  # 空列表也缓存

    try:
        # 空日期让上游返回最新可用披露期；固定年份会把过期季报冒充当前持仓。
        df = _call_akshare(ak.fund_portfolio_hold_em, symbol=code, date="")
        if df.empty or "季度" not in df.columns:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        latest_quarter = _latest_report_period(df["季度"], code, "holdings")
        if latest_quarter is None:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        _HOLDINGS_AS_OF[code] = str(latest_quarter)
        qtr_df = df[df["季度"] == latest_quarter].head(10)

        holdings: list[TopHolding] = []
        for _, row in qtr_df.iterrows():
            raw_weight = _optional_float(row.get("占净值比例"))
            if raw_weight is None:
                # 缺失的权重不能变成 0：0% 权重等于"没有这只持仓"，
                # 会把一条真实持仓伪装成不存在。
                logger.warning(
                    "holdings %s %s: skipping %s with missing weight",
                    code, latest_quarter, row.get("股票名称"),
                )
                continue
            holdings.append(
                TopHolding(
                    name=str(row.get("股票名称", "")).strip(),
                    code=str(row.get("股票代码", "")).strip() if pd.notna(row.get("股票代码")) else None,
                    weight=raw_weight,
                    change_pct=None,  # 季报不含当日涨跌
                )
            )
        _set_cache(cache_key, holdings, _HOLDINGS_CACHE_TTL)
        return holdings if holdings else None
    except Exception as exc:
        logger.warning("Real holdings fetch failed for %s: %s", code, exc)
        _set_cache(cache_key, [], _HOLDINGS_FAILURE_TTL)
        return None


def _fetch_real_sectors(code: str) -> list[Sector] | None:
    """从 akshare 获取基金**最新报告期**的行业配置。失败时返回 None。

    上游 `fund_portfolio_industry_allocation_em(date="")` 同时返回多个报告期
    （实测 000001 返回 2026-06-30 与 2026-03-31 两期）。原实现遍历所有行并按
    行业名相加，等于把两个季度的权重叠加成一个从未存在过的配置：制造业
    72.78 + 61.14 = 133.92，再被整体缩放回 100% → 展示 87.8%。

    这里改为：先锁定最新报告期，只保留该期；权重原样输出，不猜测单位、
    不归一化。合计不足 100% 是真实的（未披露部分），必须如实呈现。
    """
    cache_key = f"sectors:{code}"
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached if cached else None

    try:
        df = _call_akshare(ak.fund_portfolio_industry_allocation_em, symbol=code, date="")
        if df.empty:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        # 列名检测：akshare 返回 序号/行业类别/占净值比例/市值/截止时间
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

        as_of_col = next((c for c in ("截止时间", "季度", "报告期", "截止日期") if c in df.columns), None)
        if as_of_col is None:
            # 没有报告期就无法证明这些权重属于同一时点，不能拼成一张配置图。
            logger.warning("Sectors %s: no report-period column, available: %s", code, list(df.columns))
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        latest_period = _latest_report_period(df[as_of_col], code, "sectors")
        if latest_period is None:
            _set_cache(cache_key, [], _HOLDINGS_CACHE_TTL)
            return None

        _SECTORS_AS_OF[code] = str(latest_period)
        period_df = df[df[as_of_col] == latest_period]

        colors = ["#171717", "#0071e3", "#6e6e73", "#00a550", "#ff9500",
                   "#ff3b30", "#af52de", "#34c759", "#5856d6", "#d1d1d6"]

        rows: list[tuple[str, float]] = []
        for _, row in period_df.iterrows():
            name = str(row[name_col]).strip()
            if not name or name == "nan":
                continue
            weight = _optional_float(row[weight_col])
            if weight is None:
                # 缺失权重不能当作 0%：那会让一个真实存在的行业从图上消失。
                logger.warning(
                    "sectors %s %s: skipping %s with missing weight",
                    code, latest_period, name,
                )
                continue
            if weight <= 0:
                continue
            rows.append((name, weight))

        # 同一报告期内若出现同名行业（层级重复），只保留权重最高的那条并记录，
        # 不做相加 —— 相加会造出一个数据源从未披露过的数字。
        rows.sort(key=lambda item: item[1], reverse=True)
        deduped: list[tuple[str, float]] = []
        seen: set[str] = set()
        for name, weight in rows:
            if name in seen:
                logger.warning(
                    "sectors %s %s: dropping duplicate sector %s", code, latest_period, name
                )
                continue
            seen.add(name)
            deduped.append((name, weight))

        sectors = [
            Sector(name=name, weight=round(weight, 2), color=colors[i % len(colors)])
            for i, (name, weight) in enumerate(deduped[:10])
        ]
        _set_cache(cache_key, sectors, _HOLDINGS_CACHE_TTL)
        return sectors if sectors else None
    except Exception as exc:
        logger.warning("Real sectors fetch failed for %s: %s", code, exc)
        _set_cache(cache_key, [], _HOLDINGS_FAILURE_TTL)
        return None


def _tags_for(name: str, ftype: str) -> list[str]:
    # Keep only the source category. Name-keyword labels are inferences, not
    # disclosed fund classifications.
    return [ftype] if ftype else []


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def list_all() -> list[FundSummary]:
    return _load_fund_list()


def _type_from_name_list(code: str) -> str:
    """从基金名称列表中查询某只基金的类型。"""
    funds = _load_fund_list()
    f = next((f for f in funds if f.code == code), None)
    return f.type if f else ""


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
    # 没有任何真实快照时返回空列表，而不是硬编码的替代榜单。
    snapshot = entry[0] if entry else []
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
            ftype = _simplify_type(raw_type) if raw_type else ("ETF" if _is_etf_code(code) else "未知")
            nav = _optional_float(row.get("单位净值")) if "单位净值" in df.columns else None
            change_pct = _optional_float(row.get("日增长率")) if "日增长率" in df.columns else None
            raw_one_year = _optional_float(row.get("近1年")) if "近1年" in df.columns else None
            one_year = raw_one_year / 100 if raw_one_year is not None else None
            # 榜单自带日期（场内榜单列为 `日期`）。保留观测日，避免把一份旧的
            # 榜单快照当成"当前净值"展示。
            observed = _to_date(row.get("日期")) if "日期" in df.columns else None

            results.append(
                FundSummary(
                    code=code,
                    name=name,
                    company="-",
                    type=ftype,
                    nav=round(nav, 4) if nav is not None else None,
                    nav_date=observed.isoformat() if observed else None,
                    nav_status=nav_data_status(observed) if observed else None,
                    change_pct=round(change_pct, 2) if change_pct is not None else None,
                    one_year_return=round(one_year, 4) if one_year is not None else None,
                    # 榜单没有真实波动率：不按类型猜风险等级。
                    risk_level=None,
                    size="-",
                    heat=None,
                )
            )

    # 去重并按近一年收益排序
    seen: set[str] = set()
    unique: list[FundSummary] = []
    for f in results:
        if f.code not in seen:
            seen.add(f.code)
            unique.append(f)
    unique.sort(key=lambda f: f.one_year_return if f.one_year_return is not None else float("-inf"), reverse=True)
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

    # 1. 从基金列表获取基金名称和类型。
    #    基金列表是"该基金是否存在"的唯一真源；不在列表中即视为未知基金。
    funds = _load_fund_list()
    summary = next((f for f in funds if f.code == upper), None)

    if summary is None:
        # 绝不编造名称/类型/公司/净值来凑出一个详情页。
        raise ValueError(f"未找到基金 {upper}")

    name = summary.name
    ftype = summary.type
    company = _extract_company(name)

    # 2. 判断是否场内 ETF（查真实名录，不用代码前缀猜）。
    if _is_etf_code(upper):
        ftype = "ETF"  # 覆盖类型，确保前端能进入 K 线逻辑

    # 3. 获取净值历史、真实持仓、行业分布、基本信息（四者并行）。
    #    **所有基金类型统一走净值接口**：ETF 与 LOF 也用净值，不用二级市场价。
    #    实测 fund_open_fund_info_em 对 ETF（510300）返回的净值序列与
    #    fund_etf_fund_info_em 逐行一致，因此这里不需要按类型分叉。
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _f_nav = _ex.submit(_fetch_nav_history, upper)
        _f_sectors = _ex.submit(_fetch_real_sectors, upper)
        _f_holdings = _ex.submit(_fetch_real_holdings, upper)
        _f_basic = _ex.submit(_fetch_basic_info, upper)
        nav_df = _f_nav.result()
        sectors_raw = _f_sectors.result()
        holdings_raw = _f_holdings.result()
        basic_info = _f_basic.result()

    # 4. 计算"当前净值"与涨跌幅。
    #    全部风险指标（收益率 / 波动率 / 回撤 / 夏普）都由净值序列推导：
    #    净值不足 3 条时统计量无定义，因此直接报错，由前端展示
    #    "数据暂时不可用"。绝不填充 0、估算值或生成的替代序列。
    if len(nav_df) < 3:
        raise ValueError(
            f"基金 {upper} 的真实净值数据不足（{len(nav_df)} 条），无法计算风险指标"
        )

    # 4.1 新鲜度：序列最后一条只是"最近一次观测值"，不能想当然当成"当前净值"。
    #     已退市 / 长期停牌的基金仍有完整历史序列，其最后一条绝不是当前净值。
    #     判断依据是**真实交易日历**，不是本地时钟。
    nav_as_of_date = _to_date(nav_df["净值日期"].iloc[-1])
    nav_as_of = nav_as_of_date.isoformat() if nav_as_of_date else None
    nav_status = nav_data_status(nav_as_of_date)

    # 展示净值用单位净值（用户看到的"净值"就是它）；但涨跌幅必须用累计净值：
    # 除息日单位净值下跌是分红，不是亏损，用单位净值算会显示一根假阴线。
    latest_nav = float(nav_df["单位净值"].iloc[-1])
    basis = total_return_series(nav_df)
    basis_latest = float(basis.iloc[-1])
    basis_prev = float(basis.iloc[-2])
    if basis_prev <= 0 or basis_latest <= 0:
        raise ValueError(f"基金 {upper} 的累计净值包含无效值，无法计算涨跌幅")
    change_pct = (basis_latest - basis_prev) / basis_prev * 100

    returns = _returns_from_nav(nav_df)
    metrics = _metrics_from_nav(nav_df, ftype)

    if nav_status == NAV_STATUS_INACTIVE:
        # 该基金长期没有任何新净值（>= 250 个交易日）：判定为已终止/停牌候选。
        # **不声称具体退市日期**（数据源没有可靠字段，不猜）。
        # 最后一条净值是历史事实而不是当前净值，因此绝不把它作为 nav 返回，
        # 也不给出"当日涨跌幅"和"近一年收益"—— 那些都属于当前状态口径。
        # 历史序列本身不受影响，仍可通过净值历史接口查询。
        logger.warning(
            "fund %s: no NAV since %s (%d trading days behind) -> inactive, "
            "refusing to report the last observation as current",
            upper, nav_as_of, _trading_days_behind(nav_as_of_date) or 0,
        )
        latest_nav = None
        change_pct = None
        one_year_return = None
    else:
        one_year_return = round(returns.yearly, 4) if returns.yearly is not None else None

    # 5. 真实持仓与行业分布（季报数据）。取不到就留空 —— 不填充任何默认持仓/行业。
    sectors = sectors_raw or []
    top_holdings = holdings_raw or []
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
    # 数据源不提供基金经理任职起始日：不估算，返回 None（前端显示"暂无"），
    # 绝不用基金成立日冒充经理任职天数。
    manager_days = None
    # 基金评级（如果数据源提供）
    rating_str = basic_info.get("评级", basic_info.get("基金评级", ""))
    try:
        rating = int(float(rating_str)) if rating_str and rating_str not in ("nan", "<NA>") else None
        if rating is not None:
            rating = max(1, min(5, rating))
    except (ValueError, TypeError):
        rating = None

    return FundDetail(
        code=upper,
        name=name,
        company=company,
        type=ftype,
        nav=round(latest_nav, 4) if latest_nav is not None else None,
        nav_date=nav_as_of,
        nav_status=nav_status,
        change_pct=round(change_pct, 2) if change_pct is not None else None,
        one_year_return=one_year_return,
        risk_level=metrics.risk_level,
        size=fund_size,
        heat=None,
        inception_date=inception,
        returns=returns,
        metrics=metrics,
        sectors=sectors,
        tags=_tags_for(name, ftype),
        description=f"{name}是一只{ftype}基金。",
        manager=manager,
        manager_days=manager_days,
        rating=rating,
        top_holdings=top_holdings,
        # 投资风格需要真实持仓风格 / RBSA 等数据才能判定。当前不可得：
        # 一律 None，绝不由基金类型猜一个标签（原文案来自 _style_for_type）。
        investment_style=None,
        holdings_as_of=_HOLDINGS_AS_OF.get(upper),
        sectors_as_of=_SECTORS_AS_OF.get(upper),
    )


def nav_history(code: str) -> pd.DataFrame:
    """返回该基金的**历史净值** DataFrame（单位净值 + 累计净值）。

    所有品种统一走净值接口，包括 ETF 与 LOF：二级市场行情由
    `_fetch_etf_price_history()` 单独提供，两条数据流不交叉。绝不把市场
    成交价当作净值返回 —— 那会让收益、波动率、最大回撤全部失真。
    """
    return _fetch_nav_history(code.strip().upper())
