"""概率预测实验 v5 的测试：混合+门槛叠加定义、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v5 与 v2/v3/v4 的关系测试以三者的公开输出为
参照（v5 的定义本身就是“对 v2 输出先混合、后门槛”）；小参数
（窗口/期限/半衰期）只用于让手算可行，默认参数口径由实验报告的真实
数据运行覆盖。
"""

import pytest

from experiments.forecast_baseline import (
    BUCKET_LT5,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_scorecard import MIN_BUCKET_N
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNAL_NONE,
    generate_predictions_v2,
    weighted_predict_at_v2,
)
from experiments.forecast_v3 import BLEND_W, generate_predictions_v3
from experiments.forecast_v4 import GATE_MIN_WEIGHT_N, generate_predictions_v4
from experiments.forecast_v5 import (
    generate_predictions_v5,
    weighted_predict_at_v5,
)

# 与 test_forecast_baseline / test_forecast_v1 / test_forecast_v2 /
# test_forecast_v3 / test_forecast_v4 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]


def test_drawdown_blend_gate_hand_computed():
    # 手算（窗口 3、期限 2、决策日 8、半衰期 2 天、收缩伪计数 1）：
    # 与 test_forecast_v3.test_drawdown_blend_hand_computed /
    # test_forecast_v4.test_drawdown_gate_hand_computed 同一情形：
    # 训练起点 s in [2, 6]，标签 [0, 0, 1, 0, 1]，回撤档位
    # [<5%, <5%, >10%, >10%, <5%]；决策日 8 属 <5% 档。
    # 权重 w = 0.5 ** ((8 - s) / 2)：
    #   s=2: 0.125；s=3: 0.5**2.5；s=4: 0.25；s=5: 0.5**1.5；s=6: 0.5。
    # 权重和 = 0.125 + 0.5**2.5 + 0.25 + 0.5**1.5 + 0.5；
    # 加权标签和 = 0.25（s=4）+ 0.5（s=6）= 0.75；
    # 加权基准率 = 0.75 / 权重和。
    # 同态（<5%）加权标签和 = 0.5（s=6），加权样本量 =
    #   0.125 + 0.5**2.5 + 0.5 ≈ 0.802 < 门槛 30 ——门槛触发：
    #   混合后概率 = 0.5 × 未混合状态概率 + 0.5 × 加权基准率，
    #   其中未混合状态概率 = (0.5 + 1 × 加权基准率) / (同态加权样本量 + 1)；
    #   触发门槛后 v5 状态概率 = 加权基准率。
    # 无加权基准率（比较基准）= 2/5 = 0.4；决策日结果标签为 1。
    w2 = 0.5 ** 2.5
    w5 = 0.5 ** 1.5
    weight_n = 0.125 + w2 + 0.25 + w5 + 0.5
    baseline_w = 0.75 / weight_n
    state_wn = 0.125 + w2 + 0.5
    ungated = (0.5 + baseline_w) / (state_wn + 1.0)
    blended = 0.5 * ungated + 0.5 * baseline_w
    assert state_wn < GATE_MIN_WEIGHT_N
    pred = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == BUCKET_LT5
    assert pred.signal == SIGNAL_DRAWDOWN
    assert pred.baseline_prob == pytest.approx(0.4)
    assert pred.baseline_weighted == pytest.approx(baseline_w)
    assert pred.weight_n == pytest.approx(weight_n)
    assert pred.bucket_weight_n == pytest.approx(state_wn)
    assert pred.gated is True
    assert pred.state_prob == pytest.approx(baseline_w)
    assert pred.blended_state_prob == pytest.approx(blended)
    assert pred.ungated_state_prob == pytest.approx(ungated)
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_gate_threshold_parameter_and_boundary():
    # 门槛参数只用于测试：门槛放小到 0.5 时同态加权样本量 0.802 已过门槛，
    # 门槛不触发，状态概率即混合后概率；门槛恰好等于加权样本量时也不触发
    # （触发条件是严格小于）。三者逐项核对 v2/v3 的公开输出。
    w2 = 0.5 ** 2.5
    state_wn = 0.125 + w2 + 0.5
    v2 = weighted_predict_at_v2(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    blended = 0.5 * v2.state_prob + 0.5 * v2.baseline_weighted
    pred_small_gate = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, gate_min_weight_n=0.5,
    )
    assert pred_small_gate is not None
    assert pred_small_gate.gated is False
    assert pred_small_gate.state_prob == pytest.approx(blended)
    assert pred_small_gate.blended_state_prob == pytest.approx(blended)
    pred_boundary = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, gate_min_weight_n=state_wn,
    )
    assert pred_boundary is not None
    assert pred_boundary.gated is False
    assert pred_boundary.state_prob == pytest.approx(blended)
    pred_default = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    assert pred_default is not None
    assert pred_default.gated is True
    assert pred_default.state_prob == pytest.approx(pred_default.baseline_weighted)


