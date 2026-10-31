"""回归测试：Bug A —— `_metrics_from_nav` 的正值/有限值防线。

条目 3 计算边界审计（2026-10-28）实测：脏序列会让 `_metrics_from_nav`
产出最大回撤 -2.0（回撤不可能低于 -100%）、波动率 nan 却标风险“高”等
假指标。当时只记录未修；2026-10-31 用户批准全部修后落地本防线：
累计净值不全为有限正数时抛 ValueError（由既有调用链转成详情接口的
明确错误返回，不产出指标、也不变 500）；`risk_level_from_volatility`
对非有限波动率返 None。
"""

import math
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from services import fund_service


def _recent_dates(count: int) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]


def nav_frame(cumulative):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(_recent_dates(len(cumulative))),
            "单位净值": cumulative,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(cumulative),
        }
    )


@pytest.mark.parametrize(
    "values",
    [
        [0.0, 1.0, 1.1],  # 首点为 0：旧实现波动率 nan、风险标“高”
        [1.0, 0.0, 1.1],  # 中间为 0：旧实现最大回撤 -1.0
        [1.0, 1.1, 0.0],  # 尾点为 0
        [1.0, -1.0, 1.1],  # 负值：旧实现最大回撤 -2.0、夏普 -650.88
        [1.0, float("nan"), 1.1],  # NaN 混入
        [1.0, float("inf"), 1.1],  # inf 混入
    ],
)
def test_metrics_refuse_dirty_cumulative_nav(values):
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(nav_frame(values), "股票型")


def test_metrics_clean_sequence_still_computes():
    metrics = fund_service._metrics_from_nav(nav_frame([1.0, 1.1, 1.05, 1.2]), "股票型")
    assert math.isfinite(metrics.volatility)
    assert -1.0 <= metrics.max_drawdown <= 0.0
    assert metrics.risk_level is not None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), None])
def test_risk_level_from_non_finite_volatility_is_none(bad):
    assert fund_service.risk_level_from_volatility(bad) is None


def test_risk_level_from_finite_volatility_unchanged():
    assert fund_service.risk_level_from_volatility(0.03) == "低"
    assert fund_service.risk_level_from_volatility(0.30) == "高"


def test_get_by_code_refuses_dirty_nav_instead_of_fake_metrics():
    """详情入口遇到脏净值必须拒绝（ValueError -> 接口层明确错误），不拼假指标。"""
    summary = fund_service.FundSummary(
        code="000001", name="测试基金", company="测试公司", type="股票型",
        nav=1.0, nav_date=None, nav_status=None,
        change_pct=None, one_year_return=None, risk_level=None, size="-", heat=None,
    )
    with patch.object(fund_service, "_load_fund_list", return_value=[summary]), patch.object(
        fund_service, "_fetch_nav_history", return_value=nav_frame([0.0, 1.0, 1.1])
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        with pytest.raises(ValueError):
            fund_service.get_by_code("000001")
