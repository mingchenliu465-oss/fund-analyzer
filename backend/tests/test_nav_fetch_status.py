"""回归测试：净值取数的“空”必须在服务层可区分——无数据 vs 瞬时失败。

条目 2 数据可靠性审计（2026-10-26）发现：`_fetch_nav_history` 在任何
异常时都返回与“无数据”同构的空帧，调用方无法区分该重试还是该放弃。
2026-10-31 用户批准全部修后落地最小区分：对外契约不变（仍返空帧），
但每次取数结局记入 `last_nav_fetch_status()`——ok / empty / failed，
failed 带异常类型与消息（超时消息含 timeout after Xs，可定位原因）。
"""

from unittest.mock import patch

import pandas as pd

from services import fund_service

_CLEAN = dict(
    unit_rows=[("2026-01-02", 1.00, 0.10), ("2026-01-05", 1.01, 0.20)],
    cum_rows=[("2026-01-02", 1.10), ("2026-01-05", 1.11)],
)
_DIRTY_ONLY = dict(
    unit_rows=[("2026-01-02", 0.00, 0.0), ("2026-01-05", -1.00, -1.0)],
    cum_rows=[("2026-01-02", 0.00), ("2026-01-05", -1.00)],
)


def _frames(unit_rows, cum_rows):
    def _fake(*args, **kwargs):
        if kwargs.get("indicator") == "累计净值走势":
            return pd.DataFrame(cum_rows, columns=["净值日期", "累计净值"])
        return pd.DataFrame(unit_rows, columns=["净值日期", "单位净值", "日增长率"])

    return _fake


def _fetch_with_ak(side_effect):
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_open_fund_info_em", side_effect=side_effect
    ):
        return fund_service._fetch_nav_history("000001")


def test_successful_fetch_records_ok():
    frame = _fetch_with_ak(_frames(**_CLEAN))
    assert len(frame) == 2
    status = fund_service.last_nav_fetch_status("000001")
    assert status["status"] == "ok"
    assert status["reason"] is None


def test_upstream_returning_no_usable_rows_records_empty_not_failed():
    frame = _fetch_with_ak(_frames(**_DIRTY_ONLY))
    assert frame.empty  # 对外契约不变：仍是空帧
    status = fund_service.last_nav_fetch_status("000001")
    assert status["status"] == "empty"
    assert status["reason"] is None


def test_upstream_exception_records_failed_with_reason():
    frame = _fetch_with_ak(RuntimeError("upstream exploded"))
    assert frame.empty  # 对外契约不变：仍是空帧
    status = fund_service.last_nav_fetch_status("000001")
    assert status["status"] == "failed"
    assert "upstream exploded" in (status["reason"] or "")


def test_upstream_timeout_records_failed_with_timeout_reason():
    timeout = TimeoutError("akshare call fund_open_fund_info_em timeout after 15s")
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service, "_call_akshare", side_effect=timeout
    ):
        frame = fund_service._fetch_nav_history("000001")
    assert frame.empty
    status = fund_service.last_nav_fetch_status("000001")
    assert status["status"] == "failed"
    assert "timeout after 15s" in (status["reason"] or "")


def test_status_for_other_code_is_unknown_not_misattributed():
    _fetch_with_ak(RuntimeError("upstream exploded"))
    status = fund_service.last_nav_fetch_status("999999")
    assert status["status"] == "unknown"
