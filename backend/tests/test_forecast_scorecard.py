"""条目 9 预测评估框架的测试：校准分档、技能分数、逐年失效、证据不足规则。

期望值全部在测试内手算，不调用模块内部函数反推；预测替身只带成绩单
用到的字段（state_prob / baseline_prob / outcome / bucket / index）。
"""

import pytest
from types import SimpleNamespace

from experiments.forecast_scorecard import (
    assess_evidence,
    build_scorecard,
    bucket_verdict,
    calibration_bucket_index,
    calibration_table,
    failure_years,
    skill_score,
    yearly_table,
)


def pred(state, baseline, outcome, bucket="<5%", index=0):
    return SimpleNamespace(
        state_prob=state, baseline_prob=baseline, outcome=outcome,
        bucket=bucket, index=index,
    )


def test_calibration_bucket_edges():
    assert calibration_bucket_index(0.0) == 0
    assert calibration_bucket_index(0.199) == 0
    assert calibration_bucket_index(0.2) == 1
    assert calibration_bucket_index(0.4) == 2
    assert calibration_bucket_index(0.6) == 3
    assert calibration_bucket_index(0.8) == 4
    assert calibration_bucket_index(1.0) == 4


def test_calibration_table_hand_computed():
    preds = [
        pred(0.0, 0.5, 0),
        pred(0.1, 0.5, 1),  # 0%–20% 档：n=2，均值 0.05，实际 0.5，差 -0.45
        pred(0.2, 0.5, 1),  # 20%–40% 档：n=1，均值 0.2，实际 1.0，差 -0.8
        pred(0.5, 0.5, 0),  # 40%–60% 档：n=1，均值 0.5，实际 0，差 0.5
        # 60%–80% 档空
        pred(0.8, 0.5, 1),
        pred(1.0, 0.5, 1),  # 80%–100% 档：n=2，均值 0.9，实际 1.0，差 -0.1
    ]
    rows = calibration_table(preds)
    assert [r.label for r in rows] == ["0%–20%", "20%–40%", "40%–60%", "60%–80%", "80%–100%"]
    assert rows[0].n == 2 and rows[0].mean_pred == pytest.approx(0.05)
    assert rows[0].actual_rate == pytest.approx(0.5) and rows[0].gap == pytest.approx(-0.45)
    assert rows[1].n == 1 and rows[1].mean_pred == pytest.approx(0.2)
    assert rows[1].actual_rate == pytest.approx(1.0) and rows[1].gap == pytest.approx(-0.8)
    assert rows[2].n == 1 and rows[2].gap == pytest.approx(0.5)
    assert rows[3].n == 0 and rows[3].mean_pred is None
    assert rows[3].actual_rate is None and rows[3].gap is None
    assert rows[4].n == 2 and rows[4].mean_pred == pytest.approx(0.9)
    assert rows[4].actual_rate == pytest.approx(1.0) and rows[4].gap == pytest.approx(-0.1)


def test_skill_score_hand_computed():
    assert skill_score(0.20, 0.25) == pytest.approx(0.2)
    assert skill_score(0.30, 0.25) == pytest.approx(-0.2)
    assert skill_score(0.0, 0.0) is None  # 退化：分母为零，不是满分
    assert skill_score(None, 0.25) is None
    assert skill_score(0.2, None) is None


def test_yearly_table_and_failure_years():
    preds = [
        pred(0.5, 0.4, 1, index=0),
        pred(0.5, 0.4, 0, index=1),  # 2020：状态 0.25 vs 基准 0.26，未失效
        pred(1.0, 0.5, 0, index=2),  # 2021：状态 1.0 vs 基准 0.25，失效
        pred(0.0, 0.0, 0, index=3),
        pred(0.0, 0.0, 0, index=4),  # 2022：双方均为 0，相等不算失效
    ]
    years = [2020, 2020, 2021, 2022, 2022]
    rows = yearly_table(preds, years)
    assert [(r.year, r.n) for r in rows] == [(2020, 2), (2021, 1), (2022, 2)]
    assert rows[0].brier_state == pytest.approx(0.25)
    assert rows[0].brier_baseline == pytest.approx(0.26)
    assert rows[0].state_worse is False
    assert rows[1].brier_state == pytest.approx(1.0) and rows[1].state_worse is True
    assert rows[2].brier_state == pytest.approx(0.0) and rows[2].state_worse is False
    assert failure_years(rows) == [2021]
    with pytest.raises(ValueError):
        yearly_table(preds, [2020])


def test_bucket_verdict_thresholds():
    assert bucket_verdict(0) == "absent"
    assert bucket_verdict(1) == "insufficient"
    assert bucket_verdict(29) == "insufficient"
    assert bucket_verdict(30) == "ok"


def test_assess_evidence_thresholds():
    few = [pred(0.5, 0.5, 1, bucket="<5%", index=i) for i in range(50)]
    ev = assess_evidence(few, history_days=2000)
    assert ev.verdict == "insufficient"
    assert any("50" in r for r in ev.reasons)
    assert ev.bucket_verdicts["<5%"] == "ok"  # 50 个样本外已过档位阈值
    assert ev.bucket_verdicts["5%-10%"] == "absent"

    many = [pred(0.5, 0.5, 1, bucket="<5%", index=i) for i in range(150)]
    ev_short_history = assess_evidence(many, history_days=1000)
    assert ev_short_history.verdict == "insufficient"
    assert any("1000" in r for r in ev_short_history.reasons)

    ev_ok = assess_evidence(many, history_days=2000)
    assert ev_ok.verdict == "sufficient" and ev_ok.reasons == []

    ev_explicit = assess_evidence(many, history_days=2000, bucket_ns={"<5%": 5, "5%-10%": 40})
    assert ev_explicit.bucket_verdicts == {"<5%": "insufficient", "5%-10%": "ok", ">10%": "absent"}


def test_build_scorecard_small_and_empty():
    preds = [
        pred(0.5, 0.4, 1, bucket="<5%", index=0),
        pred(0.5, 0.4, 0, bucket="<5%", index=1),
        pred(1.0, 0.5, 0, bucket=">10%", index=2),
    ]
    card = build_scorecard(preds, [2020, 2020, 2021], history_days=2000, horizon=126)
    assert card.n == 3
    assert card.evidence.verdict == "insufficient"  # n < 100
    assert len(card.calibration) == 5
    assert card.failures == [2021]
    assert card.degenerate is False
    assert card.non_overlapping_blocks == 1  # (2-0)//126 + 1

    empty = build_scorecard([], [], history_days=2000, horizon=126)
    assert empty.n == 0 and empty.brier_state is None and empty.skill is None
    assert empty.yearly == [] and empty.failures == []
    assert empty.evidence.verdict == "insufficient"
    assert all(r.n == 0 for r in empty.calibration)


def test_build_scorecard_degenerate_not_a_perfect_score():
    # 150 个预测全为 0、结果全为 0：双方 Brier 均为 0，技能分数无法计算，
    # 整体证据虽足（n>=100 且历史足），但 degenerate 必须为真，不得读作满分。
    preds = [pred(0.0, 0.0, 0, bucket="<5%", index=i) for i in range(150)]
    card = build_scorecard(preds, [2020] * 150, history_days=3000, horizon=126)
    assert card.brier_state == pytest.approx(0.0)
    assert card.brier_baseline == pytest.approx(0.0)
    assert card.skill is None
    assert card.degenerate is True
    assert card.evidence.verdict == "sufficient"
    assert card.non_overlapping_blocks == 2  # (149-0)//126 + 1
