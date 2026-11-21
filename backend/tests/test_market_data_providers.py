"""行情 Provider、显式降级与跨源核验测试（适配主干，不依赖 api.providers 路由）。"""
from datetime import date

import pandas as pd
import pytest

from models.market import KlinePoint
from services import market_data
from services.market_data import (
    IFindMarketDataProvider,
    PriceHistory,
)


def connector_frame():
    """与当前 iFinD 连接器真实返回字段同构的测试样本。"""
    return pd.DataFrame(
        {
            "open": [4005.9395, 4005.2511, 4007.3506],
            "high": [4038.815, 4028.7367, 4105.8575],
            "low": [3988.1681, 3969.5471, 3987.1516],
            "close": [4016.9179, 4008.8748, 4101.335],
            "volume": [244401128, 248779950, 246371975],
            "thscode": ["000300.SH"] * 3,
            "time": ["2026-11-02", "2026-11-03", "2026-11-04"],
            "currency": ["CNY"] * 3,
        }
    )


def clear_ifind_env(monkeypatch):
    monkeypatch.delenv("IFIND_ENABLED", raising=False)
    monkeypatch.delenv("IFIND_ACCESS_TOKEN", raising=False)


def test_ifind_is_blocked_without_credentials_or_transport(monkeypatch):
    clear_ifind_env(monkeypatch)
    provider = IFindMarketDataProvider()
    assert provider.status()["status"] == "blocked"
    assert provider.daily_history("000300.SH", date(2026, 11, 2), date(2026, 11, 4)).frame.empty

    monkeypatch.setenv("IFIND_ENABLED", "true")
    assert "IFIND_ACCESS_TOKEN" in provider.status()["detail"]
    monkeypatch.setenv("IFIND_ACCESS_TOKEN", "server-secret")
    assert "官方文档" in provider.status()["detail"]


def test_ifind_normalizes_real_connector_schema_without_filling_dates(monkeypatch):
    monkeypatch.setenv("IFIND_ENABLED", "true")
    monkeypatch.setenv("IFIND_ACCESS_TOKEN", "server-secret")
    provider = IFindMarketDataProvider(lambda ticker, start, end, token: connector_frame())
    result = provider.daily_history("000300.SH", date(2026, 11, 2), date(2026, 11, 4))

    assert result.status == "available"
    assert result.frame["close"].tolist() == pytest.approx([4016.9179, 4008.8748, 4101.335])
    assert result.frame["净值日期"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-11-02", "2026-11-03", "2026-11-04"
    ]
    assert "server-secret" not in str(result)


def test_ifind_failure_does_not_expose_access_token(monkeypatch):
    monkeypatch.setenv("IFIND_ENABLED", "true")
    monkeypatch.setenv("IFIND_ACCESS_TOKEN", "server-secret")

    def fail(ticker, start, end, token):
        raise RuntimeError(f"request rejected with {token}")

    result = IFindMarketDataProvider(fail).daily_history(
        "000300.SH", date(2026, 11, 2), date(2026, 11, 4)
    )
    assert result.status == "unavailable"
    assert "server-secret" not in result.note
    assert "RuntimeError" in result.note


def test_fallback_discloses_actual_akshare_source(monkeypatch):
    clear_ifind_env(monkeypatch)
    points = [
        KlinePoint(date="2026-11-02", open=10, high=11, low=9, close=10.5),
        KlinePoint(date="2026-11-03", open=10.5, high=11, low=10, close=10.8),
    ]
    monkeypatch.setattr(market_data.market_service, "index_kline", lambda code, period: points)
    result = market_data.history_with_fallback("000300.SH", date(2026, 11, 2), date(2026, 11, 3))

    assert result.provider == "akshare"
    assert result.fallback_from == "ifind"
    assert "akshare" in result.source
    assert "实际来源" in result.note
    assert result.frame["close"].tolist() == [10.5, 10.8]


def test_cross_source_comparison_uses_inner_join_and_counts_missing_dates():
    left = connector_frame().iloc[:2].copy()
    right = connector_frame().iloc[1:].copy()
    right.loc[right.index[0], "close"] = right.loc[right.index[0], "close"] * 1.01
    primary = PriceHistory(
        "000300.SH", "akshare", "主源", "available",
        market_data.normalize_price_frame(left, "000300.SH", date(2026, 11, 2), date(2026, 11, 4)),
    )
    secondary = PriceHistory(
        "000300.SH", "ifind", "核验源", "available",
        market_data.normalize_price_frame(right, "000300.SH", date(2026, 11, 2), date(2026, 11, 4)),
    )
    result = market_data.compare_history(primary, secondary)

    assert result["matched_samples"] == 1
    assert result["primary_only_dates"] == 1
    assert result["secondary_only_dates"] == 1
    assert result["status"] == "warning"
    assert result["differences"][0]["date"] == "2026-11-03"
    assert result["differences"][0]["difference_pct"] == pytest.approx(0.01, abs=1e-6)


def test_provider_registry_status_exposes_fund_nav_blocked(monkeypatch):
    clear_ifind_env(monkeypatch)
    body = market_data.provider_registry_status()

    assert body["active_provider"] == "akshare"
    assert body["fund_accumulated_nav_status"] == "blocked"
    assert {item["name"]: item["status"] for item in body["providers"]} == {
        "akshare": "available", "ifind": "blocked"
    }


def test_cross_source_check_returns_blocked_instead_of_fake_second_source(monkeypatch):
    clear_ifind_env(monkeypatch)
    monkeypatch.setattr(market_data.market_service, "index_kline", lambda code, period: [])
    body = market_data.cross_source_check("000300.SH", date(2026, 11, 2), date(2026, 11, 4))

    assert body["status"] == "blocked"
    assert body["matched_samples"] == 0
    assert body["differences"] == []
    assert "blocked" in body["note"]