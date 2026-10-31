"""回归测试：`_call_akshare` 超时信息保留 + 全量净值超时放宽。

条目 2 数据可靠性审计（2026-10-26）发现：超时抛出的 TimeoutError 本身
无消息，日志里失败原因为空，无法定位是超时还是上游报错；且默认 3 秒
对“成立来”全量净值偏紧。2026-10-31 用户批准全部修后落地：
超时异常带调用名与 `timeout after Xs`；上游异常原样透传（与超时可
区分）；只有 `_fetch_nav_history` 的两路全量调用放宽到 15 秒。
"""

import time
from unittest.mock import patch

import pandas as pd
import pytest

from services import fund_service


def _slow_callable():
    time.sleep(2)
    return "never"


def _boom_callable():
    raise RuntimeError("upstream exploded")


def test_timeout_error_carries_call_name_and_seconds():
    with pytest.raises(TimeoutError) as excinfo:
        fund_service._call_akshare(_slow_callable, timeout=1)
    message = str(excinfo.value)
    assert "_slow_callable" in message
    assert "timeout after 1s" in message


def test_upstream_exception_propagates_unchanged_not_as_timeout():
    with pytest.raises(RuntimeError, match="upstream exploded"):
        fund_service._call_akshare(_boom_callable, timeout=5)


def test_success_within_timeout_returns_value():
    assert fund_service._call_akshare(lambda: 42, timeout=5) == 42


def test_nav_history_calls_use_widened_timeout_only_there():
    recorded: list[int | None] = []

    def _recorder(func, *args, **kwargs):
        recorded.append(kwargs.get("timeout"))
        if kwargs.get("indicator") == "累计净值走势":
            return pd.DataFrame(
                [("2026-01-02", 1.10), ("2026-01-05", 1.11)],
                columns=["净值日期", "累计净值"],
            )
        return pd.DataFrame(
            [("2026-01-02", 1.00, 0.10), ("2026-01-05", 1.01, 0.20)],
            columns=["净值日期", "单位净值", "日增长率"],
        )

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service, "_call_akshare", side_effect=_recorder
    ):
        frame = fund_service._fetch_nav_history("000001")

    assert len(frame) == 2
    assert recorded == [fund_service._NAV_HISTORY_TIMEOUT] * 2
    assert fund_service._NAV_HISTORY_TIMEOUT > fund_service._AKSHARE_TIMEOUT
