"""回归测试：AI 解读（commentary）不得因缺失数据而崩溃或编造数字。

已修复的 bug：
  1. `ret_str = f"{ret_1y * 100:+.2f}%"` —— 近一年收益需要 >= 365 天历史。
     成立不足一年、或已终止的基金 `one_year_return` 为 None，原实现直接
     抛 TypeError，`main.py` 的全局处理器把它变成 /api/analysis/ai/{code} 的 500。
     实测真实标的：560160 食品ETF易方达（242 天）、159253 银行ETF博时（295 天）。
  2. `sharpe_str = f"{m.sharpe:.2f}"` 与 `m.sharpe > 0.5` —— 收益序列方差为 0 时
     夏普无定义（后端返回 None），原实现同样抛 TypeError。
  3. `elif sharpe_str and m.sharpe > 0.5` —— sharpe_str 是字符串、恒为真，
     `and` 起不到保护作用。

修复原则：缺失就说"数据不足"，既不能崩，也不能用 0 或估算值顶替。
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import analysis as analysis_api
from models.fund import FundDetail, FundMetrics, FundReturns, FundSummary
from services import analysis_service, fund_service


def build_detail(
    code="000001",
    name="测试基金",
    one_year_return=None,
    sharpe=0.8,
    risk_level="中高",
):
    return FundDetail(
        code=code,
        name=name,
        company="测试基金公司",
        type="股票型",
        nav=1.25,
        nav_date="2026-09-18",
        nav_status="fresh",
        change_pct=0.5,
        one_year_return=one_year_return,
        risk_level=risk_level,
        size="-",
        heat=None,
        inception_date="2026-01-19",
        returns=FundReturns(daily=0.0, weekly=None, monthly=None, yearly=one_year_return),
        metrics=FundMetrics(
            max_drawdown=-0.12,
            volatility=0.19,
            sharpe=sharpe,
            risk_level=risk_level,
            risk_score=None,
        ),
        sectors=[],
        tags=["股票型"],
        description=f"{name}是一只股票型基金。",
        manager="暂无数据",
        manager_days=None,
        rating=None,
        top_holdings=[],
        investment_style=None,
    )


def _commentary_with(detail):
    with patch.object(fund_service, "get_by_code", return_value=detail):
        return analysis_service.commentary(detail.code)


# ---------------------------------------------------------------------------
# bug 1：近一年收益缺失（历史不足一年 / 已终止）
# ---------------------------------------------------------------------------


def test_short_history_does_not_crash():
    detail = build_detail(one_year_return=None)

    result = _commentary_with(detail)

    assert result.performance
    assert "历史数据不足一年" in result.performance


def test_short_history_does_not_fabricate_a_return_number():
    """缺失的收益率不得被显示成 +0.00% —— 那是一个看起来真实的收益数字。"""
    detail = build_detail(one_year_return=None)

    result = _commentary_with(detail)

    # 最强断言：既然收益率缺失，整段文案里不该出现任何百分比数字。
    assert "%" not in result.performance, "缺失的收益率不得产生任何百分比数字"
    assert "不足一年" in result.performance
    assert "暂无" in result.performance


def test_short_history_still_reports_real_risk_metrics():
    """收益率缺失不影响真实的风险指标展示（波动率/回撤是算得出来的）。"""
    detail = build_detail(one_year_return=None)

    result = _commentary_with(detail)

    assert "最大回撤" in result.risk_warning
    assert "年化波动率" in result.risk_warning


def test_normal_fund_keeps_the_original_wording():
    """有真实近一年收益时行为不变（防回归）。"""
    detail = build_detail(one_year_return=-0.2401)

    result = _commentary_with(detail)

    assert "-24.01%" in result.performance
    assert "跌幅较大" in result.performance


@pytest.mark.parametrize(
    "ret_1y,expected",
    [(0.30, "涨幅明显"), (0.10, "录得正收益"), (0.02, "收益偏保守"),
     (-0.05, "短期承压"), (-0.30, "跌幅较大")],
)
def test_all_return_branches_still_work(ret_1y, expected):
    result = _commentary_with(build_detail(one_year_return=ret_1y))
    assert expected in result.performance


@pytest.mark.parametrize("ret_1y", [0.30, 0.10, 0.02, -0.05, -0.30])
def test_commentary_never_claims_a_peer_comparison_it_never_computed(ret_1y):
    """commentary 只调用过 get_by_code()，没有任何同业数据。

    因此"显著跑赢同类平均"/"处于同类中等水平"这类断言是编造的比较，
    必须不再出现（真实同业对比请走 /api/analysis/peers）。
    """
    result = _commentary_with(build_detail(one_year_return=ret_1y))

    for fabricated in ("同类平均", "同类中等", "跑赢同类", "低于同类", "高于同类"):
        assert fabricated not in result.performance
        assert fabricated not in result.risk_warning
        assert fabricated not in result.suggestion


# ---------------------------------------------------------------------------
# bug 2/3：夏普无定义（收益序列方差为 0）
# ---------------------------------------------------------------------------


def test_undefined_sharpe_does_not_crash():
    detail = build_detail(one_year_return=0.10, sharpe=None)

    result = _commentary_with(detail)

    assert "无定义" in result.suggestion
    assert result.suggestion


def test_undefined_sharpe_does_not_claim_low_risk_adjusted_return():
    """夏普算不出来时不得套用"风险收益比较低"这种结论。"""
    detail = build_detail(one_year_return=0.10, sharpe=None)

    result = _commentary_with(detail)

    assert "风险收益比较低" not in result.suggestion
    assert "Sharpe 比率 0.00" not in result.suggestion


def test_undefined_sharpe_does_not_show_a_zero_ratio():
    detail = build_detail(one_year_return=0.10, sharpe=None)

    result = _commentary_with(detail)

    assert "0.00" not in result.suggestion


@pytest.mark.parametrize(
    "sharpe,expected",
    [(0.9, "风险调整后收益尚可"), (0.2, "风险调整后收益偏低"), (-0.5, "风险收益比较低")],
)
def test_sharpe_branches_unchanged(sharpe, expected):
    detail = build_detail(one_year_return=0.10, sharpe=sharpe)

    assert expected in _commentary_with(detail).suggestion


def test_undefined_sharpe_reachable_from_a_real_flat_series():
    """确认 sharpe=None 不是理论分支：完全平坦的收益序列就会产出它。"""
    import pandas as pd
    from datetime import datetime, timedelta

    dates = [datetime.now().date() - timedelta(days=offset) for offset in range(400, -1, -1)]
    flat = pd.DataFrame(
        {
            "净值日期": pd.to_datetime(dates),
            "单位净值": [1.0] * len(dates),
            "累计净值": [1.0] * len(dates),
            "日增长率": [0.0] * len(dates),
        }
    )

    metrics = fund_service._metrics_from_nav(flat, "债券型")

    assert metrics.volatility == 0.0
    assert metrics.sharpe is None


# ---------------------------------------------------------------------------
# 端到端：/api/analysis/ai/{code} 不再 500
# ---------------------------------------------------------------------------


def test_ai_endpoint_returns_200_for_short_history_fund():
    app = FastAPI()
    app.include_router(analysis_api.router, prefix="/api")

    detail = build_detail(code="560160", name="食品ETF易方达", one_year_return=None)

    with patch.object(fund_service, "list_all", return_value=[FundSummary(
        code="560160", name="食品ETF易方达", company="-", type="ETF",
        nav=1.0, nav_date="2026-09-18", nav_status="fresh",
        change_pct=0.0, one_year_return=None, risk_level=None, size="-", heat=None,
    )]), patch.object(fund_service, "get_by_code", return_value=detail):
        with TestClient(app) as client:
            response = client.get("/api/analysis/ai/560160")

    assert response.status_code == 200
    assert "历史数据不足一年" in response.json()["performance"]
