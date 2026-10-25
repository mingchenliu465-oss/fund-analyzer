"""诚实回测报告层测试：口径回归、6 组合完整性、拒绝规则、披露与文案红线。"""

import pandas as pd
import pytest

from services.backtest_service import (
    FeeModel,
    PRESET_HOLD_MONTHS,
    PRESET_THRESHOLDS,
    render_report_markdown,
    run_backtest,
)


def _frame(dates, cumulative, unit=None):
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(dates),
            "单位净值": unit if unit is not None else cumulative,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(cumulative),
        }
    )


def _long_frame(years=8):
    idx = pd.bdate_range("2018-01-02", periods=years * 250)
    # 带涨跌的确定性序列（避免全程单调导致从不触发或必然触发）
    import numpy as np

    t = np.arange(len(idx))
    values = 1.5 * (1 + 0.25 * np.sin(t / 90.0)) * (1 + t * 0.00008)
    return _frame(idx, list(values)), idx


# ---------------------------------------------------------------------------
# 口径回归：除息日单位净值跳水时，引擎必须按累计净值算（161725 教训的构造版）
# ---------------------------------------------------------------------------

def test_engine_uses_cumulative_nav_not_unit_nav():
    idx = pd.bdate_range("2018-01-02", periods=8 * 250)
    import numpy as np

    t = np.arange(len(idx))
    cumulative = 1.0 + t * (1.2 / len(idx))  # 累计净值 8 年线性涨到 2.2
    unit = cumulative.copy()
    unit[len(idx) // 2 :] *= 0.8  # 中途一次"分红除息"：单位净值从此低 20%
    frame = _frame(idx, list(cumulative), list(unit))
    report = run_backtest(frame, "TEST01")
    assert report["status"] == "ok"
    combo = report["combos"][0]
    # 样本外段基准收益的手算（累计口径）：(1-申购费) * 期末/期初 - 1
    eval_start = 250
    expected_benchmark = (1 - 0.0015) * cumulative[-1] / cumulative[eval_start] - 1
    assert combo["benchmark_return"] == pytest.approx(expected_benchmark, abs=1e-6)
    # 若误用单位净值，基准收益会低约 20%，与期望值差距必须显著（防测试空转）
    unit_expected = (1 - 0.0015) * unit[-1] / unit[eval_start] - 1
    assert abs(combo["benchmark_return"] - unit_expected) > 0.05


def test_missing_cumulative_nav_column_raises():
    frame = pd.DataFrame(
        {"净值日期": pd.to_datetime(["2020-01-02", "2020-01-03"]), "单位净值": [1.0, 1.1]}
    )
    with pytest.raises(ValueError):
        run_backtest(frame, "TEST02")


# ---------------------------------------------------------------------------
# 6 种组合必须全列示，结论只能出自三段式
# ---------------------------------------------------------------------------

def test_report_contains_all_six_preset_combos():
    frame, _ = _long_frame()
    report = run_backtest(frame, "TEST03")
    assert report["status"] == "ok"
    assert len(report["combos"]) == 6
    grid = {(c["threshold"], c["hold_months"]) for c in report["combos"]}
    assert grid == {(t, h) for t in PRESET_THRESHOLDS for h in PRESET_HOLD_MONTHS}
    for combo in report["combos"]:
        assert combo["conclusion"] in {"成立", "不成立", "证据不足"}
        assert combo["conclusion_reason"]
        assert len(combo["yearly"]) >= 5
        failed_from_rows = [r["year"] for r in combo["yearly"] if r["failed"]]
        assert combo["failed_years"] == failed_from_rows


# ---------------------------------------------------------------------------
# 拒绝规则：历史不足 3 年直接拒绝出结论
# ---------------------------------------------------------------------------

def test_history_shorter_than_3_years_is_refused():
    idx = pd.bdate_range("2024-01-02", periods=2 * 250)
    frame = _frame(idx, [1.0 + i * 0.001 for i in range(len(idx))])
    report = run_backtest(frame, "TEST04")
    assert report["status"] == "refused"
    assert "不足 3 年" in report["refusal_reason"]
    assert report["combos"] == []


# ---------------------------------------------------------------------------
# 披露完整性与文案红线
# ---------------------------------------------------------------------------

def test_disclosures_and_wording_red_lines():
    frame, _ = _long_frame()
    report = run_backtest(frame, "TEST05")
    markdown = render_report_markdown(report)
    # 必须出现的披露
    for keyword in ["幸存者偏差", "未消除", "T+1", "历史验证不代表未来表现", "全部列示"]:
        assert keyword in markdown, keyword
    # 费用三档口径必须逐项标注
    assert "法定下限" in markdown and "证监会公告〔2017〕12 号" in markdown
    assert "假设值" in markdown and "示例口径" in markdown
    # 文案红线：报告全文不得出现这两个词组
    assert "预测" not in markdown
    assert "推荐买入" not in markdown


def test_refused_report_still_has_disclosures():
    idx = pd.bdate_range("2024-01-02", periods=100)
    frame = _frame(idx, [1.0] * 100)
    report = run_backtest(frame, "TEST06")
    markdown = render_report_markdown(report)
    assert "拒绝出结论" in markdown
    assert "历史验证不代表未来表现" in markdown
