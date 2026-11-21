"""实验 v14（滚动保序校准映射）单元测试与离线回归测试。"""

from __future__ import annotations

import math
from pathlib import Path
import sqlite3
import sys

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from experiments.forecast_baseline import HORIZON_A_DAYS, HORIZON_B_DAYS, TEST_START_INDEX, WINDOW_DAYS
from experiments.forecast_scorecard import build_scorecard
from experiments.forecast_v1 import PredictionV1, generate_predictions_v1
from experiments.forecast_v14 import (
    DEFAULT_DB_PATH,
    FIT_WINDOW_PREDS,
    MIN_CALIBRATION_PREDS,
    PROB_CLIP_MAX,
    PROB_CLIP_MIN,
    REFIT_INTERVAL_DAYS,
    SHRINKAGE_LAMBDA,
    TARGET_FUNDS,
    calibrate_predictions_v14,
    evaluate_all_groups,
    fit_isotonic_calibrator,
    format_report,
    generate_predictions_v14,
)


def _synthetic_nav(length: int = 1800) -> list[float]:
    """构造确定性的波动净值序列，兼含上涨段与回撤段。"""
    nav = [1.0]
    for i in range(1, length):
        cyc = 0.0004 + 0.012 * math.sin(i / 27.0) + 0.008 * math.cos(i / 61.0)
        nav.append(max(0.2, nav[-1] * (1.0 + cyc)))
    return nav


def _make_dummy_v1_series(n: int = 400) -> list[PredictionV1]:
    preds: list[PredictionV1] = []
    for idx in range(n):
        raw = 0.15 + 0.70 * ((idx % 20) / 19.0)
        outcome = 1 if (idx % 3 == 0 and raw > 0.45) or (idx % 5 == 0) else 0
        preds.append(
            PredictionV1(
                index=500 + idx,
                bucket="<5%",
                baseline_prob=0.50,
                state_prob=raw,
                outcome=outcome,
                train_n=250 + idx,
                bucket_train_n=100 + idx // 2,
                state_fallback=False,
                baseline_weighted=0.48,
                weight_n=200.0,
                bucket_weight_n=80.0,
            )
        )
    return preds


def test_constants_are_locked_and_valid() -> None:
    assert FIT_WINDOW_PREDS == 756
    assert MIN_CALIBRATION_PREDS == 252
    assert REFIT_INTERVAL_DAYS == 63
    assert math.isclose(SHRINKAGE_LAMBDA, 0.20)
    assert 0.0 < PROB_CLIP_MIN < PROB_CLIP_MAX < 1.0


def test_isotonic_calibrator_monotonicity_and_shrinkage() -> None:
    # 故意构造非单调经验序列：低分箱反常偏高，PAVA 应将其合并为单调非减
    raw_probs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    outcomes = [1, 0, 0, 0, 1, 0, 1, 1]
    cal = fit_isotonic_calibrator(raw_probs, outcomes, shrinkage_lambda=0.20)

    assert len(cal.xs) == len(cal.ys)
    assert all(cal.ys[i] <= cal.ys[i + 1] + 1e-12 for i in range(len(cal.ys) - 1))

    grid = [i / 100.0 for i in range(101)]
    mapped = [cal.predict(x) for x in grid]
    assert all(mapped[i] <= mapped[i + 1] + 1e-12 for i in range(len(mapped) - 1))
    assert all(PROB_CLIP_MIN <= p <= PROB_CLIP_MAX for p in mapped)


def test_cold_start_and_quarterly_refit_schedule() -> None:
    horizon = 20
    v1_series = _make_dummy_v1_series(n=120)
    cal_series = calibrate_predictions_v14(
        v1_preds=v1_series,
        horizon=horizon,
        fit_window=60,
        min_samples=30,
        refit_interval=15,
    )

    assert len(cal_series) == len(v1_series)
    # 决策下标 < min_samples + horizon 时，已到期样本不足 30，必须保持冷启动退化
    for pos in range(29 + horizon):
        assert cal_series[pos].state_fallback is True
        assert math.isclose(cal_series[pos].state_prob, v1_series[pos].state_prob)
        assert cal_series[pos].refit_index is None

    # 脱离冷启动后，同一重拟合周期内 refit_index 保持锁定，每隔 15 个交易日更新一次
    active = [p for p in cal_series if not p.state_fallback]
    assert len(active) > 0
    first_refit = active[0].refit_index
    assert first_refit == active[0].index
    for p in active[:15]:
        assert p.refit_index == first_refit
    assert active[15].refit_index == active[15].index


def test_strict_no_lookahead_invariance() -> None:
    """篡改决策日 t 之后的未来净值，t 及之前所有预测结果必须逐点完全不变。"""
    nav_orig = _synthetic_nav(2200)
    cutoff = 1600
    nav_altered = list(nav_orig)
    for i in range(cutoff + 1, len(nav_altered)):
        nav_altered[i] = nav_altered[i - 1] * 0.97  # 未来暴跌

    for kind in ("A", "B"):
        preds_orig = generate_predictions_v14(nav_orig, kind=kind)
        preds_alt = generate_predictions_v14(nav_altered, kind=kind)

        orig_prefix = [p for p in preds_orig if p.index <= cutoff]
        alt_prefix = [p for p in preds_alt if p.index <= cutoff]

        assert len(orig_prefix) == len(alt_prefix) > 0
        for p1, p2 in zip(orig_prefix, alt_prefix):
            assert p1.index == p2.index
            assert math.isclose(p1.state_prob, p2.state_prob, rel_tol=0.0, abs_tol=1e-12)
            assert math.isclose(p1.baseline_prob, p2.baseline_prob, rel_tol=0.0, abs_tol=1e-12)
            assert p1.refit_index == p2.refit_index
            assert p1.calibration_n == p2.calibration_n


def test_scorecard_compatibility_on_synthetic_nav() -> None:
    nav = _synthetic_nav(1800)
    years = [2015 + (i // 252) for i in range(len(nav))]
    for kind, horizon in (("A", HORIZON_A_DAYS), ("B", HORIZON_B_DAYS)):
        preds = generate_predictions_v14(nav, kind=kind)
        assert len(preds) > 0
        sc = build_scorecard(
            preds,
            [years[p.index] for p in preds],
            history_days=len(nav),
            horizon=horizon,
        )
        assert sc.n == len(preds)
        assert sc.brier_state is not None
        assert sc.brier_baseline is not None
        assert len(sc.calibration) == 5


@pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="local nav_history.db not present",
)
def test_evaluate_four_target_funds_and_report() -> None:
    """若本地存在 nav_history.db，端到端跑通 4 只目标基金 A/B 共 8 组并校验报告格式。"""
    with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        if not tables:
            pytest.skip("nav_history.db has no tables")

    comparisons = evaluate_all_groups(db_path=DEFAULT_DB_PATH, funds=TARGET_FUNDS)
    assert len(comparisons) == 8
    report = format_report(comparisons)
    assert "实验 v14 报告" in report
    assert "8 组同表对比" in report
    for code, _ in TARGET_FUNDS:
        assert code in report