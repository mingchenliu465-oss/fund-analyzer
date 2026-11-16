"""概率预测实验 v8 的测试：相对极性门槛定义、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v8 与 v2 的关系测试以 v2 的公开输出为参照
（v8 的定义本身就是“对 v2 输出做相对极性门槛判断”）；小参数
（窗口/期限/半衰期）只用于让手算可行，默认参数口径由实验报告的真实
数据运行覆盖。v8 不需要日期输入。
"""

import math

import pytest

from experiments.forecast_baseline import (
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
from experiments.forecast_v8 import (
    RELATIVE_POLARITY_GAP,
    generate_predictions_v8,
    weighted_predict_at_v8,
)

# 与 test_forecast_baseline / test_forecast_v1 / ... / test_forecast_v7
# 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]

# 决策日 8 的手算情形（窗口 3、期限 2、半衰期 1 天、收缩伪计数 1），
# 与 v7 测试同一组数：训练起点 s in [2, 6]，自定义标签 [0, 1, 1, 0, 1]，
# 回撤档位 [<5%, <5%, >10%, >10%, <5%]；决策日 8 属 <5% 档，标签为 1。
# <5% 档正标签占比约 0.9474（v7 在此触发），但加权基准率约 0.7097，
# 相对差距约 0.2377 < 0.5 ——v8 在此**不**触发：这是 v7 与 v8 分得开
# 的直接证据（绝对一边倒、但与全局构成差得不够远）。
_CUSTOM_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 6: 1, 8: 1}


def _custom_label_fn(nav, start, horizon):
    """测试用标签函数：只在手算表里有值的起点返回标签，其余返回 None。"""
    return _CUSTOM_LABELS.get(start)


def _hand_values_day8(half_life: float = 1.0):
    """决策日 8 的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((8 - s) / half_life) for s in (2, 3, 4, 5, 6)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4] + w[6]) / weight_n
    bucket_wn = w[2] + w[3] + w[6]
    bucket_ws = w[3] + w[6]
    pos_frac = bucket_ws / bucket_wn
    gap = abs(pos_frac - baseline_w)
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "pos_frac": pos_frac,
        "gap": gap,
        "ungated": ungated,
    }


# 决策日 9 的手算情形（窗口 3、期限 2、半衰期 10000 天、收缩伪计数 1）：
# 训练起点 s in [2, 7]，自定义标签只有 s=7 为 1，其余为 0；回撤档位
# [<5%, <5%, >10%, >10%, <5%, 5%-10%]；决策日 9 属 5%-10% 档，标签为 1。
# 5%-10% 档训练标签只有 s=7（标签 1）：正标签占比 = 1.0；
# 加权基准率约 1/6 ≈ 0.1667；相对差距约 0.8333 >= 0.5 ——门槛触发。
_TRIGGER_LABELS = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 1, 9: 1}


def _trigger_label_fn(nav, start, horizon):
    """触发情形的测试用标签函数。"""
    return _TRIGGER_LABELS.get(start)


def _hand_values_day9(half_life: float = 10000.0):
    """决策日 9 的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((9 - s) / half_life) for s in range(2, 8)}
    weight_n = sum(w.values())
    baseline_w = w[7] / weight_n
    pos_frac = 1.0
    gap = abs(pos_frac - baseline_w)
    ungated = (w[7] + baseline_w) / (w[7] + 1.0)
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": w[7],
        "bucket_ws": w[7],
        "pos_frac": pos_frac,
        "gap": gap,
        "ungated": ungated,
    }


def test_relative_gap_hand_computed_triggered():
    # 半衰期 10000 天：5%-10% 档正标签占比 1.0、加权基准率约 1/6，
    # 相对差距约 0.8333 >= 0.5，门槛触发，状态概率 = 加权基准率。
    hv = _hand_values_day9()
    assert hv["pos_frac"] == pytest.approx(1.0)
    assert hv["baseline_w"] == pytest.approx(1.0 / 6.0, abs=1e-4)
    assert hv["gap"] == pytest.approx(5.0 / 6.0, abs=1e-4)
    assert hv["gap"] >= 0.5
    pred = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == "5%-10%"
    assert pred.signal == SIGNAL_DRAWDOWN
    assert pred.baseline_prob == pytest.approx(1.0 / 6.0, abs=1e-4)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is True
    assert pred.pos_label_frac == pytest.approx(hv["pos_frac"])
    assert pred.gap == pytest.approx(hv["gap"])
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 6
    assert pred.bucket_train_n == 1
    assert pred.outcome == 1