def test_relation_matches_v3_and_v4():
    # v5 的定义：未触发日状态概率 = v3（混合后）；触发日 = 加权基准率，
    # 与 v4 的触发日相同；其余字段与 v2/v3/v4 逐点一致（A/B 两类）。
    # 长序列上触发与未触发两种情形都应出现。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(700)]
    assert min(nav) > 0
    for kind in ("A", "B"):
        v5_preds = generate_predictions_v5(nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250)
        v3_preds = generate_predictions_v3(nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250)
        v4_preds = generate_predictions_v4(nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250)
        assert len(v5_preds) == len(v3_preds) == len(v4_preds)
        assert v5_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p5, p3, p4 in zip(v5_preds, v3_preds, v4_preds):
            assert p5.index == p3.index == p4.index
            assert p5.bucket == p3.bucket == p4.bucket
            assert p5.bucket_weight_n == pytest.approx(p3.bucket_weight_n, abs=1e-12)
            assert p5.gated == p4.gated == (p3.bucket_weight_n < GATE_MIN_WEIGHT_N)
            assert p5.blended_state_prob == pytest.approx(p3.state_prob, abs=1e-12)
            assert p5.ungated_state_prob == pytest.approx(p4.ungated_state_prob, abs=1e-12)
            if p5.gated:
                gated_seen += 1
                assert p5.state_prob == pytest.approx(p5.baseline_weighted, abs=1e-12)
                assert p5.state_prob == pytest.approx(p4.state_prob, abs=1e-12)
            else:
                ungated_seen += 1
                assert p5.state_prob == pytest.approx(p3.state_prob, abs=1e-12)
            assert p5.baseline_prob == pytest.approx(p3.baseline_prob, abs=1e-12)
            assert p5.baseline_weighted == pytest.approx(p3.baseline_weighted, abs=1e-12)
            assert p5.outcome == p3.outcome
            assert p5.train_n == p3.train_n
            assert p5.bucket_train_n == p3.bucket_train_n
            assert p5.state_fallback == p3.state_fallback
        assert gated_seen > 0, f"{kind} 应有触发门槛的决策日"
        assert ungated_seen > 0, f"{kind} 应有未触发门槛的决策日"


def test_none_signal_identity():
    # 无信号：v2 的状态概率已等于加权基准率，混合与门槛都是恒等变换。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(700)]
    for kind in ("A", "B"):
        v5_preds = generate_predictions_v5(nav, kind, SIGNAL_NONE, window=30, test_start=250)
        v2_preds = generate_predictions_v2(nav, kind, SIGNAL_NONE, window=30, test_start=250)
        assert len(v5_preds) == len(v2_preds)
        for p5, p2 in zip(v5_preds, v2_preds):
            assert p5.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p5.blended_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p5.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。混合与门槛判断只用当天的
    # 量（v2 状态概率、加权基准率、bucket_weight_n），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    before = {
        t: weighted_predict_at_v5(base, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5)
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v5(mutated, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5)
        for t in range(130, 160)
    }
    assert all(v is not None for v in before.values())
    for idx in before:
        assert before[idx].baseline_prob == pytest.approx(after[idx].baseline_prob)
        assert before[idx].state_prob == pytest.approx(after[idx].state_prob)
        assert before[idx].blended_state_prob == pytest.approx(
            after[idx].blended_state_prob
        )
        assert before[idx].ungated_state_prob == pytest.approx(
            after[idx].ungated_state_prob
        )
        assert before[idx].baseline_weighted == pytest.approx(
            after[idx].baseline_weighted
        )
        assert before[idx].gated == after[idx].gated
        assert before[idx].bucket == after[idx].bucket
    for idx in range(130, 158):
        assert before[idx].outcome == after[idx].outcome
    assert before[158].outcome != after[158].outcome


