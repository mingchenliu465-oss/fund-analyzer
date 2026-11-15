"""概率预测实验 v7 的测试：标签极性门槛定义、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v7 与 v2 的关系测试以 v2 的公开输出为参照
（v7 的定义本身就是“对 v2 输出做标签极性门槛判断”）；小参数
（窗口/期限/半衰期）只用于让手算可行，默认参数口径由实验报告的真实
数据运行覆盖。v7 不需要日期输入。
"""

import math

import pytest

from experiments.forecast_baseline import (
    BUCKET_LT5,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNAL_NONE,
    generate_predictions_v2,
    weighted_predict_at_v2,
)
from experiments.forecast_v7 import (
    POLARITY_ONE_SIDED_SHARE,
    generate_predictions_v7,
    weighted_predict_at_v7,
)

# 与 test_forecast_baseline / test_forecast_v1 / ... / test_forecast_v6
# 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]

# 决策日 8 的手算情形（窗口 3、期限 2、半衰期 1 天、收缩伪计数 1），
# 用自定义标签函数控制各训练起点的标签（真实 A 类标签是 [0, 0, 1, 0, 1]，
# <5% 档的正标签占比只有约 0.62，触发不了极性门槛，须另造一边倒的情形）：
# 训练起点 s in [2, 6]，自定义标签 [0, 1, 1, 0, 1]，回撤档位
# [<5%, <5%, >10%, >10%, <5%]；决策日 8 属 <5% 档，标签为 1。
# <5% 档训练标签：s=2: 0、s=3: 1、s=6: 1；半衰期 1 天时权重
# w = 0.5 ** (8 - s)：w2 = 0.5**6、w3 = 0.5**5、w6 = 0.5**2；
# 正标签占比 = (w3 + w6) / (w2 + w3 + w6) = 0.28125 / 0.296875 ≈ 0.9474
# （多数占比同值），>= 0.9 ——门槛触发。无加权基准率 = 3/5 = 0.6。
_CUSTOM_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 6: 1, 8: 1}


def _custom_label_fn(nav, start, horizon):
    """测试用标签函数：只在手算表里有值的起点返回标签，其余返回 None。"""
    return _CUSTOM_LABELS.get(start)


