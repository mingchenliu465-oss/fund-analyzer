"""条目 3 计算正确性边界审计（2026-10-28 定时运行）。

审计范围：收益率 / 涨跌幅 / 净值相关计算的边界情况——空序列、
只有一天数据、除零（零值/负值净值）、有效收益不足。

审计结论（见 RUNLOG 2026-10-28）：
  * 本文件锁定的行为全部通过：空/单点序列一律拒绝计算、不产出 0 冒充
    收益；首尾零值/负值被 `_returns_from_nav` 拦下；周期内无数据时
    回撤与统计审计返回空/不足状态而不崩溃。
  * 本文件**不**锁定 `_metrics_from_nav` 对序列中间/首位零值、负值、
    NaN 的行为：探针证实它会产出无意义指标（波动率 nan 却标“高”风险、
    最大回撤 -2.0），属已记录未修的真 bug（Bug A），不在本文件中断言，
    以免把错误行为锁死为正确口径。
  * 同理不锁定单点周期帧的两个接口行为：净值历史与回撤接口在周期内
    恰好 1 个点时抛 ValueError 变成 500（Bug B），已记录未修。
"""

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from models.fund import FundSummary
from models.market import NavPeriod
from services import analysis_service, fund_service, portfolio_service


def _recent_dates(count: int) -> list[str]:
    today = date.today()
    return [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]


def nav_frame(cumulative):
    """与 `_fetch_nav_history` 同构的净值帧；单位净值 == 累计净值（无分红）。"""
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(_recent_dates(len(cumulative))),
            "单位净值": cumulative,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(cumulative),
        }
    )


def empty_frame():
    return pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"])


def stub_fund(code="000001", name="测试基金"):
    return fund_service.FundSummary(
        code=code, name=name, company="测试公司", type="股票型",
        nav=1.0, nav_date=None, nav_status=None,
        change_pct=None, one_year_return=None, risk_level=None, size="-", heat=None,
    )


# ---------------------------------------------------------------------------
# 空序列与单点序列：一切收益/风险计算必须拒绝，不产出 0
# ---------------------------------------------------------------------------


def test_empty_frame_is_refused_by_all_three_calculations():
    with pytest.raises(ValueError):
        fund_service.total_return_series(empty_frame())
    with pytest.raises(ValueError):
        fund_service._returns_from_nav(empty_frame())
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(empty_frame(), "股票型")


def test_single_point_frame_is_refused_by_all_three_calculations():
    frame = nav_frame([1.0])
    with pytest.raises(ValueError):
        fund_service.total_return_series(frame)
    with pytest.raises(ValueError):
        fund_service._returns_from_nav(frame)
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(frame, "股票型")


def test_two_point_frame_yields_returns_but_not_risk_metrics():
    """2 个点只有 1 个日收益：收益率可算，风险指标（需 >= 2 个收益）必须拒绝。"""
    returns = fund_service._returns_from_nav(nav_frame([1.0, 1.1]))
    assert returns.daily == pytest.approx(0.1)
    assert returns.weekly is None  # 历史不足 7 天，窗口收益为 None 而非 0
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(nav_frame([1.0, 1.1]), "股票型")


def test_all_nan_cumulative_nav_is_refused():
    frame = nav_frame([float("nan"), float("nan"), float("nan")])
    with pytest.raises(ValueError):
        fund_service.total_return_series(frame)


# ---------------------------------------------------------------------------
# 除零：首尾零值/负值净值必须拒绝；中间零值不污染当日涨跌幅
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("values", [[1.0, 1.1, 0.0], [1.0, 0.0, 1.1], [1.0, 1.1, -1.0], [1.0, -1.0, 1.1]])
def test_returns_refuse_non_positive_latest_or_previous(values):
    with pytest.raises(ValueError):
        fund_service._returns_from_nav(nav_frame(values))


def test_returns_daily_uses_only_the_last_two_points():
    """中间脏点不改变当日涨跌幅的定义（当日 = 最后两点之比），且结果有限。"""
    import math

    returns = fund_service._returns_from_nav(nav_frame([1.0, 0.0, 1.1, 1.2]))
    assert returns.daily == pytest.approx((1.2 - 1.1) / 1.1)
    assert math.isfinite(returns.daily)


# ---------------------------------------------------------------------------
# 详情入口：净值不足 3 条时拒绝，不拼凑详情页
# ---------------------------------------------------------------------------


def test_get_by_code_refuses_fewer_than_three_nav_points():
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=nav_frame([1.0, 1.1])
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        with pytest.raises(ValueError):
            fund_service.get_by_code("000001")


# ---------------------------------------------------------------------------
# 周期过滤后的边界：周期内无数据 -> 空/不足状态，不崩溃
# ---------------------------------------------------------------------------


def test_drawdown_with_no_points_in_period_returns_empty():
    """2020 年的旧序列在近一年窗口内无点：回撤返回 []（与空帧路径一致）。"""
    old = pd.DataFrame(
        {
            "净值日期": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
            "单位净值": [1.0, 1.1, 1.05],
            "累计净值": [1.0, 1.1, 1.05],
            "日增长率": [0.0, 0.0, 0.0],
        }
    )
    with patch.object(fund_service, "nav_history", return_value=old):
        assert analysis_service.drawdown("000001", NavPeriod.ONE_YEAR) == []


def test_statistics_audit_with_one_valid_return_is_insufficient_not_crash():
    with patch.object(fund_service, "nav_history", return_value=nav_frame([1.0, 1.1])):
        audit = analysis_service.statistics_audit("000001", NavPeriod.ONE_YEAR)
    assert audit.status == "insufficient"
    assert audit.valid_returns == 1


# ---------------------------------------------------------------------------
# 组合侧边界：单点快照与单点指数不产生虚假收益率
# ---------------------------------------------------------------------------


def test_history_insight_with_single_snapshot_is_insufficient():
    insight = portfolio_service._build_history_insight(
        [{"date": "2026-10-28", "total_value": 10000.0, "profit": 0.0}]
    )
    assert insight["data_sufficiency"] == "insufficient"
    assert insight["trend"] == "暂无"
    assert insight["points"][0]["day_change"] is None
    assert insight["points"][0]["day_change_pct"] is None


def test_index_return_with_single_point_is_none():
    from models.market import KlinePoint
    from services import market_service

    point = KlinePoint(date="2026-10-28", open=3000.0, high=3000.0, low=3000.0, close=3000.0)
    with patch.object(market_service, "index_kline", return_value=[point]):
        assert portfolio_service._fetch_index_return("sh000300", None) is None
