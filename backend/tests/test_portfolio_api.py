from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import database
from api import portfolio, review
from services import portfolio_service as service


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "portfolio.db")
    database.init_db()
    monkeypatch.setattr(service, "_resolve_fund_name", lambda code, name: name)
    # 净值映射现在携带观测日（code -> (nav, nav_date)）。
    monkeypatch.setattr(service, "_build_nav_map", lambda: {"000001": (2, "2026-09-18")})
    monkeypatch.setattr(
        service.fund_service, "get_by_code",
        lambda code: SimpleNamespace(nav=2, nav_date="2026-09-18"),
    )
    monkeypatch.setattr(service.fund_service, "_load_fund_list", lambda: [])
    monkeypatch.setattr(service, "_open_fund_nav_change", lambda code: (2, 1.9, 100 / 19))
    # 这里隔离交易日历：本文件验证的是持仓/组合的管道，freshness 判定本身由
    # test_nav_freshness.py 用真实/注入日历单独覆盖。
    monkeypatch.setattr(service.fund_service, "is_current_nav", lambda *_: True)
    app = FastAPI()
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(review.router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


PAYLOAD = dict(fund_code="000001", fund_name="测试基金", fund_type="股票型",
               buy_date="2026-08-01", buy_amount=100, buy_nav=1, shares=100, fee=1)


def test_holdings_lifecycle_without_implicit_snapshot(client):
    created = client.post("/api/portfolio/holdings", json=PAYLOAD)
    assert created.status_code == 201
    url = "/api/portfolio/holdings/" + str(created.json()["id"])
    assert client.get(url).json()["current_value"] == 200
    for _ in range(2):
        summary = client.get("/api/portfolio").json()
        assert summary["total_profit"] == 99
    # GET /api/portfolio 是纯读取：不再顺带写入当日快照，所以历史应为空。
    history = client.get("/api/portfolio/history?period=ALL").json()["points"]
    assert history == []
    attribution = client.get("/api/portfolio/attribution")
    assert attribution.status_code == 200
    assert attribution.json()["today_return"] == 10
    assert client.get("/api/review/daily?provider=rules").json()["provider"] == "rules"
    assert client.put(url, json={**PAYLOAD, "notes": "updated"}).json()["notes"] == "updated"
    sold = client.post(url + "/sell", json=dict(sell_date="2026-09-01", sell_amount=200, sell_nav=2))
    assert sold.json()["is_sold"] is True
    assert client.get("/api/portfolio/holdings").json() == []
    assert len(client.get("/api/portfolio/holdings?include_sold=true").json()) == 1
    assert client.delete(url).status_code == 200
    assert client.get(url).status_code == 404
    assert client.delete(url).status_code == 404


def test_invalid_amount_does_not_write(client):
    assert client.post("/api/portfolio/holdings", json={**PAYLOAD, "shares": -1}).status_code == 422
    assert client.get("/api/portfolio/holdings").json() == []


def test_get_portfolio_never_writes_snapshots(client):
    """GET /api/portfolio 必须是纯读取，不能产生任何写操作。"""
    def snapshot_count() -> int:
        conn = database.get_connection()
        try:
            return conn.execute(
                "SELECT COUNT(*) AS c FROM portfolio_snapshots"
            ).fetchone()["c"]
        finally:
            conn.close()

    assert snapshot_count() == 0
    for _ in range(3):
        assert client.get("/api/portfolio").status_code == 200
    assert snapshot_count() == 0


def test_drip_creates_weekly_lots(client, monkeypatch):
    monkeypatch.setattr(service.fund_service, "_fetch_nav_history", lambda code: pd.DataFrame({
        "净值日期": pd.to_datetime(["2026-08-10", "2026-08-17"]), "单位净值": [2, 4]}))
    response = client.post("/api/portfolio/auto-drip", json=dict(
        fund_code="000001", fund_name="测试基金", amount=100, frequency="weekly",
        start_date="2026-08-05", end_date="2026-08-18", day_of_week=1))
    assert response.status_code == 201
    assert response.json()["created"] == 2
    assert [item["shares"] for item in response.json()["items"]] == [50, 25]


def test_empty_review_falls_back_to_rules(client):
    response = client.get("/api/review/daily")
    assert response.status_code == 200
    assert response.json()["provider"] == "rules"
    assert "暂无持仓" in response.json()["summary"]
