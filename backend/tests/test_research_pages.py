"""Performance、Risk、Data Audit 的独立金融口径测试。"""
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app
from models.analysis import ResearchPeriod
from services import overview_service, research_service

AS_OF = date(2026, 3, 1)


def make_nav(dates, cumulative, unit=None):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(dates),
            "单位净值": unit if unit is not None else cumulative,
            "累计净值": cumulative,
        }
    )


def patch_common(monkeypatch, nav):
    monkeypatch.setattr(overview_service.fund_service, "nav_history", lambda code: nav)
    monkeypatch.setattr(
        overview_service.fund_service,
        "list_all",
        lambda: [SimpleNamespace(code="161725", name="测试基金")],
    )
    monkeypatch.setattr(overview_service.market_service, "index_kline", lambda code, period: [])


def test_performance_annualized_and_calendar_return_definitions(monkeypatch):
    nav = make_nav(
        ["2025-12-31", "2026-01-02", "2026-01-30", "2026-02-02", "2026-02-27"],
        [1.0, 1.1, 1.21, 1.1, 1.32],
    )
    patch_common(monkeypatch, nav)

    result = research_service.performance("161725", ResearchPeriod.ALL, date(2026, 2, 27))

    days = (pd.Timestamp("2026-02-27") - pd.Timestamp("2025-12-31")).days
    assert result["metrics"]["annualized_return"] == pytest.approx(
        round(float(1.32 ** (365.25 / days) - 1), 4)
    )
    assert result["metrics"]["period_return"] == pytest.approx(0.32)
    assert result["metrics"]["benchmark_return"] is None
    assert result["metrics"]["excess_return"] is None
    assert result["annual_returns"][0]["return"] is None
    assert result["annual_returns"][1]["return"] == pytest.approx(0.32)
    january = next(item for item in result["monthly_returns"] if item["label"] == "2026-01")
    february = next(item for item in result["monthly_returns"] if item["label"] == "2026-02")
    assert january["return"] == pytest.approx(0.21)
    assert january["is_partial"] is False
    assert february["return"] == 0.0909  # 服务统一保留四位小数
    assert february["is_partial"] is True


def test_risk_drawdown_tracks_decline_and_recovery_separately(monkeypatch):
    nav = make_nav(
        ["2026-01-02", "2026-01-30", "2026-02-02", "2026-02-27"],
        [1.0, 1.21, 1.1, 1.32],
    )
    patch_common(monkeypatch, nav)

    result = research_service.risk("161725", ResearchPeriod.ALL, AS_OF)

    assert result["metrics"]["max_drawdown"] == pytest.approx(1.1 / 1.21 - 1)
    assert result["drawdown"] == {
        "peak_date": "2026-01-30",
        "trough_date": "2026-02-02",
        "recovery_date": "2026-02-27",
        "drawdown_days": 3,
        "recovery_days": 25,
        "underwater_days": 28,
        "recovery_status": "recovered",
    }
    returns = np.array([0.21, 1.1 / 1.21 - 1, 1.2])
    downside = np.minimum(returns - 0.02 / 252, 0)
    assert result["metrics"]["downside_deviation"] == pytest.approx(
        round(float(np.sqrt(np.mean(downside**2)) * np.sqrt(252)), 4)
    )


def test_unrecovered_drawdown_has_no_fake_recovery_time(monkeypatch):
    nav = make_nav(
        ["2026-01-02", "2026-01-30", "2026-02-02", "2026-02-27"],
        [1.0, 1.2, 0.9, 1.0],
    )
    patch_common(monkeypatch, nav)

    result = research_service.risk("161725", ResearchPeriod.ALL, AS_OF)

    assert result["drawdown"]["recovery_status"] == "unrecovered"
    assert result["drawdown"]["recovery_date"] is None
    assert result["drawdown"]["recovery_days"] is None
    assert result["drawdown"]["underwater_days"] == 28


