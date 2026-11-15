"""研究概览：区间累计净值指标与真实交易日基准对齐。

本模块只组合现有净值、指标和对齐实现，不另写一套波动率或 Sharpe 算法。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

import pandas as pd

from models.analysis import ResearchPeriod
from models.market import NavPeriod
from services import alignment, fund_service, market_service

logger = logging.getLogger(__name__)

PERIOD_DAYS = {
    ResearchPeriod.ONE_MONTH: 30,
    ResearchPeriod.THREE_MONTH: 90,
    ResearchPeriod.SIX_MONTH: 180,
    ResearchPeriod.ONE_YEAR: 365,
    ResearchPeriod.THREE_YEAR: 1095,
}
REFERENCE_BENCHMARK = "sh000300"
REFERENCE_BENCHMARK_NAME = "沪深300"
FUND_SOURCE = "东方财富基金历史净值（经 akshare 获取）"
BENCHMARK_SOURCE = "指数历史行情（经 akshare 获取）"


def clean_nav(raw: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """清洗研究用累计净值；拒绝单位净值或 ETF 市价替代。"""
    if raw is None or raw.empty or "累计净值" not in raw.columns:
        return pd.DataFrame(columns=["净值日期", "累计净值"]), 0, 0

    frame = raw.copy()
    frame["净值日期"] = pd.to_datetime(frame["净值日期"], errors="coerce")
    frame["累计净值"] = pd.to_numeric(frame["累计净值"], errors="coerce")
    invalid = int(
        (frame["净值日期"].isna() | frame["累计净值"].isna() | (frame["累计净值"] <= 0)).sum()
    )
    frame = frame.dropna(subset=["净值日期", "累计净值"])
    frame = frame[frame["累计净值"] > 0]
    duplicates = int(frame.duplicated(subset=["净值日期"], keep="last").sum())
    frame = (
        frame.drop_duplicates(subset=["净值日期"], keep="last")
        .sort_values("净值日期")
        .reset_index(drop=True)
    )
    return frame[["净值日期", "累计净值"]], duplicates, invalid


def _empty_metrics() -> dict:
    return {
        "period_return": None,
        "volatility": None,
        "max_drawdown": None,
        "sharpe": None,
    }


def _metric_status(sample_count: int) -> str:
    if sample_count >= 3:
        return "available"
    if sample_count == 2:
        return "partial"
    return "insufficient"


def overview(code: str, period: ResearchPeriod, as_of: date | None = None) -> dict:
    code = code.strip().upper()
    today = as_of or datetime.now().date()
    raw = fund_service.nav_history(code)
    cleaned, duplicate_dates, invalid_records = clean_nav(raw)

    cutoff = None
    if period != ResearchPeriod.ALL:
        cutoff = pd.Timestamp(today - timedelta(days=PERIOD_DAYS[period]))
    selected = cleaned if cutoff is None else cleaned[cleaned["净值日期"] >= cutoff]
    selected = selected.reset_index(drop=True)
    sample_count = len(selected)

    metrics = _empty_metrics()
    if sample_count >= 2:
        nav = selected["累计净值"].astype(float)
        metrics["period_return"] = round(float(nav.iloc[-1] / nav.iloc[0] - 1), 4)
    if sample_count >= 3:
        # 唯一的波动率、最大回撤、Sharpe 实现；本服务不重复定义金融公式。
        calculated = fund_service._metrics_from_nav(selected, "")
        metrics.update(
            volatility=calculated.volatility,
            max_drawdown=calculated.max_drawdown,
            sharpe=calculated.sharpe,
        )

    quality_notes: list[str] = []
    if duplicate_dates:
        quality_notes.append(f"发现 {duplicate_dates} 条重复日期记录，保留最后一条。")
    if invalid_records:
        quality_notes.append(f"剔除 {invalid_records} 条日期缺失或累计净值非正/缺失的记录。")
    data_as_of = selected["净值日期"].iloc[-1].date() if sample_count else None
    stale = bool(data_as_of and (today - data_as_of).days > 10)
    if stale:
        quality_notes.append("最新净值距研究日期超过 10 个自然日，请留意数据时效。")
    if not sample_count:
        quality_notes.append("所选区间没有有效累计净值，指标不可计算。")
    elif sample_count < 3:
        quality_notes.append("有效样本不足：至少需要 3 个累计净值点计算风险指标。")

    if not sample_count:
        quality_status = "missing"
    elif duplicate_dates or invalid_records:
        quality_status = "warning"
    elif stale:
        quality_status = "stale"
    else:
        quality_status = "normal"

    benchmark = {
        "code": REFERENCE_BENCHMARK,
        "name": REFERENCE_BENCHMARK_NAME,
        "status": "unavailable",
        "source": BENCHMARK_SOURCE,
        "period_return": None,
        "matched_samples": 0,
        "fund_only_dates": 0,
        "benchmark_only_dates": 0,
        "note": "沪深300仅作统一参考基准，不代表该基金合同约定的业绩比较基准。",
    }
    curve: list[dict] = []
    benchmark_frame = pd.DataFrame(columns=["净值日期", "close"])
    try:
        points = market_service.index_kline(REFERENCE_BENCHMARK, NavPeriod.DAILY)
        if points:
            benchmark_frame = pd.DataFrame(
                [{"净值日期": point.date, "close": point.close} for point in points]
            )
            benchmark_frame["净值日期"] = pd.to_datetime(
                benchmark_frame["净值日期"], errors="coerce"
            )
            benchmark_frame["close"] = pd.to_numeric(benchmark_frame["close"], errors="coerce")
            benchmark_frame = benchmark_frame.dropna()
            benchmark_frame = benchmark_frame[benchmark_frame["close"] > 0]
            if cutoff is not None:
                benchmark_frame = benchmark_frame[benchmark_frame["净值日期"] >= cutoff]
    except Exception as exc:  # 基准失败不应抹掉已经真实可得的基金指标
        logger.warning("Overview benchmark unavailable for %s: %s", code, type(exc).__name__)

    if sample_count and not benchmark_frame.empty:
        fund_series = pd.Series(
            selected["累计净值"].to_numpy(), index=pd.to_datetime(selected["净值日期"])
        )
        benchmark_series = pd.Series(
            benchmark_frame["close"].to_numpy(),
            index=pd.to_datetime(benchmark_frame["净值日期"]),
        )
        counts = alignment.count_unmatched(fund_series, benchmark_series)
        aligned = alignment.align_fund_benchmark(selected, benchmark_frame, "close")
        benchmark.update(
            matched_samples=len(aligned),
            fund_only_dates=counts["left_only"],
            benchmark_only_dates=counts["right_only"],
        )
        if len(aligned) >= 2:
            fund_base = float(aligned["fund"].iloc[0])
            benchmark_base = float(aligned["benchmark"].iloc[0])
            curve = [
                {
                    "date": idx.date().isoformat(),
                    "fund": round(float(row.fund / fund_base), 6),
                    "benchmark": round(float(row.benchmark / benchmark_base), 6),
                }
                for idx, row in aligned.iterrows()
            ]
            benchmark["period_return"] = round(
                float(aligned["benchmark"].iloc[-1] / benchmark_base - 1), 4
            )
            benchmark["status"] = "available"
        else:
            benchmark["status"] = "insufficient"
            benchmark["note"] += " 所选区间共同交易日不足，未计算基准收益。"

    # 基准不可用时仍展示基金真实曲线，但不补造任何基准点。
    if sample_count >= 2 and not curve:
        base = float(selected["累计净值"].iloc[0])
        curve = [
            {
                "date": row["净值日期"].date().isoformat(),
                "fund": round(float(row["累计净值"] / base), 6),
                "benchmark": None,
            }
            for _, row in selected.iterrows()
        ]

    fund_name = code
    try:
        fund_name = next(
            (item.name for item in fund_service.list_all() if item.code == code), code
        )
    except Exception:
        # _ensure_exists 已在路由层校验；名称不可得时保留代码，不阻塞指标。
        pass

    return {
        "code": code,
        "name": fund_name,
        "period": period.value,
        "data_start": selected["净值日期"].iloc[0].date().isoformat() if sample_count else None,
        "data_end": data_as_of.isoformat() if data_as_of else None,
        "sample_count": sample_count,
        "metric_status": _metric_status(sample_count),
        "metrics": metrics,
        "curve": curve,
        "benchmark": benchmark,
        "quality_status": quality_status,
        "quality_notes": quality_notes,
        "duplicate_dates": duplicate_dates,
        "invalid_nav_records": invalid_records,
        "source": FUND_SOURCE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