def _hand_values(half_life: float = 1.0):
    """决策日 8 的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((8 - s) / half_life) for s in (2, 3, 4, 5, 6)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4] + w[6]) / weight_n
    bucket_wn = w[2] + w[3] + w[6]
    bucket_ws = w[3] + w[6]
    pos_frac = bucket_ws / bucket_wn
    majority = max(pos_frac, 1.0 - pos_frac)
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "pos_frac": pos_frac,
        "majority": majority,
        "ungated": ungated,
    }


def test_polarity_gate_hand_computed_triggered():
    # 半衰期 1 天：<5% 档正标签占比约 0.9474、多数占比同值 >= 0.9，
    # 门槛触发，状态概率 = 加权基准率。
    hv = _hand_values()
    assert hv["pos_frac"] == pytest.approx(0.28125 / 0.296875)
    assert hv["majority"] >= 0.9
    pred = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=1.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == BUCKET_LT5
    assert pred.signal == SIGNAL_DRAWDOWN
    assert pred.baseline_prob == pytest.approx(0.6)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is True
    assert pred.pos_label_frac == pytest.approx(hv["pos_frac"])
    assert pred.majority_share == pytest.approx(hv["majority"])
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_polarity_gate_hand_computed_not_triggered():
    # 半衰期 10000 天：权重几乎相等，<5% 档正标签占比 = 2/3，
    # 多数占比同值 < 0.9，不触发。
    hv = _hand_values(half_life=10000.0)
    assert 0.66 < hv["pos_frac"] < 0.67
    assert hv["majority"] < 0.9
    pred = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.gated is False
    assert pred.pos_label_frac == pytest.approx(hv["pos_frac"])
    assert pred.majority_share == pytest.approx(hv["majority"])
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])


def test_gate_threshold_parameter_and_boundary():
    # 以未触发情形（半衰期 10000 天、多数占比约 2/3）为基底：
    # 门槛 0.6 时触发（占比约 0.6667 >= 0.6）；门槛恰好等于多数占比时
    # 触发（触发条件是 >=）；门槛 0.9 时不触发；门槛 1.0 时不触发；
    # 门槛 0 时恒触发。
    hv = _hand_values(half_life=10000.0)
    majority = hv["majority"]
    v2 = weighted_predict_at_v2(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    pred_low = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        one_sided_share=0.6,
    )
    assert pred_low is not None
    assert pred_low.gated is True
    assert pred_low.state_prob == pytest.approx(pred_low.baseline_weighted)
    pred_boundary = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        one_sided_share=majority,
    )
    assert pred_boundary is not None
    assert pred_boundary.gated is True
    assert pred_boundary.state_prob == pytest.approx(pred_boundary.baseline_weighted)
    pred_default = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert pred_default is not None
    assert pred_default.gated is False
    assert pred_default.state_prob == pytest.approx(v2.state_prob)
    pred_one = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        one_sided_share=1.0,
    )
    assert pred_one is not None
    assert pred_one.gated is False
    pred_zero = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        one_sided_share=0.0,
    )
    assert pred_zero is not None
    assert pred_zero.gated is True
    assert pred_zero.state_prob == pytest.approx(pred_zero.baseline_weighted)


def _long_series():
    # 1500 天、横跨 2010–2014 五个日历年（与 v6 测试同一序列）：
    # 递推与直算的一致性用它；关系测试另用正弦序列（标签混合更充分）。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(1500)]
    assert min(nav) > 0
    return nav


def _sine_series():
    # 1500 天正弦净值（周期约 157 天，无趋势），振幅在第 750 天切换：
    # 前半段振幅 30（峰谷跌幅约 5.8% < 10%，B 类标签恒为 0），后半段
    # 振幅 120（峰谷跌幅约 21% > 10%，B 类标签恒为 1）。A 类 126 天收益
    # 的标签随相位正负交替。两段标签构成不同，同一回撤档内的训练标签既
    # 有混合、也有一边倒的时段，触发与未触发两种情形都应出现。
    # （纯正弦不行：252 天窗口总含一个完整峰谷，B 类标签恒为 1。）
    return [
        1000.0 + (30.0 if i < 750 else 120.0) * math.sin(i / 25.0)
        for i in range(1500)
    ]


def test_relation_matches_v2():
    # v7 的定义：未触发日状态概率 = v2；触发日 = 加权基准率；其余字段
    # 与 v2 逐点一致（A/B 两类）。正弦序列上触发与未触发两种情形都应出现。
    nav = _sine_series()
    for kind in ("A", "B"):
        v7_preds = generate_predictions_v7(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert len(v7_preds) == len(v2_preds)
        assert v7_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p7, p2 in zip(v7_preds, v2_preds):
            assert p7.index == p2.index
            assert p7.bucket == p2.bucket
            assert p7.bucket_weight_n == pytest.approx(p2.bucket_weight_n, abs=1e-12)
            assert p7.gated == (
                p2.bucket_weight_n > 0
                and p7.majority_share >= POLARITY_ONE_SIDED_SHARE
            )
            assert 0.0 <= p7.pos_label_frac <= 1.0
            assert 0.5 <= p7.majority_share <= 1.0 or p2.bucket_weight_n == 0
            if p2.bucket_weight_n > 0:
                assert p7.majority_share == pytest.approx(
                    max(p7.pos_label_frac, 1.0 - p7.pos_label_frac), abs=1e-12
                )
            else:
                assert p7.gated is False
                assert p7.pos_label_frac == pytest.approx(0.0)
                assert p7.majority_share == pytest.approx(0.0)
            assert p7.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            if p7.gated:
                gated_seen += 1
                assert p7.state_prob == pytest.approx(p7.baseline_weighted, abs=1e-12)
            else:
                ungated_seen += 1
                assert p7.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p7.baseline_prob == pytest.approx(p2.baseline_prob, abs=1e-12)
            assert p7.baseline_weighted == pytest.approx(p2.baseline_weighted, abs=1e-12)
            assert p7.outcome == p2.outcome
            assert p7.train_n == p2.train_n
            assert p7.bucket_train_n == p2.bucket_train_n
            assert p7.state_fallback == p2.state_fallback
        assert gated_seen > 0, f"{kind} 应有触发门槛的决策日"
        assert ungated_seen > 0, f"{kind} 应有未触发门槛的决策日"


def test_none_signal_identity():
    # 无信号：v2 的状态概率已等于加权基准率，门槛是恒等变换（触发与否
    # 状态概率都不变）。
    nav = _sine_series()
    for kind in ("A", "B"):
        v7_preds = generate_predictions_v7(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        assert len(v7_preds) == len(v2_preds)
        for p7, p2 in zip(v7_preds, v2_preds):
            assert p7.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p7.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。标签极性只用当天的训练
    # 集（t 之前的数据），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    before = {
        t: weighted_predict_at_v7(
            base, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5
        )
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v7(
            mutated, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5
        )
        for t in range(130, 160)
    }
    assert all(v is not None for v in before.values())
    for idx in before:
        assert before[idx].baseline_prob == pytest.approx(after[idx].baseline_prob)
        assert before[idx].state_prob == pytest.approx(after[idx].state_prob)
        assert before[idx].ungated_state_prob == pytest.approx(
            after[idx].ungated_state_prob
        )
        assert before[idx].baseline_weighted == pytest.approx(
            after[idx].baseline_weighted
        )
        assert before[idx].gated == after[idx].gated
        assert before[idx].pos_label_frac == pytest.approx(
            after[idx].pos_label_frac
        )
        assert before[idx].majority_share == pytest.approx(
            after[idx].majority_share
        )
        assert before[idx].bucket == after[idx].bucket
    for idx in range(130, 158):
        assert before[idx].outcome == after[idx].outcome
    assert before[158].outcome != after[158].outcome


def test_generate_matches_direct():
    # 递推实现与逐项直算在决策日上逐点一致（A/B 两类）。
    # B 类期限 252 天：序列须足够长，取 700 天使 A/B 两类都有充足预测；
    # B 类只抽查部分决策日以控运行时长。
    nav = _long_series()
    for kind in ("A", "B"):
        preds = generate_predictions_v7(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v7(
                nav, pred.index, horizon, label_fn, SIGNAL_DRAWDOWN, window=30
            )
            assert direct is not None
            assert direct.state_prob == pytest.approx(pred.state_prob, abs=1e-9)
            assert direct.ungated_state_prob == pytest.approx(
                pred.ungated_state_prob, abs=1e-9
            )
            assert direct.baseline_prob == pytest.approx(pred.baseline_prob)
            assert direct.baseline_weighted == pytest.approx(
                pred.baseline_weighted, abs=1e-9
            )
            assert direct.gated == pred.gated
            assert direct.pos_label_frac == pytest.approx(
                pred.pos_label_frac, abs=1e-9
            )
            assert direct.majority_share == pytest.approx(
                pred.majority_share, abs=1e-9
            )
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0，正标签占比 0、多数占比
    # 1.0，门槛触发，状态概率 = 加权基准率 = 0。
    nav = [1000.0 - i for i in range(200)]
    pred = weighted_predict_at_v7(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.pos_label_frac == pytest.approx(0.0)
    assert pred.majority_share == pytest.approx(1.0)
    assert pred.gated is True
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：标签极性门槛 0.9（“九成以上一边倒”的唯一对称分界，见模块
    # docstring）、半衰期 756 天、收缩伪计数 50（均从 v1 继承、未改）。
    assert POLARITY_ONE_SIDED_SHARE == 0.9
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    nav = _long_series()
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v7([10.0 + 0.01 * i for i in range(30)], "A") == []
    with pytest.raises(ValueError):
        generate_predictions_v7(nav, "A", "nope")
    with pytest.raises(ValueError):
        generate_predictions_v7(nav, "C")
    with pytest.raises(ValueError):
        weighted_predict_at_v7(NAV, 8, 2, label_positive_return, "nope")
    # 门槛为 0 时恒触发，退化为加权基准率（定义检查）。
    pred_gate0 = weighted_predict_at_v7(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=1.0, shrinkage_m=1.0, one_sided_share=0.0,
    )
    assert pred_gate0 is not None
    assert pred_gate0.gated is True
    assert pred_gate0.state_prob == pytest.approx(pred_gate0.baseline_weighted)
