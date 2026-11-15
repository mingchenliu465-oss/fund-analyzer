"""研究概览的区间口径、累计净值和共同交易日测试。"""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app
from models.analysis import ResearchPeriod
from models.market import KlinePoint
from services import overview_service

AS_OF = date(2026, 3, 1)


def nav_frame(values, dates=None, include_cumulative=True):
    dates = dates or ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    dates = dates[: len(values)]
    frame = pd.DataFrame({"净值日期": dates, "单位净值": [0.8] * len(values)})
    if include_cumulative:
        frame["累计净值"] = values
    return frame


def benchmark_points(dates, closes):
    return [
        KlinePoint(date=day, open=value, high=value, low=value, close=value)
        for day, value in zip(dates, closes)
    ]


def patch_sources(monkeypatch, nav, benchmark=None):
    monkeypatch.setattr(overview_service.fund_service, "nav_history", lambda code: nav)
    monkeypatch.setattr(
        overview_service.fund_service,
        "list_all",
        lambda: [SimpleNamespace(code="161725", name="招商中证白酒指数")],
    )
    monkeypatch.setattr(
        overview_service.market_service,
        "index_kline",
        lambda code, period: benchmark or [],
    )


def test_metrics_use_selected_cumulative_nav_not_unit_nav(monkeypatch):
    patch_sources(monkeypatch, nav_frame([1.0, 1.1, 0.99, 1.188]))

    result = overview_service.overview("161725", ResearchPeriod.ALL, AS_OF)

    assert result["metrics"]["period_return"] == pytest.approx(0.188)
    assert result["metrics"]["max_drawdown"] == pytest.approx(-0.1)
    returns = np.array([0.1, -0.1, 0.2])
    assert result["metrics"]["volatility"] == pytest.approx(
        round(float(returns.std() * np.sqrt(252)), 4)
    )
    assert result["metrics"]["sharpe"] == pytest.approx(
        round(float((returns - 0.02 / 252).mean() / (returns - 0.02 / 252).std() * np.sqrt(252)), 2)
    )
    assert result["metric_status"] == "available"


def test_period_filter_excludes_observations_before_cutoff(monkeypatch):
    patch_sources(
        monkeypatch,
        nav_frame(
            [5.0, 1.0, 1.1, 1.21],
            ["2025-01-01", "2026-02-10", "2026-02-11", "2026-02-12"],
        ),
    )

    result = overview_service.overview("161725", ResearchPeriod.ONE_MONTH, AS_OF)

    assert result["data_start"] == "2026-02-10"
    assert result["sample_count"] == 3
    assert result["metrics"]["period_return"] == pytest.approx(0.21)


def test_benchmark_is_inner_joined_and_normalized_on_common_dates(monkeypatch):
    patch_sources(
        monkeypatch,
        nav_frame([1.0, 1.1, 0.99, 1.188]),
        benchmark_points(
            ["2026-01-05", "2026-01-06", "2026-01-08"],
            [3000.0, 3030.0, 3090.0],
        ),
    )

    result = overview_service.overview("161725", ResearchPeriod.ALL, AS_OF)

    assert [point["date"] for point in result["curve"]] == ["2026-01-05", "2026-01-06"]
    assert result["curve"][0] == {"date": "2026-01-05", "fund": 1.0, "benchmark": 1.0}
    assert result["curve"][-1]["fund"] == pytest.approx(0.9)
    assert result["curve"][-1]["benchmark"] == pytest.approx(1.01)
    assert result["benchmark"]["period_return"] == pytest.approx(0.01)
    assert result["benchmark"]["matched_samples"] == 2
    assert result["benchmark"]["fund_only_dates"] == 2
    assert result["benchmark"]["benchmark_only_dates"] == 1


def test_missing_benchmark_keeps_real_fund_curve_without_fabricated_points(monkeypatch):
    patch_sources(monkeypatch, nav_frame([1.0, 1.1, 1.21]), [])

    result = overview_service.overview("161725", ResearchPeriod.ALL, AS_OF)

    assert len(result["curve"]) == 3
    assert all(point["benchmark"] is None for point in result["curve"])
    assert result["benchmark"]["status"] == "unavailable"
    assert result["benchmark"]["period_return"] is None


def test_two_points_return_only_period_return(monkeypatch):
    patch_sources(monkeypatch, nav_frame([1.0, 1.1], ["2026-02-10", "2026-02-11"]))

    result = overview_service.overview("161725", ResearchPeriod.ONE_MONTH, AS_OF)

    assert result["metric_status"] == "partial"
    assert result["metrics"]["period_return"] == pytest.approx(0.1)
    assert result["metrics"]["volatility"] is None
    assert result["metrics"]["max_drawdown"] is None
    assert result["metrics"]["sharpe"] is None


def test_unit_nav_only_is_not_silently_substituted(monkeypatch):
    patch_sources(monkeypatch, nav_frame([1.0, 1.1, 1.2], include_cumulative=False))

    result = overview_service.overview("161725", ResearchPeriod.ALL, AS_OF)

    assert result["sample_count"] == 0
    assert result["metric_status"] == "insufficient"
    assert result["quality_status"] == "missing"
    assert result["curve"] == []
    assert all(value is None for value in result["metrics"].values())


def test_duplicate_dates_keep_last_and_are_disclosed(monkeypatch):
    nav = nav_frame([999.0, 1.0, 1.2], ["2026-02-10", "2026-02-10", "2026-02-11"])
    patch_sources(monkeypatch, nav)

    result = overview_service.overview("161725", ResearchPeriod.ALL, AS_OF)

    assert result["metrics"]["period_return"] == pytest.approx(0.2)
    assert result["duplicate_dates"] == 1
    assert result["quality_status"] == "warning"


def test_overview_api_uses_camel_case_and_rejects_unknown_period(monkeypatch):
    nav = nav_frame([1.0, 1.1, 1.21])
    monkeypatch.setattr(overview_service.fund_service, "nav_history", lambda code: nav)
    monkeypatch.setattr(
        overview_service.fund_service,
        "list_all",
        lambda: [SimpleNamespace(code="161725", name="测试基金")],
    )
    monkeypatch.setattr(overview_service.market_service, "index_kline", lambda code, period: [])
    monkeypatch.setattr(
        "api.analysis._ensure_exists",
        lambda code: None,
    )

    with TestClient(app) as client:
        response = client.get("/api/analysis/overview/161725?period=1m")
        invalid = client.get("/api/analysis/overview/161725?period=1M")

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == "1m"
    assert payload["sampleCount"] == 0  # 固定历史样本不在实时近一个月内
    assert "metricStatus" in payload and "qualityNotes" in payload
    assert invalid.status_code == 422
