"""基金—基准逐日对齐（alignment）的单元测试。

对齐只允许内连接：单侧缺失的日期剔除并可计数，绝不填充或插值。
"""

import pandas as pd
import pytest

from services import alignment


def _series(pairs):
    return pd.Series(
        [p[1] for p in pairs],
        index=pd.to_datetime([p[0] for p in pairs]),
    )


def test_align_keeps_only_common_dates():
    left = _series([("2024-01-02", 1.0), ("2024-01-03", 2.0), ("2024-01-04", 3.0)])
    right = _series([("2024-01-03", 20.0), ("2024-01-04", 30.0), ("2024-01-05", 40.0)])
    aligned = alignment.align_series(left, right)
    assert [d.strftime("%Y-%m-%d") for d in aligned.index] == ["2024-01-03", "2024-01-04"]
    assert list(aligned["left"]) == [2.0, 3.0]
    assert list(aligned["right"]) == [20.0, 30.0]


def test_align_sorts_unsorted_input_and_dedupes_last():
    left = _series([("2024-01-03", 2.0), ("2024-01-02", 1.0), ("2024-01-03", 2.5)])
    right = _series([("2024-01-02", 10.0), ("2024-01-03", 20.0)])
    aligned = alignment.align_series(left, right)
    assert list(aligned["left"]) == [1.0, 2.5]


def test_align_drops_nan_pairs():
    left = _series([("2024-01-02", 1.0), ("2024-01-03", float("nan"))])
    right = _series([("2024-01-02", 10.0), ("2024-01-03", 20.0)])
    aligned = alignment.align_series(left, right)
    assert len(aligned) == 1


def test_align_empty_intersection():
    left = _series([("2024-01-02", 1.0)])
    right = _series([("2024-02-02", 10.0)])
    assert alignment.align_series(left, right).empty


def test_count_unmatched():
    left = _series([("2024-01-02", 1.0), ("2024-01-03", 2.0), ("2024-01-04", 3.0)])
    right = _series([("2024-01-03", 20.0), ("2024-01-05", 50.0)])
    assert alignment.count_unmatched(left, right) == {
        "left_only": 2,
        "right_only": 1,
        "matched": 1,
    }


def test_align_fund_benchmark_uses_cumulative_nav():
    nav = pd.DataFrame(
        {
            "净值日期": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "单位净值": [0.9, 0.8],
            "累计净值": [1.5, 1.65],
        }
    )
    bench = pd.DataFrame(
        {
            "净值日期": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "close": [3000.0, 3030.0],
        }
    )
    aligned = alignment.align_fund_benchmark(nav, bench, benchmark_col="close")
    assert list(aligned["fund"]) == [1.5, 1.65]
    assert list(aligned["benchmark"]) == [3000.0, 3030.0]


def test_align_fund_benchmark_rejects_unit_nav_only():
    nav = pd.DataFrame({"净值日期": pd.to_datetime(["2024-01-02"]), "单位净值": [0.9]})
    bench = pd.DataFrame({"净值日期": pd.to_datetime(["2024-01-02"]), "close": [3000.0]})
    with pytest.raises(ValueError):
        alignment.align_fund_benchmark(nav, bench, benchmark_col="close")