def test_audit_reports_missing_trading_day_and_possible_adjustment(monkeypatch):
    nav = make_nav(
        ["2026-01-05", "2026-01-06", "2026-01-08"],
        [1.0, 1.0, 1.1],
        [1.0, 0.9, 0.9],
    )
    monkeypatch.setattr(research_service.fund_service, "nav_history", lambda code: nav)
    calendar = [date(2026, 1, 5) + timedelta(days=i) for i in range(4)]
    monkeypatch.setattr(research_service.fund_service, "_trade_calendar", lambda: calendar)

    result = research_service.data_audit("161725", ResearchPeriod.ALL, AS_OF)

    assert result["missing_dates"] == ["2026-01-07"]
    assert result["coverage_ratio"] == pytest.approx(0.75)
    assert result["distribution_candidates"][0]["date"] == "2026-01-06"
    assert result["distribution_candidates"][0]["status"] == "unverified"
    continuity = next(check for check in result["checks"] if check["key"] == "continuity")
    cross_source = next(check for check in result["checks"] if check["key"] == "cross_source")
    assert continuity["status"] == "abnormal"
    assert cross_source["status"] == "unverified"
    assert result["overall_status"] == "abnormal"


def test_audit_does_not_confirm_distribution_without_event_source(monkeypatch):
    nav = make_nav(["2026-01-05", "2026-01-06"], [1.0, 1.0], [1.0, 0.9])
    monkeypatch.setattr(research_service.fund_service, "nav_history", lambda code: nav)
    monkeypatch.setattr(research_service.fund_service, "_trade_calendar", lambda: [date(2026, 1, 5), date(2026, 1, 6)])

    result = research_service.data_audit("161725", ResearchPeriod.ALL, AS_OF)

    distribution = next(check for check in result["checks"] if check["key"] == "distributions")
    assert distribution["status"] == "unverified"
    assert "不确认事件性质" in distribution["detail"]


def test_constant_nav_offset_is_not_misreported_as_distribution(monkeypatch):
    # 单位净值与累计净值基数不同会让百分比收益不同，但每日绝对变动完全一致。
    nav = make_nav(
        ["2026-01-05", "2026-01-06", "2026-01-07"],
        [2.0, 2.1, 2.21],
        [1.0, 1.1, 1.21],
    )
    monkeypatch.setattr(research_service.fund_service, "nav_history", lambda code: nav)
    monkeypatch.setattr(
        research_service.fund_service,
        "_trade_calendar",
        lambda: [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)],
    )

    result = research_service.data_audit("161725", ResearchPeriod.ALL, AS_OF)

    assert result["distribution_candidates"] == []
    consistency = next(check for check in result["checks"] if check["key"] == "nav_consistency")
    assert consistency["status"] == "normal"


def test_research_apis_return_camel_case(monkeypatch):
    nav = make_nav(
        ["2026-01-02", "2026-01-30", "2026-02-02", "2026-02-27"],
        [1.0, 1.21, 1.1, 1.32],
    )
    patch_common(monkeypatch, nav)
    monkeypatch.setattr(research_service.fund_service, "nav_history", lambda code: nav)
    monkeypatch.setattr(research_service.fund_service, "_trade_calendar", lambda: [])
    monkeypatch.setattr("api.analysis._ensure_exists", lambda code: None)

    client = TestClient(app)
    performance = client.get("/api/analysis/performance/161725?period=all")
    risk = client.get("/api/analysis/risk/161725?period=all")
    audit = client.get("/api/analysis/audit/161725?period=all")

    assert performance.status_code == 200
    assert risk.status_code == 200
    assert audit.status_code == 200
    assert performance.json()["metrics"]["annualizedReturn"] is not None
    assert "annualReturns" in performance.json()
    assert risk.json()["drawdown"]["recoveryStatus"] == "recovered"
    assert "downsideDeviation" in risk.json()["metrics"]
    assert "overallStatus" in audit.json()
    assert "distributionCandidates" in audit.json()