def test_relative_gap_hand_computed_not_triggered():
    # 半衰期 1 天：<5% 档正标签占比约 0.9474（v7 在此触发），但相对差距
    # 约 0.2377 < 0.5，v8 不触发，状态概率 = v2 未加门槛值。
    hv = _hand_values_day8()
    assert hv["pos_frac"] == pytest.approx(0.28125 / 0.296875)
    assert hv["gap"] == pytest.approx(0.2377, abs=1e-4)
    assert hv["gap"] < 0.5
    pred = weighted_predict_at_v8(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=1.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.baseline_prob == pytest.approx(0.6)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is False
    assert pred.pos_label_frac == pytest.approx(hv["pos_frac"])
    assert pred.gap == pytest.approx(hv["gap"])
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_gap_threshold_parameter_and_boundary():
    # 以触发情形（决策日 9、相对差距约 0.8333）为基底：
    # 门槛 0.9 时不触发；门槛恰好等于相对差距时触发（触发条件是 >=）；
    # 默认门槛 0.5 时触发；门槛 1.0 时不触发；门槛 0 时恒触发。
    hv = _hand_values_day9()
    gap = hv["gap"]
    v2 = weighted_predict_at_v2(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    pred_high = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        gap_threshold=0.9,
    )
    assert pred_high is not None
    assert pred_high.gated is False
    assert pred_high.state_prob == pytest.approx(v2.state_prob)
    pred_boundary = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        gap_threshold=gap,
    )
    assert pred_boundary is not None
    assert pred_boundary.gated is True
    assert pred_boundary.state_prob == pytest.approx(
        pred_boundary.baseline_weighted
    )
    pred_default = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert pred_default is not None
    assert pred_default.gated is True
    assert pred_default.state_prob == pytest.approx(pred_default.baseline_weighted)
    pred_one = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        gap_threshold=1.0,
    )
    assert pred_one is not None
    assert pred_one.gated is False
    pred_zero = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        gap_threshold=0.0,
    )
    assert pred_zero is not None
    assert pred_zero.gated is True
    assert pred_zero.state_prob == pytest.approx(pred_zero.baseline_weighted)


def _long_series():
    # 1500 天、横跨 2010–2014 五个日历年（与 v6/v7 测试同一序列）：
    # 递推与直算的一致性用它。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(1500)]
    assert min(nav) > 0
    return nav


def _sine_series():
    # 1500 天正弦净值（周期约 157 天，无趋势），振幅在第 750 天切换：
    # 前半段振幅 30（峰谷跌幅约 5.8% < 10%，B 类标签恒为 0），后半段
    # 振幅 120（峰谷跌幅约 21% > 10%，B 类标签恒为 1）。B 类上触发与未
    # 触发两种情形都应出现（A 类上相对差距达不到 0.5，关系测试不依赖它）。
    return [
        1000.0 + (30.0 if i < 750 else 120.0) * math.sin(i / 25.0)
        for i in range(1500)
    ]


def _crash_recovery_series():
    # 0–499 天平盘 1000；500–530 天跌到 600；530 天起每天 +0.35 缓慢修复：
    # 修复期回撤（250 天窗口）仍 >10%，126 天远期收益为正——>10% 态的标
    # 签与全局构成差得足够远，A/B 两类上触发与未触发两种情形都应出现。
    nav = [1000.0]
    for i in range(1, 1500):
        if i < 500:
            nav.append(1000.0)
        elif i <= 530:
            nav.append(1000.0 - (1000.0 - 600.0) * (i - 499) / 31.0)
        else:
            nav.append(600.0 + 0.35 * (i - 530))
    assert min(nav) > 0
    return nav


