"""统计诊断必须保留累计净值口径，且只能标记异常数据。"""

from unittest.mock import patch

import numpy as np
import pandas as pd

from models.market import NavPeriod
from services import analysis_service


def _nav_frame(cumulative: list[float], unit: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp.now().normalize(), periods=len(cumulative), freq="B")
    return pd.DataFrame({
        "净值日期": dates,
        "单位净值": unit if unit is not None else cumulative,
        "累计净值": cumulative,
        "日增长率": [0.0] * len(cumulative),
    })


def test_audit_uses_cumulative_nav_and_only_flags_outliers():
    cumulative = list(np.linspace(1.0, 1.05, 30)) + [1.30] + list(np.linspace(1.31, 1.36, 20))
    # 单位净值模拟除息跳变；若错误使用它，会产生额外的假异常。
    unit = cumulative.copy()
    unit[20] = 0.5
    with patch.object(analysis_service.fund_service, "nav_history", return_value=_nav_frame(cumulative, unit)):
        result = analysis_service.statistics_audit("000001", NavPeriod.ONE_YEAR)

    assert result.observations == len(cumulative)
    assert result.valid_returns == len(cumulative) - 1
    assert result.outliers
    assert all(item.date != _nav_frame(cumulative, unit).iloc[20]["净值日期"].strftime("%Y-%m-%d") for item in result.outliers)
    assert result.volatility_ci is not None


def test_audit_is_reproducible_and_reports_insufficient_history():
    frame = _nav_frame(list(np.linspace(1.0, 1.10, 25)))
    with patch.object(analysis_service.fund_service, "nav_history", return_value=frame):
        first = analysis_service.statistics_audit("000001")
        second = analysis_service.statistics_audit("000001")

    assert first.volatility_ci == second.volatility_ci

    with patch.object(analysis_service.fund_service, "nav_history", return_value=_nav_frame([1.0, 1.01, 1.02])):
        short = analysis_service.statistics_audit("000001")

    assert short.status == "available"
    assert short.volatility_ci is None
    assert any("少于 20" in note for note in short.notes)
