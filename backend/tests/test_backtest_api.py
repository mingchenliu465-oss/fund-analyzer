"""回测接口层测试：数据层全部 mock，只验证接口的取数编排与错误翻译。

引擎本身的计算与结论规则由 test_backtest_engine.py / test_backtest_report.py
覆盖，这里不重复；本文件守住的是：正常返回完整报告、代码不存在 404、
数据源不可用 503、历史不足 3 年按引擎纪律 refused、净值为空 503、
累计净值口径不满足时把引擎的 ValueError 原样转成 422。
"""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import backtest as backtest_api


def _frame(dates, cumulative):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(dates),
            "单位净值": cumulative,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(cumulative),
        }
    )


def _long_frame(years=8):
    idx = pd.bdate_range("2018-01-02", periods=years * 250)
    t = np.arange(len(idx))
    values = 1.5 * (1 + 0.25 * np.sin(t / 90.0)) * (1 + t * 0.00008)
    return _frame(idx, list(values))


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(backtest_api.router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


def _mock_funds(monkeypatch, funds):
    monkeypatch.setattr(backtest_api.fund_service, "list_all", lambda: funds)


def _mock_nav(monkeypatch, frame):
    monkeypatch.setattr(backtest_api.fund_service, "nav_history", lambda code: frame)


def test_backtest_ok_returns_full_report(client, monkeypatch):
    _mock_funds(monkeypatch, [SimpleNamespace(code="161725", name="招商中证白酒")])
    _mock_nav(monkeypatch, _long_frame())
    resp = client.get("/api/backtest/161725")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["code"] == "161725"
    assert body["name"] == "招商中证白酒"
    assert body["refusal_reason"] is None
    assert len(body["combos"]) == 6  # 6 种组合全部列示，不许只报最优
    for combo in body["combos"]:
        assert combo["conclusion"] in ("成立", "不成立", "证据不足")
        assert combo["yearly"]
    assert body["disclosures"]  # 披露块必须全量带上
    assert any("幸存者偏差" in d for d in body["disclosures"])


def test_backtest_unknown_code_returns_404(client, monkeypatch):
    _mock_funds(monkeypatch, [SimpleNamespace(code="161725", name="招商中证白酒")])
    _mock_nav(monkeypatch, _long_frame())
    resp = client.get("/api/backtest/999999")
    assert resp.status_code == 404
    assert "999999" in resp.json()["detail"]


def test_backtest_fund_list_unavailable_returns_503(client, monkeypatch):
    _mock_funds(monkeypatch, [])
    resp = client.get("/api/backtest/161725")
    assert resp.status_code == 503


def test_backtest_short_history_is_refused_by_engine(client, monkeypatch):
    _mock_funds(monkeypatch, [SimpleNamespace(code="161725", name="招商中证白酒")])
    _mock_nav(monkeypatch, _long_frame(years=2))
    resp = client.get("/api/backtest/161725")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "refused"
    assert "不足 3 年" in body["refusal_reason"]
    assert body["combos"] == []


def test_backtest_empty_nav_returns_503(client, monkeypatch):
    _mock_funds(monkeypatch, [SimpleNamespace(code="161725", name="招商中证白酒")])
    _mock_nav(monkeypatch, pd.DataFrame())
    resp = client.get("/api/backtest/161725")
    assert resp.status_code == 503
    assert "净值" in resp.json()["detail"]


def test_backtest_missing_cumulative_nav_returns_422(client, monkeypatch):
    _mock_funds(monkeypatch, [SimpleNamespace(code="161725", name="招商中证白酒")])
    idx = pd.bdate_range("2018-01-02", periods=8 * 250)
    unit_only = pd.DataFrame(
        {"净值日期": idx, "单位净值": [1.0] * len(idx), "日增长率": [0.0] * len(idx)}
    )
    _mock_nav(monkeypatch, unit_only)
    resp = client.get("/api/backtest/161725")
    assert resp.status_code == 422
    assert resp.json()["detail"]  # 引擎的原样原因，不许吞掉
