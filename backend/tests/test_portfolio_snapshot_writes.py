"""组合快照写入路径测试。

规则（2026-10-24 补上写入路径后）：
- 快照只能由显式写操作（新增/修改/卖出/删除持仓、自动定投）成功后记录；
- GET /api/portfolio 等只读接口绝不写快照；
- _upsert_snapshot 按日期幂等：同一天多次写只保留一行，数值更新为最新。
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import database
from api import portfolio
from services import portfolio_service as service


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "portfolio.db")
    database.init_db()
    monkeypatch.setattr(service, "_resolve_fund_name", lambda code, name: name)
    monkeypatch.setattr(service, "_build_nav_map", lambda: {"000001": (2, "2026-09-18")})
    monkeypatch.setattr(
        service.fund_service, "get_by_code",
        lambda code: SimpleNamespace(nav=2, nav_date="2026-09-18"),
    )
    monkeypatch.setattr(service.fund_service, "_load_fund_list", lambda: [])
    monkeypatch.setattr(service.fund_service, "is_current_nav", lambda *_: True)
    app = FastAPI()
    app.include_router(portfolio.router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


PAYLOAD = dict(fund_code="000001", fund_name="测试基金", fund_type="股票型",
               buy_date="2026-08-01", buy_amount=100, buy_nav=1, shares=100, fee=1)


def _snapshot_count() -> int:
    conn = database.get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM portfolio_snapshots"
        ).fetchone()["c"]
    finally:
        conn.close()


def test_write_holding_records_one_snapshot(client):
    assert _snapshot_count() == 0
    created = client.post("/api/portfolio/holdings", json=PAYLOAD)
    assert created.status_code == 201
    assert _snapshot_count() == 1
    history = client.get("/api/portfolio/history?period=ALL").json()["points"]
    assert len(history) == 1
    # 份额 100 × 当前净值 2 = 200，与组合总览口径一致。
    assert history[0]["total_value"] == 200


def test_get_requests_never_add_snapshots(client):
    assert client.post("/api/portfolio/holdings", json=PAYLOAD).status_code == 201
    assert _snapshot_count() == 1
    for _ in range(3):
        assert client.get("/api/portfolio").status_code == 200
        assert client.get("/api/portfolio/history?period=ALL").status_code == 200
        assert client.get("/api/portfolio/holdings").status_code == 200
    assert _snapshot_count() == 1


def test_same_day_repeated_writes_stay_one_row(client):
    first = client.post("/api/portfolio/holdings", json=PAYLOAD)
    assert first.status_code == 201
    url = "/api/portfolio/holdings/" + str(first.json()["id"])
    # 同一天内修改、再新增一笔，都只更新当日同一行，不新增行数。
    assert client.put(url, json={**PAYLOAD, "notes": "updated"}).status_code == 200
    assert client.post("/api/portfolio/holdings", json=PAYLOAD).status_code == 201
    assert _snapshot_count() == 1
    history = client.get("/api/portfolio/history?period=ALL").json()["points"]
    assert len(history) == 1
    # 两笔持仓后当日总价值更新为 400。
    assert history[0]["total_value"] == 400
