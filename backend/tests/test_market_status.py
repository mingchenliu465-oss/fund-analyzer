"""回归测试：市场状态必须基于真实交易日历，不能用本地时钟猜。

已修复的 bug：
  后端 `market_service.status()` 只看本地时间，不看星期与法定节假日。
  实测周六 2026-09-19 10:00 返回 **"交易中"** —— 把非交易日谎报成正在交易。

  前端 `services/fund.ts:getMarketStatus()` 是同一套规则的**重复实现**，且已漂移：
    1) 只判断工作日，节假日仍会显示"交易中"；
    2) 11:31-12:59 落到最后一个分支，把"午间休市"标成"未开盘"。
  现在前端直接调用 `/api/market/status`，删除重复实现。
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import market as market_api
from services import fund_service, market_service

# 真实日历：2026-09-18 是周五（交易日），09-19/20 是周末。
FRIDAY = datetime(2026, 9, 18)
SATURDAY = datetime(2026, 9, 19)
SUNDAY = datetime(2026, 9, 20)


class _FakeDateTime:
    """把 now() 固定到某个时刻，其余行为与 datetime 一致。"""

    current: datetime = FRIDAY

    @classmethod
    def now(cls) -> datetime:
        return cls.current

    @classmethod
    def fromisoformat(cls, value: str) -> datetime:
        return datetime.fromisoformat(value)

    @classmethod
    def combine(cls, *args, **kwargs):
        return datetime.combine(*args, **kwargs)


def status_at(moment: datetime):
    """在伪造的"当前时刻"下调用 status()，日历仍用真实数据。"""
    _FakeDateTime.current = moment
    with patch.object(market_service, "datetime", _FakeDateTime), patch.object(
        fund_service, "datetime", _FakeDateTime
    ):
        return market_service.status()


# ---------------------------------------------------------------------------
# 周末 / 非交易日
# ---------------------------------------------------------------------------


def test_saturday_midmorning_is_not_reported_as_trading():
    """核心断言：周六 10:00 不得返回"交易中"。"""
    result = status_at(SATURDAY.replace(hour=10))

    assert result.status == "休市"
    assert result.status != "交易中"
    assert "非交易日" in result.session


def test_sunday_midmorning_is_not_reported_as_trading():
    result = status_at(SUNDAY.replace(hour=10))

    assert result.status == "休市"
    assert "非交易日" in result.session


def test_saturday_afternoon_is_not_reported_as_trading():
    result = status_at(SATURDAY.replace(hour=14))

    assert result.status == "休市"


# ---------------------------------------------------------------------------
# 交易日：盘中各时段语义不变（防回归）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hour,minute,expected_status,expected_session",
    [
        (8, 0, "未开盘", "等待开盘"),
        (9, 30, "交易中", "A股连续竞价"),
        (10, 0, "交易中", "A股连续竞价"),
        (11, 29, "交易中", "A股连续竞价"),
        (11, 30, "午间休市", "午间休市"),
        (12, 0, "午间休市", "午间休市"),
        (12, 59, "午间休市", "午间休市"),
        (13, 0, "交易中", "A股连续竞价"),
        (14, 59, "交易中", "A股连续竞价"),
        (15, 0, "已收盘", "等待下一交易日"),
        (16, 0, "已收盘", "等待下一交易日"),
    ],
)
def test_trading_day_intraday_branches_unchanged(hour, minute, expected_status, expected_session):
    result = status_at(FRIDAY.replace(hour=hour, minute=minute))

    assert result.status == expected_status
    assert result.session == expected_session


def test_friday_is_recognised_as_a_trading_day():
    """确认 2026-09-18 确实在真实交易日历里，上一条参数化才有意义。"""
    assert date(2026, 9, 18) in fund_service._trade_calendar()
    assert date(2026, 9, 19) not in fund_service._trade_calendar()
    assert date(2026, 9, 20) not in fund_service._trade_calendar()


# ---------------------------------------------------------------------------
# 日历不可用：不得猜成"交易中"
# ---------------------------------------------------------------------------


def test_unavailable_calendar_does_not_claim_the_market_is_open():
    with patch.object(fund_service, "latest_trading_day", return_value=None):
        result = market_service.status()

    assert result.status == "休市"
    assert result.status != "交易中"
    assert "无法确认" in result.session


# ---------------------------------------------------------------------------
# 端到端：API 与 status() 一致
# ---------------------------------------------------------------------------


def test_api_exposes_the_calendar_aware_status():
    app = FastAPI()
    app.include_router(market_api.router, prefix="/api")

    _FakeDateTime.current = SATURDAY.replace(hour=10)
    with patch.object(market_service, "datetime", _FakeDateTime), patch.object(
        fund_service, "datetime", _FakeDateTime
    ):
        with TestClient(app) as client:
            response = client.get("/api/market/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "休市"
    assert "updateTime" in payload
