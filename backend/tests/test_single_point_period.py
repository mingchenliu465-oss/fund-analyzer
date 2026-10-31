"""回归测试：Bug B —— 周期内恰好 1 个点时两个接口返 500。

条目 3 计算边界审计（2026-10-28）TestClient 实测：mock 净值序列在请求
周期内只剩 1 点时，GET /api/funds/{code}/nav-history 与
GET /api/analysis/drawdown/{code} 均 500（`total_return_series` 要求
>= 2 点抛 ValueError，接口层未捕获；空帧路径有 [] 兜底，单点没有）。
2026-10-31 用户批准全部修后落地：两处在周期过滤后点数 < 2 时返回 []，
与空帧路径一致。本文件覆盖单点与空两种情形、两个接口，并保留多点回归。
"""

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import analysis as analysis_api
from api import fund as fund_api
from services import analysis_service, fund_service


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(fund_api.router, prefix="/api")
    app.include_router(analysis_api.router, prefix="/api")
    return app


def _frame(dates_values):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime([d for d, _ in dates_values]),
            "单位净值": [v for _, v in dates_values],
            "累计净值": [v for _, v in dates_values],
            "日增长率": [0.0] * len(dates_values),
        }
    )


def _today(offset_days: int) -> str:
    return (date.today() - timedelta(days=offset_days)).isoformat()


# 周期（近一年）内恰好 1 个点：今天 1 点 + 两年前 2 点（被周期过滤掉）
SINGLE_IN_PERIOD = _frame([("2020-01-02", 1.0), ("2020-01-03", 1.1), (_today(0), 1.2)])
# 周期内 0 个点
NONE_IN_PERIOD = _frame([("2020-01-02", 1.0), ("2020-01-03", 1.1)])
# 周期内多个点（回归）
MULTI_IN_PERIOD = _frame([(_today(30), 1.0), (_today(10), 1.1), (_today(0), 1.05)])


def _stub_fund():
    return fund_service.FundSummary(
        code="000001", name="测试基金", company="测试公司", type="股票型",
        nav=1.0, nav_date=None, nav_status=None,
        change_pct=None, one_year_return=None, risk_level=None, size="-", heat=None,
    )


def _get(path: str, frame: pd.DataFrame):
    app = _make_app()
    with patch.object(fund_service, "nav_history", return_value=frame), patch.object(
        fund_service, "list_all", return_value=[_stub_fund()]
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.get(path, params={"period": "1Y"})


def test_nav_history_single_point_in_period_returns_empty_list():
    response = _get("/api/funds/000001/nav-history", SINGLE_IN_PERIOD)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_nav_history_no_point_in_period_returns_empty_list():
    response = _get("/api/funds/000001/nav-history", NONE_IN_PERIOD)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_nav_history_multi_point_in_period_still_returns_points():
    response = _get("/api/funds/000001/nav-history", MULTI_IN_PERIOD)
    assert response.status_code == 200, response.text
    assert len(response.json()) == 3


def test_drawdown_single_point_in_period_returns_empty_list():
    response = _get("/api/analysis/drawdown/000001", SINGLE_IN_PERIOD)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_drawdown_no_point_in_period_returns_empty_list():
    response = _get("/api/analysis/drawdown/000001", NONE_IN_PERIOD)
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_drawdown_service_single_point_in_period_returns_empty():
    with patch.object(fund_service, "nav_history", return_value=SINGLE_IN_PERIOD):
        from models.market import NavPeriod

        assert analysis_service.drawdown("000001", NavPeriod.ONE_YEAR) == []
