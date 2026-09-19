"""NavPeriod 映射完整性测试。

历史缺陷：backend/api/fund.py 的 nav-history 路由内联了一份只有 5 个键的
period→天数 字典，且用 `[period]` 直接取值，没有默认值。NavPeriod 已有
12 个合法取值，因此传入 5D/10D/20D/日K/周K/月K/年K 都会抛 KeyError → 500。

这些测试保证：
1. 每个 NavPeriod 取值在所有映射中都有对应项（新增枚举值时会立即失败）；
2. period_to_days 对未知取值给出明确的 ValueError（而不是裸 KeyError）；
3. 该路由对每个合法周期都不会 500。
"""

from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import fund as fund_api
from models.market import PERIOD_DAYS, NavPeriod, period_to_days
from services import fund_service, market_service

ALL_PERIODS = list(NavPeriod)
ALL_PERIOD_VALUES = [p.value for p in NavPeriod]


def test_period_days_covers_every_nav_period():
    assert set(PERIOD_DAYS) == set(ALL_PERIODS), (
        "PERIOD_DAYS 与 NavPeriod 不一致："
        f"缺少 {set(ALL_PERIODS) - set(PERIOD_DAYS)}，多余 {set(PERIOD_DAYS) - set(ALL_PERIODS)}"
    )


def test_resample_rule_covers_every_nav_period():
    assert set(market_service.PERIOD_RESAMPLE_RULE) == set(ALL_PERIODS), (
        "PERIOD_RESAMPLE_RULE 与 NavPeriod 不一致："
        f"缺少 {set(ALL_PERIODS) - set(market_service.PERIOD_RESAMPLE_RULE)}，"
        f"多余 {set(market_service.PERIOD_RESAMPLE_RULE) - set(ALL_PERIODS)}"
    )


@pytest.mark.parametrize("period", ALL_PERIODS)
def test_period_to_days_supports_every_nav_period(period):
    assert period_to_days(period) > 0


def test_period_to_days_raises_value_error_for_unknown():
    with pytest.raises(ValueError):
        period_to_days("NOT_A_PERIOD")


@pytest.mark.parametrize("period_value", ALL_PERIOD_VALUES)
def test_nav_history_endpoint_never_500s_for_any_valid_period(period_value):
    """所有合法 NavPeriod 都必须正常返回，不能因映射缺项变成 500。"""
    app = FastAPI()
    app.include_router(fund_api.router, prefix="/api")

    nav = pd.DataFrame(
        {
            "净值日期": pd.to_datetime(["2000-01-03", "2000-01-04", "2000-01-05"]),
            "单位净值": [1.0, 1.1, 1.2],
            "日增长率": [0.0, 10.0, 9.09],
        }
    )
    with patch.object(fund_service, "nav_history", return_value=nav):
        with TestClient(app) as client:
            response = client.get(
                "/api/funds/000001/nav-history", params={"period": period_value}
            )
    assert response.status_code == 200, response.text
