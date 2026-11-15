"""Performance、Risk 与 Data Audit 的共享研究计算。

所有收益序列来自真实累计净值；风险指标继续复用 overview 中的既有指标实现。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import math

import numpy as np
import pandas as pd

from models.analysis import ResearchPeriod
from services import fund_service, overview_service

ALL_PERIODS = [
    ResearchPeriod.ONE_MONTH,
    ResearchPeriod.THREE_MONTH,
    ResearchPeriod.SIX_MONTH,
    ResearchPeriod.ONE_YEAR,
    ResearchPeriod.THREE_YEAR,
    ResearchPeriod.ALL,
]
RISK_FREE_DAILY = 0.02 / 252


def select_nav(
    code: str, period: ResearchPeriod, as_of: date | None = None
) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """返回所选区间、完整清洗历史及质量计数。"""
    raw = fund_service.nav_history(code)
    cleaned, duplicates, invalid = overview_service.clean_nav(raw)
    if period == ResearchPeriod.ALL:
        return cleaned.copy(), cleaned, duplicates, invalid
    today = as_of or datetime.now().date()
    cutoff = pd.Timestamp(today - timedelta(days=overview_service.PERIOD_DAYS[period]))
    return cleaned[cleaned["净值日期"] >= cutoff].reset_index(drop=True), cleaned, duplicates, invalid


def annualized_return(frame: pd.DataFrame) -> float | None:
    """按真实首末日期做几何年化；不足两个不同日期时不可计算。"""
    if len(frame) < 2:
        return None
    days = int((frame["净值日期"].iloc[-1] - frame["净值日期"].iloc[0]).days)
    if days <= 0:
        return None
    first, last = float(frame["累计净值"].iloc[0]), float(frame["累计净值"].iloc[-1])
    if first <= 0 or last <= 0:
        return None
    return round(float((last / first) ** (365.25 / days) - 1), 4)


def _calendar_returns(frame: pd.DataFrame, frequency: str, as_of: date) -> list[dict]:
    if len(frame) < 2:
        return []
    work = frame.copy().reset_index(drop=True)
    work["group"] = work["净值日期"].dt.strftime("%Y" if frequency == "year" else "%Y-%m")
    groups = list(work.groupby("group", sort=True))
    results: list[dict] = []
    previous_last: float | None = None
    for label, group in groups:
        first = group.iloc[0]
        last = group.iloc[-1]
        base = previous_last if previous_last is not None else float(first["累计净值"])
        value = None
        if base > 0 and (previous_last is not None or len(group) >= 2):
            value = round(float(float(last["累计净值"]) / base - 1), 4)
        is_current = (
            int(label[:4]) == as_of.year
            if frequency == "year"
            else label == as_of.strftime("%Y-%m")
        )
        results.append(
            {
                "label": label,
                "return": value,
                "start_date": first["净值日期"].date().isoformat(),
                "end_date": last["净值日期"].date().isoformat(),
                "observations": len(group),
                "is_partial": previous_last is None or is_current,
            }
        )
        previous_last = float(last["累计净值"])
    return results


def performance(code: str, period: ResearchPeriod, as_of: date | None = None) -> dict:
    today = as_of or datetime.now().date()
    base = overview_service.overview(code, period, today)
    selected, _, _, _ = select_nav(code, period, today)
    annualized = annualized_return(selected)
    fund_return = base["metrics"]["period_return"]
    benchmark_return = base["benchmark"]["period_return"]
    excess = (
        round(fund_return - benchmark_return, 4)
        if fund_return is not None and benchmark_return is not None
        else None
    )

    comparisons = []
    for item_period in ALL_PERIODS:
        item = overview_service.overview(code, item_period, today)
        item_selected, _, _, _ = select_nav(code, item_period, today)
        item_fund = item["metrics"]["period_return"]
        item_benchmark = item["benchmark"]["period_return"]
        comparisons.append(
            {
                "period": item_period.value,
                "status": item["metric_status"],
                "sample_count": item["sample_count"],
                "fund_return": item_fund,
                "annualized_return": annualized_return(item_selected),
                "benchmark_return": item_benchmark,
                "excess_return": (
                    round(item_fund - item_benchmark, 4)
                    if item_fund is not None and item_benchmark is not None
                    else None
                ),
            }
        )

    return {
        "code": base["code"],
        "name": base["name"],
        "period": period.value,
        "metric_status": base["metric_status"],
        "metrics": {
            "period_return": fund_return,
            "annualized_return": annualized,
            "benchmark_return": benchmark_return,
            "excess_return": excess,
        },
        "curve": base["curve"],
        "annual_returns": _calendar_returns(selected, "year", today),
        "monthly_returns": _calendar_returns(selected, "month", today),
        "period_comparisons": comparisons,
        "coverage": {
            "data_start": base["data_start"],
            "data_end": base["data_end"],
            "sample_count": base["sample_count"],
            "matched_samples": base["benchmark"]["matched_samples"],
            "quality_status": base["quality_status"],
        },
        "source": base["source"],
        "benchmark_source": base["benchmark"]["source"],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "definitions": [
            "区间累计收益 = 区间末累计净值 / 区间初累计净值 - 1。",
            "年化收益按首末真实日期做几何年化，365.25 天为一年；短区间年化不代表全年实际收益。",
            "超额收益 = 基金区间收益 - 沪深300参考基准共同日期收益，不是基金合同基准超额。",
            "自然年/月首期若没有上一期期末基准，则仅计算所选区间内的收益并标记为不完整。",
        ],
    }


def downside_deviation(nav: pd.Series) -> float | None:
    """下行偏差：负超额收益对全部收益样本取均方，252 日年化。"""
    values = pd.to_numeric(nav, errors="coerce").dropna().astype(float).to_numpy()
    if len(values) < 3 or np.any(values <= 0):
        return None
    returns = values[1:] / values[:-1] - 1
    downside = np.minimum(returns - RISK_FREE_DAILY, 0)
    return round(float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(252)), 4)


def _drawdown_details(frame: pd.DataFrame) -> dict:
    empty = {
        "peak_date": None,
        "trough_date": None,
        "recovery_date": None,
        "drawdown_days": None,
        "recovery_days": None,
        "underwater_days": None,
        "recovery_status": "unavailable",
    }
    if len(frame) < 2:
        return empty
    dates = pd.to_datetime(frame["净值日期"]).reset_index(drop=True)
    nav = pd.to_numeric(frame["累计净值"], errors="coerce").reset_index(drop=True)
    running_peak = nav.cummax()
    drawdown = nav / running_peak - 1
    trough_position = int(drawdown.idxmin())
    if float(drawdown.iloc[trough_position]) >= 0:
        return {**empty, "drawdown_days": 0, "recovery_days": 0, "underwater_days": 0, "recovery_status": "no_drawdown"}
    peak_position = int(nav.iloc[: trough_position + 1].idxmax())
    peak_value = float(nav.iloc[peak_position])
    recovered = nav.iloc[trough_position + 1 :]
    recovered = recovered[recovered >= peak_value]
    recovery_position = int(recovered.index[0]) if len(recovered) else None
    peak_date = dates.iloc[peak_position].date()
    trough_date = dates.iloc[trough_position].date()
    recovery_date = dates.iloc[recovery_position].date() if recovery_position is not None else None
    end_date = recovery_date or dates.iloc[-1].date()
    return {
        "peak_date": peak_date.isoformat(),
        "trough_date": trough_date.isoformat(),
        "recovery_date": recovery_date.isoformat() if recovery_date else None,
        "drawdown_days": (trough_date - peak_date).days,
        "recovery_days": (recovery_date - trough_date).days if recovery_date else None,
        "underwater_days": (end_date - peak_date).days,
        "recovery_status": "recovered" if recovery_date else "unrecovered",
    }


def _drawdown_curve(curve: list[dict]) -> list[dict]:
    if not curve:
        return []
    fund_peak = benchmark_peak = -math.inf
    points = []
    for point in curve:
        fund = float(point["fund"])
        benchmark = point.get("benchmark")
        fund_peak = max(fund_peak, fund)
        benchmark_peak = max(benchmark_peak, float(benchmark)) if benchmark is not None else benchmark_peak
        points.append(
            {
                "date": point["date"],
                "fund": round(fund / fund_peak - 1, 6),
                "benchmark": (
                    round(float(benchmark) / benchmark_peak - 1, 6)
                    if benchmark is not None
                    else None
                ),
            }
        )
    return points


def _series_risk(values: list[float]) -> dict:
    if len(values) < 3 or any(value <= 0 for value in values):
        return {"volatility": None, "max_drawdown": None, "sharpe": None, "downside_deviation": None}
    array = np.asarray(values, dtype=float)
    returns = array[1:] / array[:-1] - 1
    excess = returns - RISK_FREE_DAILY
    drawdown = array / np.maximum.accumulate(array) - 1
    downside = np.minimum(excess, 0)
    return {
        "volatility": round(float(returns.std() * np.sqrt(252)), 4),
        "max_drawdown": round(float(drawdown.min()), 4),
        "sharpe": (
            round(float(excess.mean() / excess.std() * np.sqrt(252)), 2)
            if excess.std() > 0
            else None
        ),
        "downside_deviation": round(float(np.sqrt(np.mean(np.square(downside))) * np.sqrt(252)), 4),
    }


def risk(code: str, period: ResearchPeriod, as_of: date | None = None) -> dict:
    today = as_of or datetime.now().date()
    base = overview_service.overview(code, period, today)
    selected, _, _, _ = select_nav(code, period, today)
    benchmark_values = [
        float(point["benchmark"]) for point in base["curve"] if point.get("benchmark") is not None
    ]
    benchmark_metrics = _series_risk(benchmark_values)

    changes = []
    for item_period in ALL_PERIODS:
        item = overview_service.overview(code, item_period, today)
        item_selected, _, _, _ = select_nav(code, item_period, today)
        changes.append(
            {
                "period": item_period.value,
                "status": item["metric_status"],
                "sample_count": item["sample_count"],
                "volatility": item["metrics"]["volatility"],
                "max_drawdown": item["metrics"]["max_drawdown"],
                "sharpe": item["metrics"]["sharpe"],
                "downside_deviation": (
                    downside_deviation(item_selected["累计净值"]) if len(item_selected) else None
                ),
            }
        )

    return {
        "code": base["code"],
        "name": base["name"],
        "period": period.value,
        "metric_status": base["metric_status"],
        "metrics": {**base["metrics"], "downside_deviation": downside_deviation(selected["累计净值"]) if len(selected) else None},
        "benchmark_metrics": benchmark_metrics,
        "drawdown": _drawdown_details(selected),
        "drawdown_curve": _drawdown_curve(base["curve"]),
        "period_comparisons": changes,
        "data_start": base["data_start"],
        "data_end": base["data_end"],
        "sample_count": base["sample_count"],
        "source": base["source"],
        "benchmark_source": base["benchmark"]["source"],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "definitions": [
            "波动率 = 累计净值日收益率总体标准差 × √252。",
            "Sharpe 使用年化 2% 无风险利率，先折算为日利率，再按 252 个交易日年化。",
            "下行风险仅惩罚低于日无风险利率的收益，但对全部收益样本取均方后年化。",
            "最大回撤是净值相对历史峰值的最大跌幅；回撤持续与恢复时间是不同概念。",
            "尚未回到前高时恢复时间为 null，水下天数统计至区间末，不假设未来恢复。",
        ],
    }


def data_audit(code: str, period: ResearchPeriod, as_of: date | None = None) -> dict:
    today = as_of or datetime.now().date()
    raw = fund_service.nav_history(code)
    if raw is None:
        raw = pd.DataFrame()
    frame = raw.copy()
    if "净值日期" not in frame.columns:
        frame["净值日期"] = pd.NaT
    frame["净值日期"] = pd.to_datetime(frame["净值日期"], errors="coerce")
    if period != ResearchPeriod.ALL:
        cutoff = pd.Timestamp(today - timedelta(days=overview_service.PERIOD_DAYS[period]))
        frame = frame[frame["净值日期"] >= cutoff]
    frame = frame.sort_values("净值日期").reset_index(drop=True)
    for column in ["单位净值", "累计净值"]:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    valid_dates = frame.dropna(subset=["净值日期"])
    data_start = valid_dates["净值日期"].min()
    data_end = valid_dates["净值日期"].max()
    duplicate_dates = int(valid_dates.duplicated(subset=["净值日期"], keep="last").sum())
    missing_unit = int(valid_dates["单位净值"].isna().sum())
    missing_cumulative = int(valid_dates["累计净值"].isna().sum())
    non_positive_unit = int((valid_dates["单位净值"].dropna() <= 0).sum())
    non_positive_cumulative = int((valid_dates["累计净值"].dropna() <= 0).sum())

    missing_dates: list[str] = []
    expected_days = observed_days = longest_gap = 0
    if pd.notna(data_start) and pd.notna(data_end):
        calendar = {
            pd.Timestamp(item).date()
            for item in fund_service._trade_calendar()
            if data_start.date() <= pd.Timestamp(item).date() <= data_end.date()
        }
        observed = set(valid_dates["净值日期"].dt.date)
        expected = sorted(calendar)
        missing = sorted(calendar - observed)
        missing_dates = [item.isoformat() for item in missing[:20]]
        expected_days = len(expected)
        observed_days = len(calendar & observed)
        run = 0
        for item in expected:
            run = run + 1 if item in missing else 0
            longest_gap = max(longest_gap, run)

    cleaned, _, _ = overview_service.clean_nav(valid_dates)
    extreme_moves = []
    if len(cleaned) >= 2:
        returns = cleaned["累计净值"].pct_change()
        for idx in cleaned.index[returns.abs() >= 0.1]:
            extreme_moves.append(
                {
                    "date": cleaned.loc[idx, "净值日期"].date().isoformat(),
                    "return": round(float(returns.loc[idx]), 4),
                    "note": "累计净值单日绝对变动达到 10%，需结合分红、拆分或市场事件核验。",
                }
            )

    pairs = valid_dates.dropna(subset=["净值日期", "单位净值", "累计净值"]).copy()
    pairs = pairs[(pairs["单位净值"] > 0) & (pairs["累计净值"] > 0)]
    pairs = pairs.drop_duplicates(subset=["净值日期"], keep="last").sort_values("净值日期")
    distribution_candidates = []
    if len(pairs) >= 2:
        unit_changes = pairs["单位净值"].diff()
        cumulative_changes = pairs["累计净值"].diff()
        # 无权益事件时：累计净值 = 单位净值 + 固定累计分红，二者的绝对变动应一致。
        # 不能直接比较百分比收益：两者基数不同，普通波动也会产生不同收益率。
        gaps = (cumulative_changes - unit_changes).abs()
        for idx in pairs.index[gaps >= 0.005]:
            distribution_candidates.append(
                {
                    "date": pairs.loc[idx, "净值日期"].date().isoformat(),
                    "unit_change": round(float(unit_changes.loc[idx]), 4),
                    "cumulative_change": round(float(cumulative_changes.loc[idx]), 4),
                    "difference": round(float(cumulative_changes.loc[idx] - unit_changes.loc[idx]), 4),
                    "status": "unverified",
                }
            )

    freshness_days = (today - data_end.date()).days if pd.notna(data_end) else None
    coverage_ratio = observed_days / expected_days if expected_days else None
    checks = [
        {
            "key": "source",
            "label": "来源与覆盖",
            "status": "normal" if len(valid_dates) else "missing",
            "detail": f"东方财富基金历史净值（经 akshare 获取）；{len(valid_dates)} 条区间记录。",
        },
        {
            "key": "freshness",
            "label": "数据更新时间",
            "status": "missing" if freshness_days is None else ("warning" if freshness_days > 10 else "normal"),
            "detail": f"最新净值日期 {data_end.date().isoformat() if pd.notna(data_end) else '—'}；距研究日期 {freshness_days if freshness_days is not None else '—'} 天。",
        },
        {
            "key": "duplicates",
            "label": "重复记录",
            "status": "warning" if duplicate_dates else "normal",
            "detail": f"发现 {duplicate_dates} 条重复日期；指标计算保留原始顺序中的最后一条。",
        },
        {
            "key": "nav_validity",
            "label": "异常净值",
            "status": "abnormal" if non_positive_unit or non_positive_cumulative else "normal",
            "detail": f"单位净值缺失/非正：{missing_unit}/{non_positive_unit}；累计净值缺失/非正：{missing_cumulative}/{non_positive_cumulative}；极端变动 {len(extreme_moves)} 条。",
        },
        {
            "key": "continuity",
            "label": "交易日连续性",
            "status": "missing" if not expected_days else ("abnormal" if coverage_ratio is not None and coverage_ratio < 0.9 else ("warning" if expected_days != observed_days else "normal")),
            "detail": f"交易日历覆盖 {observed_days}/{expected_days}；缺失 {max(expected_days - observed_days, 0)} 日，最长连续缺失 {longest_gap} 个交易日。缺口不自动等同于错误。",
        },
        {
            "key": "nav_consistency",
            "label": "单位净值与累计净值",
            "status": "missing" if not len(pairs) else ("warning" if distribution_candidates else "normal"),
            "detail": f"可配对记录 {len(pairs)} 条；单位净值与累计净值每日变动差异达到 0.005 个净值单位的记录 {len(distribution_candidates)} 条。",
        },
        {
            "key": "distributions",
            "label": "分红与复权",
            "status": "unverified",
            "detail": "净值变动差异仅作为可能的分红、拆分或复权线索；没有官方权益事件数据时不确认事件性质。",
        },
        {
            "key": "cross_source",
            "label": "跨数据源差异",
            "status": "unverified",
            "detail": "第二独立累计净值数据源尚未完成权限与口径验证，本项不做已交叉验证声明。",
        },
    ]
    statuses = {check["status"] for check in checks}
    overall = (
        "abnormal"
        if "abnormal" in statuses or "missing" in statuses
        else ("warning" if "warning" in statuses else ("unverified" if "unverified" in statuses else "normal"))
    )
    return {
        "code": code.strip().upper(),
        "period": period.value,
        "overall_status": overall,
        "data_start": data_start.date().isoformat() if pd.notna(data_start) else None,
        "data_end": data_end.date().isoformat() if pd.notna(data_end) else None,
        "record_count": len(valid_dates),
        "source": overview_service.FUND_SOURCE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "checks": checks,
        "missing_dates": missing_dates,
        "coverage_ratio": round(coverage_ratio, 4) if coverage_ratio is not None else None,
        "extreme_moves": extreme_moves[:50],
        "distribution_candidates": distribution_candidates[:50],
        "notes": [
            "审计结论只针对当前来源和所选区间，不代表基金合同、公告或托管数据的法律核验。",
            "单位净值用于一致性检查；收益、波动率、回撤和 Sharpe 仍只使用累计净值。",
            "缺失日期展示前 20 项，极端变动和复权候选展示前 50 项。",
        ],
    }
