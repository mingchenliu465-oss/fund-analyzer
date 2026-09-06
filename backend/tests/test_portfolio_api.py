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
    monkeypatch.setattr(service, "_build_nav_map", lambda: {"000001": 2})
    monkeypatch.setattr(service.fund_service, "get_by_code", lambda code: SimpleNamespace(nav=2))
    monkeypatch.setattr(service.fund_service, "_load_fund_list", lambda: [])
    monkeypatch.setattr(service, "_open_fund_nav_change", lambda code: (2, 1.9, 100 / 19))
    app = FastAPI()
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(review.router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


PAYLOAD = dict(fund_code="000001", fund_name="测试基金", fund_type="股票型",
               buy_date="2026-08-01", buy_amount=100, buy_nav=1, shares=100, fee=1)


def test_holdings_lifecycle_and_snapshot(client):
    created = client.post("/api/portfolio/holdings", json=PAYLOAD)
    assert created.status_code == 201
    url = "/api/portfolio/holdings/" + str(created.json()["id"])
    assert client.get(url).json()["current_value"] == 200
    for _ in range(2):
        summary = client.get("/api/portfolio").json()
        assert summary["total_profit"] == 99
    history = client.get("/api/portfolio/history?period=ALL").json()["points"]
    assert len(history) == 1
    assert history[0]["total_value"] == 200
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
