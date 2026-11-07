"""历史频率服务验证：已知答案、证据纪律、接口契约。

期望值全部由测试内独立手算，不调用服务内部函数反推；频率口径与
条目 7 可行性报告第 2 节一致（6 个月=126、12 个月=252 个交易日）。
"""

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import history_frequency as api_module
from services import fund_service, history_frequency
from services.history_frequency import (
    HORIZON_6M,
    HORIZON_12M,
    compute_history_frequency,
    run_history_frequency,
)


def _series(values, start="2020-01-02"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def _frame(values, start="2020-01-02"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.DataFrame(
        {
            "净值日期": idx,
            "单位净值": values,
            "累计净值": values,
            "日增长率": [0.0] * len(values),
        }
    )


# ---------------------------------------------------------------------------
# 已知答案：单调上涨——全部为正、无回撤、无回本事件
# ---------------------------------------------------------------------------

def test_monotonic_rise_all_positive_no_drawdown():
    nav = _series([1.0 + 0.001 * i for i in range(400)])
    out = compute_history_frequency(nav)
    assert out["origins_6m"] == 400 - HORIZON_6M  # 274
    assert out["origins_12m"] == 400 - HORIZON_12M  # 148
    assert out["non_overlapping_blocks_12m"] == 400 // HORIZON_12M  # 1
    assert out["positive_6m"] == {"freq": 1.0, "count": 274, "n": 274}
    assert out["positive_12m"] == {"freq": 1.0, "count": 148, "n": 148}
    for key in ("5", "10", "15"):
        assert out["drawdown_exceed_12m"][key] == {"freq": 0.0, "count": 0, "n": 148}
    assert out["payback_5pct"]["events"] == 0
    assert out["payback_5pct"]["recovered"] == 0
    assert out["payback_5pct"]["unrecovered"] == 0
    assert out["payback_5pct"]["unrecovered_share"] is None
    assert out["payback_5pct"]["median_days"] is None
    assert out["payback_5pct"]["evidence"] == "不足"
    # 148 个起点全部落在 2020 年
    assert out["yearly"] == [
        {
            "year": 2020,
            "n": 148,
            "positive_12m": {"freq": 1.0, "count": 148, "n": 148},
            "drawdown_gt_10pct": {"freq": 0.0, "count": 0, "n": 148},
            "evidence": "足",
        }
    ]


# ---------------------------------------------------------------------------
# 已知答案：单调下跌——全部为负、回撤全超 15%、回本全部未回升
# ---------------------------------------------------------------------------

def test_monotonic_fall_all_negative_full_drawdown():
    nav = _series([2.0 - 0.002 * i for i in range(400)])
    out = compute_history_frequency(nav)
    assert out["positive_6m"]["freq"] == 0.0
    assert out["positive_12m"]["freq"] == 0.0
    # 起点 i 的 12 个月回撤 = 1 - (2-0.002(i+252))/(2-0.002i)，i=0 时 25.2%，
    # 随 i 增大而增大，全部超过 15%。
    for key in ("5", "10", "15"):
        assert out["drawdown_exceed_12m"][key]["freq"] == 1.0
        assert out["drawdown_exceed_12m"][key]["count"] == 148
    assert out["payback_5pct"]["events"] == 368  # 起点 0..367 能在 504 天内跌破起点 5%
    assert out["payback_5pct"]["recovered"] == 0
    assert out["payback_5pct"]["unrecovered"] == 368
    assert out["payback_5pct"]["unrecovered_share"] == pytest.approx(1.0)
    assert out["payback_5pct"]["median_days"] is None  # 无回升样本，中位数不存在
    assert out["payback_5pct"]["evidence"] == "足"  # 事件数 368 >= 30


# ---------------------------------------------------------------------------
# 已知答案：一次 6%  dip 后回升——逐项手算频率与回本天数
# ---------------------------------------------------------------------------

def test_single_dip_hand_computed():
    # 300 天 1.00，第 300 天跌到 0.94，第 301 天仍 0.94，第 302 天回到 1.00，
    # 此后涨到 1.02 并维持到第 500 天，共 501 个点。
    values = [1.00] * 300 + [0.94, 0.94] + [1.02] * 199
    assert len(values) == 501
    nav = _series(values)
    out = compute_history_frequency(nav)

    # 6 个月：i=176..299（126 个起点，1.00→1.02）+ i=300,301（0.94→1.02）
    # = 126 个为正；其余起点 6 个月后净值持平或更低。
    assert out["positive_6m"] == {"freq": pytest.approx(126 / 375), "count": 126, "n": 375}
    # 12 个月：i+252 >= 302 即 i >= 50 时 12 个月后为 1.02，i=50..248 共 199 个。
    assert out["positive_12m"] == {"freq": pytest.approx(199 / 249), "count": 199, "n": 249}
    # 12 个月窗口 [i, i+252] 只在 i+252 >= 300（即 i >= 48）时才包含第 300/301 天
    # 的 0.94：i=48..248 共 201 个起点相对高点 1.00 回撤恰为 6%，超 5%；
    # i=0..47 的窗口内全是 1.00，无回撤。超 10%/15% 全不中。
    assert out["drawdown_exceed_12m"]["5"] == {"freq": pytest.approx(201 / 249), "count": 201, "n": 249}
    assert out["drawdown_exceed_12m"]["10"] == {"freq": 0.0, "count": 0, "n": 249}
    assert out["drawdown_exceed_12m"]["15"] == {"freq": 0.0, "count": 0, "n": 249}
    # 回本（口径：起点=全部交易日；跌破=净值首次跌破决策日净值的 95%；
    # 天数=回升日−决策日）：只有 i=0..299 的起点能在 504 天内跌破（第 300 天
    # 的 0.94 < 0.95×1.00），共 300 个事件；都在第 302 天回到 1.00，
    # 回本天数 = 302−i，即 3..302；中位 152.5、p75 227.25、p90 272.1。
    payback = out["payback_5pct"]
    assert payback["events"] == 300
    assert payback["recovered"] == 300
    assert payback["unrecovered"] == 0
    assert payback["unrecovered_share"] == pytest.approx(0.0)
    assert payback["median_days"] == pytest.approx(152.5)
    assert payback["p75_days"] == pytest.approx(227.25)
    assert payback["p90_days"] == pytest.approx(272.1)
    assert payback["evidence"] == "足"
    # 249 个起点全部落在 2020 年（2020-01-02 起 249 个交易日约到 12 月中旬）。
    assert len(out["yearly"]) == 1
    assert out["yearly"][0]["year"] == 2020
    assert out["yearly"][0]["n"] == 249
    assert out["yearly"][0]["positive_12m"]["count"] == 199
    assert out["yearly"][0]["drawdown_gt_10pct"]["count"] == 0
    assert out["yearly"][0]["evidence"] == "足"


# ---------------------------------------------------------------------------
# 边界：序列太短时 6/12 个月统计分段缺失，不得崩溃
# ---------------------------------------------------------------------------

def test_short_series_partial_stats():
    assert compute_history_frequency(_series([1.0] * 100))["positive_6m"] is None
    out = compute_history_frequency(_series([1.0] * 200))
    assert out["positive_6m"] == {"freq": 0.0, "count": 0, "n": 74}
    assert out["positive_12m"] is None
    assert out["drawdown_exceed_12m"] == {}
    assert out["yearly"] == []


def test_year_with_few_origins_marked_insufficient():
    # 跨两年：2020 年起点 261 个、2021 年起点只有 7 个（序列共 520 点）。
    nav = _series([1.0 + 0.001 * i for i in range(520)])
    out = compute_history_frequency(nav)
    by_year = {row["year"]: row for row in out["yearly"]}
    assert by_year[2020]["n"] == 261
    assert by_year[2020]["evidence"] == "足"
    assert by_year[2021]["n"] == 7
    assert by_year[2021]["evidence"] == "不足"


# ---------------------------------------------------------------------------
# 证据纪律：run_history_frequency 层（历史不足 3 年拒绝；起点不足降级）
# ---------------------------------------------------------------------------

def test_refused_when_history_under_three_years():
    # 约 2 年交易日（522 点），跨度不足 3 年。
    frame = _frame([1.0 + 0.001 * i for i in range(522)])
    report = run_history_frequency(frame, "161725", "测试基金")
    assert report["status"] == "refused"
    assert "不足 3 年" in report["refusal_reason"]
    assert report["positive_12m"] is None


def test_empty_frame_raises_like_backtest_engine():
    # 与回测引擎一致：空帧在清洗层（累计净值缺失）即抛 ValueError，
    # 接口层把它翻译成 422；API 层对空帧先返回 503，服务层收不到空帧。
    frame = pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"])
    with pytest.raises(ValueError, match="净值数据为空"):
        run_history_frequency(frame, "161725")


def test_insufficient_when_origins_under_100():
    # 周频日期：300 行跨约 5.75 年（历史够 3 年），但 12 个月起点仅 48 个。
    idx = pd.date_range("2020-01-06", periods=300, freq="W-MON")
    frame = pd.DataFrame(
        {
            "净值日期": idx,
            "单位净值": [1.0 + 0.001 * i for i in range(300)],
            "累计净值": [1.0 + 0.001 * i for i in range(300)],
            "日增长率": [0.0] * 300,
        }
    )
    report = run_history_frequency(frame, "161725")
    assert report["status"] == "ok"
    assert report["evidence"] == "不足"
    assert "不足 100 个" in report["evidence_reason"]
    assert report["origins_12m"] == 48
    # 数字照常列示，只是不下结论。
    assert report["positive_12m"]["n"] == 48


def test_ok_report_shape_and_disclosures():
    frame = _frame([1.0 + 0.001 * i for i in range(800)], start="2019-01-02")
    report = run_history_frequency(frame, "161725", "测试基金")
    assert report["status"] == "ok"
    assert report["evidence"] == "足"
    assert report["data_start"] == "2019-01-02"
    assert report["positive_12m"]["freq"] == 1.0
    assert report["non_overlapping_blocks_12m"] == 800 // HORIZON_12M
    assert any("只描述过去" in d for d in report["disclosures"])
    assert any("不重叠" in d for d in report["disclosures"])
    assert any("幸存者偏差" in d for d in report["disclosures"])
    assert report["disclosures"][-1] == history_frequency.FIXED_DISCLAIMER


def test_dirty_rows_dropped_and_counted():
    values = [1.0 + 0.001 * i for i in range(800)]
    values[100] = -1.0  # 脏行：非正净值
    values[200] = float("nan")  # 脏行：缺失
    frame = _frame(values, start="2019-01-02")
    report = run_history_frequency(frame, "161725")
    assert report["status"] == "ok"
    assert report["dropped_rows"] == 2
    assert any("剔除 2 条无效净值记录" in d for d in report["disclosures"])


# ---------------------------------------------------------------------------
# 接口契约：TestClient + monkeypatch（不联网）
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        fund_service, "list_all",
        lambda: [SimpleNamespace(code="161725", name="测试基金")],
    )
    monkeypatch.setattr(
        fund_service, "nav_history",
        lambda code: _frame([1.0 + 0.001 * i for i in range(800)], start="2019-01-02"),
    )
    app = FastAPI()
    app.include_router(api_module.router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


def test_api_ok(client):
    resp = client.get("/api/history-frequency/161725")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "161725"
    assert body["status"] == "ok"
    assert body["positive_12m"]["freq"] == 1.0
    assert body["yearly"]
    assert body["disclosures"]


def test_api_unknown_code_404(client):
    assert client.get("/api/history-frequency/999999").status_code == 404


def test_api_empty_fund_list_503(client, monkeypatch):
    monkeypatch.setattr(fund_service, "list_all", lambda: [])
    assert client.get("/api/history-frequency/161725").status_code == 503


def test_api_empty_nav_503(client, monkeypatch):
    monkeypatch.setattr(
        fund_service, "nav_history",
        lambda code: pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"]),
    )
    assert client.get("/api/history-frequency/161725").status_code == 503