def test_generate_matches_direct():
    # 递推实现与逐项直算在决策日上逐点一致（A/B 两类）。
    # B 类期限 252 天：序列须足够长，取 700 天使 A/B 两类都有充足预测；
    # B 类只抽查部分决策日以控运行时长。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(700)]
    for kind in ("A", "B"):
        preds = generate_predictions_v5(nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250)
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v5(
                nav, pred.index, horizon, label_fn, SIGNAL_DRAWDOWN, window=30,
            )
            assert direct is not None
            assert direct.state_prob == pytest.approx(pred.state_prob, abs=1e-9)
            assert direct.blended_state_prob == pytest.approx(
                pred.blended_state_prob, abs=1e-9
            )
            assert direct.ungated_state_prob == pytest.approx(
                pred.ungated_state_prob, abs=1e-9
            )
            assert direct.baseline_prob == pytest.approx(pred.baseline_prob)
            assert direct.baseline_weighted == pytest.approx(
                pred.baseline_weighted, abs=1e-9
            )
            assert direct.gated == pred.gated
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0，叠加后状态概率仍为 0。
    nav = [1000.0 - i for i in range(200)]
    pred = weighted_predict_at_v5(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.blended_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：混合权重 0.5（从 v3 继承）、门槛 30.0（从 v4 继承，借用成绩
    # 单 MIN_BUCKET_N 的证据规则，见模块 docstring）、半衰期 756 天、
    # 收缩伪计数 50（均从 v1 继承、未改）。
    assert BLEND_W == 0.5
    assert GATE_MIN_WEIGHT_N == 30.0
    assert MIN_BUCKET_N == 30
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v5([10.0 + 0.01 * i for i in range(30)], "A") == []
    with pytest.raises(ValueError):
        generate_predictions_v5([10.0] * 30, "A", "nope")
    with pytest.raises(ValueError):
        generate_predictions_v5([10.0] * 30, "C")
    with pytest.raises(ValueError):
        weighted_predict_at_v5(NAV, 8, 2, label_positive_return, "nope")
    # 门槛为 0 时永不触发，退化为 v3（定义检查）；混合权重为 1 时退化为 v4。
    from experiments.forecast_v3 import weighted_predict_at_v3
    from experiments.forecast_v4 import weighted_predict_at_v4

    pred_gate0 = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, gate_min_weight_n=0.0,
    )
    pred_v3_direct = weighted_predict_at_v3(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    pred_v4_direct = weighted_predict_at_v4(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    assert pred_gate0 is not None and pred_v3_direct is not None
    assert pred_gate0.gated is False
    assert pred_gate0.state_prob == pytest.approx(pred_v3_direct.state_prob)
    pred_blend1 = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, blend_w=1.0,
    )
    assert pred_blend1 is not None and pred_v4_direct is not None
    assert pred_blend1.gated == pred_v4_direct.gated
    assert pred_blend1.state_prob == pytest.approx(pred_v4_direct.state_prob)
    assert pred_blend1.blended_state_prob == pytest.approx(
        pred_v4_direct.ungated_state_prob
    )
    # 混合权重为 0 时状态概率恒等于加权基准率（定义检查）。
    pred_blend0 = weighted_predict_at_v5(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, blend_w=0.0,
    )
    assert pred_blend0 is not None
    assert pred_blend0.state_prob == pytest.approx(pred_blend0.baseline_weighted)