def test_relation_matches_v2():
    # v8 的定义：未触发日状态概率 = v2；触发日 = 加权基准率；其余字段
    # 与 v2 逐点一致（A/B 两类）。崩盘修复序列（窗口 250）上触发与未触发
    # 两种情形都应出现。
    nav = _crash_recovery_series()
    for kind in ("A", "B"):
        v8_preds = generate_predictions_v8(
            nav, kind, SIGNAL_DRAWDOWN, window=250, test_start=250
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=250, test_start=250
        )
        assert len(v8_preds) == len(v2_preds)
        assert v8_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p8, p2 in zip(v8_preds, v2_preds):
            assert p8.index == p2.index
            assert p8.bucket == p2.bucket
            assert p8.bucket_weight_n == pytest.approx(p2.bucket_weight_n, abs=1e-12)
            assert p8.gated == (
                p2.bucket_weight_n > 0
                and p8.gap >= RELATIVE_POLARITY_GAP
            )
            assert 0.0 <= p8.pos_label_frac <= 1.0
            assert 0.0 <= p8.gap <= 1.0
            if p2.bucket_weight_n > 0:
                assert p8.gap == pytest.approx(
                    abs(p8.pos_label_frac - p2.baseline_weighted), abs=1e-12
                )
            else:
                assert p8.gated is False
                assert p8.pos_label_frac == pytest.approx(0.0)
                assert p8.gap == pytest.approx(0.0)
            assert p8.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            if p8.gated:
                gated_seen += 1
                assert p8.state_prob == pytest.approx(p8.baseline_weighted, abs=1e-12)
            else:
                ungated_seen += 1
                assert p8.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p8.baseline_prob == pytest.approx(p2.baseline_prob, abs=1e-12)
            assert p8.baseline_weighted == pytest.approx(p2.baseline_weighted, abs=1e-12)
            assert p8.outcome == p2.outcome
            assert p8.train_n == p2.train_n
            assert p8.bucket_train_n == p2.bucket_train_n
            assert p8.state_fallback == p2.state_fallback
        assert gated_seen > 0, f"{kind} 应有触发门槛的决策日"
        assert ungated_seen > 0, f"{kind} 应有未触发门槛的决策日"


def test_none_signal_identity():
    # 无信号：该态即全部训练集，态内正占比恒等于加权基准率，相对差距恒
    # 为 0，门槛是恒等变换（触发与否状态概率都不变）。
    nav = _sine_series()
    for kind in ("A", "B"):
        v8_preds = generate_predictions_v8(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        assert len(v8_preds) == len(v2_preds)
        for p8, p2 in zip(v8_preds, v2_preds):
            assert p8.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p8.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p8.gated is False
            assert p8.gap == pytest.approx(0.0, abs=1e-9)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。相对极性只用当天的训练
    # 集（t 之前的数据），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    before = {
        t: weighted_predict_at_v8(
            base, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5
        )
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v8(
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
        assert before[idx].gap == pytest.approx(after[idx].gap)
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
        preds = generate_predictions_v8(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v8(
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
            assert direct.gap == pytest.approx(pred.gap, abs=1e-9)
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0，正标签占比 0、加权基准
    # 率 0，相对差距 0 ——门槛不触发（与 v7 不同：v7 的绝对极性在此触发，
    # 多数占比 1.0）。v8 在此等于 v2。
    nav = [1000.0 - i for i in range(200)]
    pred = weighted_predict_at_v8(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.pos_label_frac == pytest.approx(0.0)
    assert pred.gap == pytest.approx(0.0)
    assert pred.gated is False
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：相对极性门槛 0.5（“差半个概率尺度”的唯一对称分界，见模块
    # docstring）、半衰期 756 天、收缩伪计数 50（均从 v1 继承、未改）。
    assert RELATIVE_POLARITY_GAP == 0.5
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    nav = _long_series()
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v8([10.0 + 0.01 * i for i in range(30)], "A") == []
    with pytest.raises(ValueError):
        generate_predictions_v8(nav, "A", "nope")
    with pytest.raises(ValueError):
        generate_predictions_v8(nav, "C")
    with pytest.raises(ValueError):
        weighted_predict_at_v8(NAV, 9, 2, label_positive_return, "nope")
    # 门槛为 0 时恒触发，退化为加权基准率（定义检查）。
    pred_gate0 = weighted_predict_at_v8(
        NAV, 9, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0, gap_threshold=0.0,
    )
    assert pred_gate0 is not None
    assert pred_gate0.gated is True
    assert pred_gate0.state_prob == pytest.approx(pred_gate0.baseline_weighted)
