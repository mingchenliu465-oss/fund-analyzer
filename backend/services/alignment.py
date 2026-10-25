"""基金净值与基准序列的逐日对齐工具。

回测与基准对比的前提是两条序列按同一组交易日逐点对应：基金停牌、节假日、
指数与基金的交易日历并不完全一致，硬按行号拼接会把不同日期的数值配成一对，
算出的超额收益是假的。这里只做内连接对齐：只保留两边都有真实数值的日期，
缺失的一律剔除并可计数，不前向填充、不插值、不编造。
"""

from __future__ import annotations

import pandas as pd

DATE_COL = "净值日期"


def align_series(left: pd.Series, right: pd.Series) -> pd.DataFrame:
    """把两条以日期为索引的序列按日期内连接对齐。

    - 输入索引可无序，内部统一转为 DatetimeIndex 并排序；
    - 同一日期多条时保留最后一条（与净值落库的去重口径一致）；
    - 任一侧为 NaN 的日期整行剔除；
    - 返回 DataFrame：索引为日期（name="date"），列为 ["left", "right"]。
    """
    def _clean(s: pd.Series) -> pd.Series:
        s = s.copy()
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s[~s.index.isna()]
        s = pd.to_numeric(s, errors="coerce")
        s = s[~s.index.duplicated(keep="last")].sort_index()
        return s

    left_clean = _clean(left)
    right_clean = _clean(right)
    merged = pd.DataFrame({"left": left_clean, "right": right_clean}).dropna()
    merged.index.name = "date"
    return merged


def count_unmatched(left: pd.Series, right: pd.Series) -> dict[str, int]:
    """统计对齐时被剔除的日期数（只出现在单侧的日期个数），供报告披露。"""
    def _dates(s: pd.Series) -> set:
        idx = pd.to_datetime(pd.Index(s.index), errors="coerce")
        return set(idx[~idx.isna()])

    left_dates, right_dates = _dates(left), _dates(right)
    return {
        "left_only": len(left_dates - right_dates),
        "right_only": len(right_dates - left_dates),
        "matched": len(left_dates & right_dates),
    }


def align_fund_benchmark(
    nav_frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    benchmark_col: str,
    benchmark_date_col: str = DATE_COL,
) -> pd.DataFrame:
    """把基金净值帧（净值日期 + 累计净值）与基准帧按日对齐。

    基金侧固定使用累计净值（收益口径纪律，不接受单位净值替代）。
    返回 DataFrame：索引 date，列 ["fund", "benchmark"]。
    """
    if "累计净值" not in nav_frame.columns:
        raise ValueError("基金净值帧缺少累计净值列，拒绝用单位净值替代对齐")
    fund_series = pd.Series(
        nav_frame["累计净值"].to_numpy(), index=pd.to_datetime(nav_frame[DATE_COL])
    )
    bench_series = pd.Series(
        benchmark_frame[benchmark_col].to_numpy(),
        index=pd.to_datetime(benchmark_frame[benchmark_date_col]),
    )
    aligned = align_series(fund_series, bench_series)
    return aligned.rename(columns={"left": "fund", "right": "benchmark"})
