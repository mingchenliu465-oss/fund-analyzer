"""回归测试：单位净值侧重复日期必须去重，与累计净值侧对齐。

条目 2 数据可靠性审计（2026-10-26）发现：`_fetch_nav_history` 里累计
净值侧有 `drop_duplicates(keep="last")`，单位净值侧没有；上游若返回
重复日期，merge 会放大行数。2026-10-31 用户批准全部修后对齐两侧。
"""

from unittest.mock import patch

import pandas as pd

from services import fund_service


def _frames(unit_rows, cum_rows):
    def _fake(*args, **kwargs):
        if kwargs.get("indicator") == "累计净值走势":
            return pd.DataFrame(cum_rows, columns=["净值日期", "累计净值"])
        return pd.DataFrame(unit_rows, columns=["净值日期", "单位净值", "日增长率"])

    return _fake


def _fetch(unit_rows, cum_rows):
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_open_fund_info_em", side_effect=_frames(unit_rows, cum_rows)
    ):
        return fund_service._fetch_nav_history("000001")


def test_duplicate_unit_dates_do_not_amplify_rows_and_last_wins():
    unit_rows = [
        ("2026-01-02", 1.00, 0.10),
        ("2026-01-05", 1.01, 0.20),  # 同日旧值
        ("2026-01-05", 1.09, 0.99),  # 同日最后一行才算数
    ]
    cum_rows = [("2026-01-02", 1.10), ("2026-01-05", 1.11)]
    frame = _fetch(unit_rows, cum_rows)

    assert len(frame) == 2  # 行数不被重复日期放大
    by_date = frame.set_index(frame["净值日期"].dt.strftime("%Y-%m-%d"))
    assert by_date.loc["2026-01-05", "单位净值"] == 1.09
    assert by_date.loc["2026-01-05", "累计净值"] == 1.11


def test_duplicate_cumulative_dates_last_wins_regression():
    unit_rows = [("2026-01-02", 1.00, 0.10), ("2026-01-05", 1.01, 0.20)]
    cum_rows = [
        ("2026-01-02", 1.10),
        ("2026-01-05", 1.11),  # 同日旧值
        ("2026-01-05", 1.19),  # 同日最后一行才算数
    ]
    frame = _fetch(unit_rows, cum_rows)

    assert len(frame) == 2
    by_date = frame.set_index(frame["净值日期"].dt.strftime("%Y-%m-%d"))
    assert by_date.loc["2026-01-05", "累计净值"] == 1.19
