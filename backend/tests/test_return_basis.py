"""P0-1 回归测试：收益/风险必须以「累计净值」为基准，而不是「单位净值」。

背景（实测，2026-09-19）：
    基金分红（除息）会让单位净值下跌。用单位净值计算收益、波动率、最大回撤，
    就等于把「基金分红」这个真实发生的金融事实，转换并包装成「基金亏损」。

    161725 招商中证白酒：单位净值口径累计收益 -47.17% / 最大回撤 -69.88%，
    累计净值口径 +124.44% / -36.01% —— 差 171.6pp。
    000001 差 257pp，519066 差 133pp，270042 差 27pp。
    但 110022 / 000961 差异恰好为 0。

    最后一点是这类 bug 最危险的地方：它对一半基金完全正确、对另一半完全错误，
    所以抽查、抽样、单只基金验证都发现不了。因此这里必须锁死"基准是累计净值"
    以及"缺累计净值就报错，绝不静默回退"。

本文件只验证数据语义，不使用 mock 折线、不生成任何替代数据。
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import fund as fund_api
from models.fund import FundSummary
from models.market import NavPeriod
from services import analysis_service, fund_service


def _recent_dates(count: int) -> list[str]:
    """最近 count 个自然日（含今天），避免测试绑定固定日历。"""
    today = datetime.now().date()
    return [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]


# 除息日发生在最后一天：单位净值被扣掉 0.10 的分红，累计净值不变。
UNIT_NAV_WITH_EXDIV = [1.50, 1.50, 1.50, 1.50, 1.40]
CUMULATIVE_NAV_WITH_EXDIV = [2.00, 2.00, 2.00, 2.00, 2.00]


def nav_frame(unit, cumulative):
    """构造与 `_fetch_nav_history` 真实输出同构的净值帧（4 列）。"""
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(_recent_dates(len(unit))),
            "单位净值": unit,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(unit),
        }
    )


def stub_fund(code="000001", name="测试基金") -> FundSummary:
    return FundSummary(
        code=code,
        name=name,
        company="测试基金公司",
        type="股票型",
        nav=1.4,
        change_pct=None,
        one_year_return=None,
        risk_level=None,
        size="-",
        heat=None,
    )


# ---------------------------------------------------------------------------
# 基准选择：必须是累计净值
# ---------------------------------------------------------------------------


def test_return_basis_is_cumulative_nav():
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV)
    basis = fund_service.total_return_series(frame)
    assert list(basis) == CUMULATIVE_NAV_WITH_EXDIV


def test_return_basis_refuses_frame_without_cumulative_nav():
    """只有单位净值时必须报错，绝不静默拿它当收益基准。"""
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV).drop(columns=["累计净值"])

    with pytest.raises(ValueError):
        fund_service.total_return_series(frame)
    with pytest.raises(ValueError):
        fund_service._returns_from_nav(frame)
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(frame, "股票型")


def test_return_basis_refuses_single_point_cumulative_nav():
    """累计净值只有 1 个可用点时无法构成收益序列，同样必须报错。"""
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV)
    frame.loc[1:, "累计净值"] = float("nan")

    with pytest.raises(ValueError):
        fund_service.total_return_series(frame)


# ---------------------------------------------------------------------------
# 分红不能被伪装成亏损 / 假波动 / 假回撤
# ---------------------------------------------------------------------------


def test_dividend_is_not_reported_as_a_loss():
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV)

    returns = fund_service._returns_from_nav(frame)
    assert returns.daily == 0.0

    metrics = fund_service._metrics_from_nav(frame, "股票型")
    assert metrics.max_drawdown == 0.0

    # 反向确认这条断言确实有区分力：误用单位净值会得到一根 -6.67% 的假阴线。
    unit_nav_daily = (
        UNIT_NAV_WITH_EXDIV[-1] - UNIT_NAV_WITH_EXDIV[-2]
    ) / UNIT_NAV_WITH_EXDIV[-2]
    assert unit_nav_daily < -0.06


def test_drawdown_series_ignores_dividend_drop():
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV)

    with patch.object(fund_service, "nav_history", return_value=frame):
        points = analysis_service.drawdown("000001", NavPeriod.ONE_YEAR)

    assert points, "回撤序列不应为空"
    assert all(point.drawdown == 0.0 for point in points)


def test_get_by_code_shows_unit_nav_but_reports_total_return_change():
    """展示用单位净值，涨跌幅用累计净值 —— 两个字段语义不同，都要正确。"""
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV)

    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=frame
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        detail = fund_service.get_by_code("000001")

    assert detail.nav == 1.40
    assert detail.change_pct == 0.0
    assert detail.change_pct != pytest.approx(-6.67, abs=0.01)


def test_nav_history_endpoint_normalized_curve_is_total_return():
    """归一化曲线是业绩曲线，分红日不应出现下跌台阶。"""
    frame = nav_frame(UNIT_NAV_WITH_EXDIV, CUMULATIVE_NAV_WITH_EXDIV)

    app = FastAPI()
    app.include_router(fund_api.router, prefix="/api")
    with patch.object(fund_service, "nav_history", return_value=frame):
        with TestClient(app) as client:
            response = client.get("/api/funds/000001/nav-history?period=1M")

    assert response.status_code == 200
    points = response.json()
    assert [point["nav"] for point in points] == UNIT_NAV_WITH_EXDIV
    assert all(point["normalized"] == 1.0 for point in points)


# ---------------------------------------------------------------------------
# 数据源失败时不得伪造净值序列
# ---------------------------------------------------------------------------


def test_nav_history_schema_survives_source_failure():
    """数据源失败时返回空的同构帧（含累计净值列），不生成任何替代序列。"""
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_open_fund_info_em", side_effect=RuntimeError("offline")
    ):
        frame = fund_service._fetch_nav_history("000001")

    assert frame.empty
    assert list(frame.columns) == fund_service._NAV_COLUMNS
    assert "累计净值" in frame.columns
