"""回归测试：净值入口对非正净值（<= 0）的校验。

条目 2 数据可靠性审计的落地项：`_fetch_nav_history` 此前只丢弃缺失行，
0 / 负净值会原样进入净值帧。下游防御并不一致——回测引擎在消费端单独过滤
非正值，但详情页的 `_metrics_from_nav` 完全没有正值防线，0 会让收益率除法
产生 inf、无意义结果。因此在共享入口处统一丢弃非正行并记录条数。

测试用 mock 的 akshare 帧覆盖三种情形：混有脏行的正常序列、全是脏行、
全是干净行（回归：干净行必须原样通过）。
"""

from unittest.mock import patch

import pandas as pd

from services import fund_service


def _frames(unit_rows, cum_rows):
    """按 indicator 分发两路 mock 帧。"""

    def _fake(*args, **kwargs):
        if kwargs.get("indicator") == "累计净值走势":
            return pd.DataFrame(cum_rows, columns=["净值日期", "累计净值"])
        return pd.DataFrame(
            unit_rows, columns=["净值日期", "单位净值", "日增长率"]
        )

    return _fake


def test_nonpositive_nav_rows_are_dropped_not_passed_through():
    """0 与负净值行被丢弃，干净行保留，累计净值与日期对齐。"""
    unit_rows = [
        ("2026-01-02", 1.00, 0.10),
        ("2026-01-05", 0.00, 0.00),  # 零单位净值：脏行
        ("2026-01-06", -0.50, -50.0),  # 负单位净值：脏行
        ("2026-01-07", 1.02, 0.50),
    ]
    cum_rows = [
        ("2026-01-02", 1.10),
        ("2026-01-05", 1.11),
        ("2026-01-06", -2.00),  # 负累计净值：脏行
        ("2026-01-07", 1.15),
    ]
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_open_fund_info_em", side_effect=_frames(unit_rows, cum_rows)
    ):
        frame = fund_service._fetch_nav_history("000001")

    assert list(frame["净值日期"].dt.strftime("%Y-%m-%d")) == ["2026-01-02", "2026-01-07"]
    assert (frame["单位净值"] > 0).all()
    assert (frame["累计净值"] > 0).all()
    assert list(frame["累计净值"]) == [1.10, 1.15]


def test_all_nonpositive_nav_returns_empty_frame_not_crash():
    """全是脏行时返回空的同构帧，不抛错、不生成替代序列。"""
    unit_rows = [("2026-01-02", 0.00, 0.0), ("2026-01-05", -1.00, -1.0)]
    cum_rows = [("2026-01-02", 0.00), ("2026-01-05", -1.00)]
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_open_fund_info_em", side_effect=_frames(unit_rows, cum_rows)
    ):
        frame = fund_service._fetch_nav_history("000001")

    assert frame.empty
    assert list(frame.columns) == fund_service._NAV_COLUMNS


def test_clean_nav_rows_pass_through_unchanged():
    """干净行回归：过滤不得改动正常序列的值与顺序。"""
    unit_rows = [
        ("2026-01-02", 1.00, 0.10),
        ("2026-01-05", 1.01, 0.20),
        ("2026-01-06", 1.03, 0.30),
    ]
    cum_rows = [("2026-01-02", 1.10), ("2026-01-05", 1.11), ("2026-01-06", 1.13)]
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_open_fund_info_em", side_effect=_frames(unit_rows, cum_rows)
    ):
        frame = fund_service._fetch_nav_history("000001")

    assert len(frame) == 3
    assert list(frame["单位净值"]) == [1.00, 1.01, 1.03]
    assert list(frame["累计净值"]) == [1.10, 1.11, 1.13]
