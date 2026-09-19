"""P0-6 回归测试：过期 / 退市 / 旧数据不得被当作当前金融数据。

背景（实测，2026-09-19）：
  * 项目此前**完全没有交易日历意识** —— `ak.tool_trade_date_hist_sina()`
    从未被调用，是否"最新"全靠本地时钟。
  * `get_by_code()` 直接取 `nav_df["单位净值"].iloc[-1]` 当"当前净值"，不看日期：
    已退市基金（如 150153，历史止于 2020-12-31）会把它当成当前净值。
  * `portfolio_service._set_holding_nav_cache()` 把 `nav_date` 写成
    `date.today()` —— 源数据的真实观测日被丢弃，一份旧净值被盖上今天的日期。
  * `_open_fund_nav_change()` 取序列最后两条当"今日/昨日"，2020 年的涨跌幅
    会变成"今日收益"。

状态模型（互斥，绝不混成一个 0）：
    fresh / stale / inactive / unavailable / unknown

本文件锁定：用**真实交易日历**判断新鲜度，且过期数据不得进入"当前"口径。
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from api import fund as fund_api
from fastapi import FastAPI
from fastapi.testclient import TestClient
from models.fund import FundSummary
from services import fund_service, portfolio_service

# 2026-09-19 是周六（下方有断言守护），2026-09-18 是周五。
SATURDAY = date(2026, 9, 19)
FRIDAY = date(2026, 9, 18)
THURSDAY = date(2026, 9, 17)


def _synthetic_calendar(start: date, end: date) -> list[date]:
    """工作日日历（忽略法定节假日）。

    仅用于需要跨越多年（>= 250 个交易日）的阈值测试。真实节假日行为由
    `test_real_trade_calendar_*` 用真实数据源覆盖。
    """
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


FULL_CALENDAR = _synthetic_calendar(date(2019, 1, 1), date(2026, 12, 31))


@pytest.fixture
def calendar():
    """注入一份确定的交易日历，避免测试依赖网络与真实节假日。"""
    with patch.object(fund_service, "_trade_calendar", return_value=FULL_CALENDAR):
        yield FULL_CALENDAR


def nav_frame(rows: list[tuple[str, float, float]]):
    """与 _fetch_nav_history 真实输出同构的净值帧。"""
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime([row[0] for row in rows]),
            "单位净值": [row[1] for row in rows],
            "累计净值": [row[2] for row in rows],
            "日增长率": [0.0] * len(rows),
        }
    )


STALE_NAV_FRAME = nav_frame(
    [("2020-11-30", 1.20, 1.40), ("2020-12-01", 1.22, 1.42), ("2020-12-31", 1.25, 1.45)]
)


def stub_fund(code="000001", name="已退市测试基金", nav=1.25, nav_date="2020-12-31"):
    return FundSummary(
        code=code, name=name, company="测试基金公司", type="股票型",
        nav=nav, nav_date=nav_date, nav_status=None,
        change_pct=None, one_year_return=None, risk_level=None, size="-", heat=None,
    )


def test_saturday_assumption_holds():
    """本文件的 Case B 依赖 2026-09-19 是周六。"""
    assert SATURDAY.weekday() == 5
    assert FRIDAY.weekday() == 4


# ---------------------------------------------------------------------------
# Case A：数据最新 -> fresh
# ---------------------------------------------------------------------------


def test_case_a_latest_trading_day_is_fresh(calendar):
    assert fund_service.latest_trading_day(today=FRIDAY) == FRIDAY
    assert fund_service.nav_data_status(FRIDAY, today=FRIDAY) == fund_service.NAV_STATUS_FRESH
    assert fund_service.is_current_nav(FRIDAY, today=FRIDAY) is True


def test_case_a_accepts_one_trading_day_lag_for_open_funds(calendar):
    """场外基金按 T-1 披露属于正常，不能因此判 stale。"""
    assert fund_service.nav_data_status(THURSDAY, today=FRIDAY) == fund_service.NAV_STATUS_FRESH


# ---------------------------------------------------------------------------
# Case B：周末查询 -> 不能错误标记 stale
# ---------------------------------------------------------------------------


def test_case_b_friday_data_on_saturday_is_not_stale(calendar):
    assert fund_service.latest_trading_day(today=SATURDAY) == FRIDAY
    assert fund_service.nav_data_status(FRIDAY, today=SATURDAY) == fund_service.NAV_STATUS_FRESH
    assert fund_service.is_current_nav(FRIDAY, today=SATURDAY) is True


# ---------------------------------------------------------------------------
# Case C：交易日明显滞后 -> stale
# ---------------------------------------------------------------------------


def test_case_c_three_trading_days_behind_is_stale(calendar):
    three_behind = date(2026, 9, 15)  # 09-16 / 09-17 / 09-18 共 3 个交易日
    assert fund_service._trading_days_behind(three_behind, today=FRIDAY) == 3
    assert fund_service.nav_data_status(three_behind, today=FRIDAY) == fund_service.NAV_STATUS_STALE
    assert fund_service.is_current_nav(three_behind, today=FRIDAY) is False


# ---------------------------------------------------------------------------
# Case D：极老数据 -> inactive，绝不能作为 current data
# ---------------------------------------------------------------------------


def test_case_d_very_old_data_is_inactive_not_current(calendar):
    ancient = date(2020, 12, 31)
    assert fund_service._trading_days_behind(ancient, today=FRIDAY) >= 250
    assert fund_service.nav_data_status(ancient, today=FRIDAY) == fund_service.NAV_STATUS_INACTIVE
    assert fund_service.is_current_nav(ancient, today=FRIDAY) is False


def test_case_d_get_by_code_refuses_to_report_last_nav_as_current(calendar):
    """退市基金的详情页不得把 2020 年的净值当成当前净值。"""
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=STALE_NAV_FRAME
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        detail = fund_service.get_by_code("000001")

    assert detail.nav is None
    assert detail.change_pct is None
    assert detail.one_year_return is None
    assert detail.nav_date == "2020-12-31"
    assert detail.nav_status == fund_service.NAV_STATUS_INACTIVE
    # 反向确认：这些确实是可用的真实数值，只是"不是当前值"。
    assert STALE_NAV_FRAME["单位净值"].iloc[-1] == 1.25


# ---------------------------------------------------------------------------
# Case E：没有数据 -> unavailable，不能是 0
# ---------------------------------------------------------------------------


def test_case_e_missing_observation_is_unavailable_not_zero(calendar):
    assert fund_service.nav_data_status(None, today=FRIDAY) == fund_service.NAV_STATUS_UNAVAILABLE
    assert fund_service.nav_data_status("", today=FRIDAY) == fund_service.NAV_STATUS_UNAVAILABLE
    assert fund_service.is_current_nav(None, today=FRIDAY) is False


def test_case_e_missing_quote_never_becomes_zero():
    with patch.object(portfolio_service, "_get_holding_nav", return_value=None):
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")

    assert nav is None
    assert nav != 0, "缺失必须与真实的 0 区分开"
    assert nav_date is None
    assert stale is True


def test_calendar_unavailable_is_unknown_not_fresh():
    """日历取不到时无法判定新鲜度：必须是 unknown，绝不能当作 fresh。"""
    with patch.object(fund_service, "_trade_calendar", return_value=[]):
        assert fund_service.latest_trading_day(today=FRIDAY) is None
        assert fund_service.nav_data_status(FRIDAY, today=FRIDAY) == fund_service.NAV_STATUS_UNKNOWN
        assert fund_service.is_current_nav(FRIDAY, today=FRIDAY) is False


def test_unparsable_observation_is_unavailable_not_guessed(calendar):
    assert fund_service.nav_data_status("不是日期", today=FRIDAY) == fund_service.NAV_STATUS_UNAVAILABLE


# ---------------------------------------------------------------------------
# Case F：stale / inactive 不得进入"当前估值 / 当前收益"路径
# ---------------------------------------------------------------------------


def test_case_f_expired_nav_is_excluded_from_current_valuation(calendar):
    with patch.object(portfolio_service, "_get_holding_nav", return_value=(1.25, "2020-12-31")):
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")

    assert nav is None, "过期净值不得作为当前估值"
    assert nav_date == "2020-12-31", "但观测日要保留，用来说明最后已知是哪天"
    assert stale is True


def test_case_f_fresh_nav_is_used_for_current_valuation(calendar):
    with patch.object(portfolio_service, "_get_holding_nav", return_value=(1.25, FRIDAY.isoformat())):
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")

    assert nav == 1.25
    assert nav_date == FRIDAY.isoformat()
    assert stale is False


def test_case_f_expired_nav_never_becomes_todays_return(calendar):
    """退市基金的 2020 年涨跌幅不得被当成"今日收益"。"""
    with patch.object(fund_service, "_fetch_nav_history", return_value=STALE_NAV_FRAME):
        latest, prev, change_pct = portfolio_service._open_fund_nav_change("000001")

    assert (latest, prev, change_pct) == (0.0, 0.0, 0.0)


def test_case_f_expired_ranking_snapshot_is_not_used_for_attribution(calendar):
    """基金列表里的旧快照同样不能参与今日收益归因。"""
    holding = type("H", (), {
        "fund_code": "000001", "fund_name": "测试基金", "shares": 100.0, "fund_type": "股票型",
    })()
    stale_summary = stub_fund(nav=2.0, nav_date="2020-12-31")

    with patch.object(portfolio_service, "list_holdings", return_value=[holding]), patch.object(
        portfolio_service.fund_service, "_load_fund_list", return_value=[stale_summary]
    ), patch.object(
        portfolio_service, "_open_fund_nav_change", return_value=(0.0, 0.0, 0.0)
    ), patch.object(
        portfolio_service.fund_service, "_is_etf_code", return_value=False
    ):
        result = portfolio_service.attribution()

    assert result["contributions"] == []
    assert result["today_return"] is None
    assert result["summary"]["status"] == "unavailable"


def test_case_f_holding_item_carries_observation_date_and_stale_flag():
    row = {
        "id": 1, "fund_code": "000001", "fund_name": "测试基金", "fund_type": "股票型",
        "buy_date": "2020-01-01", "buy_amount": 100.0, "buy_nav": 1.0, "shares": 100.0,
        "fee": 0.0, "notes": "", "is_sold": 0,
    }

    with patch.object(portfolio_service, "_get_holding_nav", return_value=(1.25, "2020-12-31")):
        item = portfolio_service._getportfolio_nav_fallback("000001")
        result = portfolio_service._enrich_holding_from_map_r(row, "000001", item[0], item[2], item[1])

    assert result.current_nav is None
    assert result.current_value is None
    assert result.profit is None
    assert result.nav_stale is True
    assert result.nav_date == "2020-12-31"


# ---------------------------------------------------------------------------
# Case G：历史查询不受 freshness 检查影响
# ---------------------------------------------------------------------------


def test_case_g_nav_history_returns_the_full_series_including_expired_rows(calendar):
    with patch.object(fund_service, "_fetch_nav_history", return_value=STALE_NAV_FRAME):
        df = fund_service.nav_history("000001")

    assert len(df) == len(STALE_NAV_FRAME)
    assert str(df["净值日期"].iloc[-1].date()) == "2020-12-31"


def test_case_g_nav_history_api_still_serves_legitimate_history(calendar):
    """净值历史接口不做 freshness 过滤，只按用户选择的周期窗口截取。"""
    frame = nav_frame(
        [
            ((datetime.now().date() - timedelta(days=20)).isoformat(), 1.10, 1.20),
            ((datetime.now().date() - timedelta(days=10)).isoformat(), 1.12, 1.22),
            ((datetime.now().date() - timedelta(days=2)).isoformat(), 1.15, 1.25),
        ]
    )

    app = FastAPI()
    app.include_router(fund_api.router, prefix="/api")
    with patch.object(fund_service, "nav_history", return_value=frame):
        with TestClient(app) as client:
            response = client.get("/api/funds/000001/nav-history?period=1M")

    assert response.status_code == 200
    assert len(response.json()) == 3


# ---------------------------------------------------------------------------
# 真实交易日历（不注入）—— 证明真实数据源路径可用
# ---------------------------------------------------------------------------


def test_real_trade_calendar_drives_freshness_end_to_end():
    """用真实日历（tool_trade_date_hist_sina）验证：最近交易日 = fresh，
    明显滞后 = stale，2020 年 = inactive。"""
    latest = fund_service.latest_trading_day()
    assert latest is not None, "真实交易日历应可用"

    assert fund_service.nav_data_status(latest) == fund_service.NAV_STATUS_FRESH
    assert fund_service.nav_data_status(date(2020, 12, 31)) == fund_service.NAV_STATUS_INACTIVE

    calendar = fund_service._trade_calendar()
    earlier = [day for day in calendar if day < latest]
    assert len(earlier) >= 3
    three_back = earlier[-3]
    assert fund_service.nav_data_status(three_back) == fund_service.NAV_STATUS_STALE
