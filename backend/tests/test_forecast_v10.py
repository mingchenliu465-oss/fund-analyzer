"""概率预测实验 v10 的测试：趋势段定义、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v10 与 v2 的关系测试以 v2 的公开输出为参照
（v10 的定义本身就是“对 v2 输出做趋势段集中度门槛判断”）；小参数
（窗口/期限/半衰期）只用于让手算可行，默认参数口径由实验报告的真实
数据运行覆盖。v10 不需要日期输入——趋势段由净值自身的均线状态决定。
"""

import math

import pytest

from experiments.forecast_baseline import (
    WINDOW_DAYS,
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
from experiments.forecast_v10 import (
    REGIME_MAX_DOMINANT_SHARE,
    UNDEFINED_SEGMENT,
    generate_predictions_v10,
    trend_segment_ids,
    weighted_predict_at_v10,
)

# 与 test_forecast_baseline / test_forecast_v1 / ... / test_forecast_v9
# 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]

# 交替净值序列（窗口 3 时趋势每天翻转，每段恰为一天）：
# 下标 2 起趋势为 below/above 交替，段编号即下标 - 2；
# 回撤档位同样交替：偶数下标 >10%、奇数下标 <5%。
NAV_ALT = [10.0, 12.0] * 6

# 决策日 7 的触发情形（窗口 3、期限 2、半衰期 10000 天、收缩伪计数 1）：
# 训练起点 s in [2, 5]，自定义标签 [0, 1, 1, 0]，回撤档位
# [>10%, <5%, >10%, <5%]；决策日 7 属 <5% 档，标签为 1。
# <5% 档训练起点 3、5 分属两段（段 1、段 3），权重各约一半——主导段
# 占比约 0.500035 >= 0.5，门槛触发（边界语义为“达到即触发”）。
_TRIGGER_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 7: 1}


def _trigger_label_fn(nav, start, horizon):
    """触发情形的测试用标签函数。"""
    return _TRIGGER_LABELS.get(start)


def _hand_values_day7_trigger(half_life: float = 10000.0):
    """决策日 7 触发情形的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((7 - s) / half_life) for s in (2, 3, 4, 5)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4]) / weight_n
    bucket_wn = w[3] + w[5]
    bucket_ws = w[3]
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    share = w[5] / bucket_wn  # 段 3（起点 5）的占比，略大于一半
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "ungated": ungated,
        "share": share,
    }


# 决策日 9 的不触发情形（窗口 3、期限 2、半衰期 10000 天、收缩伪计数 1）：
# 训练起点 s in [2, 7]，自定义标签 [0, 1, 1, 0, 0, 1]，回撤档位
# [>10%, <5%, >10%, <5%, >10%, <5%]；决策日 9 属 <5% 档，标签为 1。
# <5% 档训练起点 3、5、7 分属三段（段 1、段 3、段 5），权重各约三分
# 之一——主导段占比约 0.333 < 0.5，门槛不触发。
_NONTRIG_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 6: 0, 7: 1, 9: 1}


def _nontrig_label_fn(nav, start, horizon):
    """不触发情形的测试用标签函数。"""
    return _NONTRIG_LABELS.get(start)


def _hand_values_day9(half_life: float = 10000.0):
    """决策日 9 不触发情形的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((9 - s) / half_life) for s in (2, 3, 4, 5, 6, 7)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4] + w[7]) / weight_n
    bucket_wn = w[3] + w[5] + w[7]
    bucket_ws = w[3] + w[7]
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    share = w[7] / bucket_wn  # 段 5（起点 7）的占比，约三分之一
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "ungated": ungated,
        "share": share,
    }


def _pred_day7_trigger(**kwargs):
    """触发情形的默认参数调用。"""
    params = dict(window=3, half_life=10000.0, shrinkage_m=1.0)
    params.update(kwargs)
    return weighted_predict_at_v10(
        NAV_ALT, 7, 2, _trigger_label_fn, SIGNAL_DRAWDOWN, **params
    )


def test_trend_segment_ids():
    # 段 = 趋势状态连续相同的最大 run；均线无完整窗口的日子记 -1。
    # 共用手算序列窗口 3：下标 2、3 同段 above，下标 4、5 同段 below，
    # 下标 6 独段 above，下标 7 独段 below，下标 8–11 同段 above。
    assert trend_segment_ids(NAV, 3) == [-1, -1, 0, 0, 1, 1, 2, 3, 4, 4, 4, 4]
    # 同一序列窗口 5：下标 4、5 同段 below，下标 6 独段 above，下标 7
    # 独段 below，下标 8–11 同段 above。
    assert trend_segment_ids(NAV, 5) == [-1, -1, -1, -1, 0, 0, 1, 2, 3, 3, 3, 3]
    # 交替序列：趋势每天翻转，每段恰为一天，段编号即下标 - 2。
    assert trend_segment_ids(NAV_ALT, 3) == [-1, -1] + list(range(10))
    # 全程单调上涨：净值恒在均线之上，只有一段。
    rising = [10.0 + i for i in range(12)]
    assert trend_segment_ids(rising, 3) == [-1, -1] + [0] * 10


def test_segment_hand_computed_triggered():
    # 半衰期 10000 天：<5% 档两段各约一半，主导段占比约 0.500035 >= 0.5，
    # 门槛触发，状态概率 = 加权基准率。
    hv = _hand_values_day7_trigger()
    pred = _pred_day7_trigger()
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.signal == SIGNAL_DRAWDOWN
    assert pred.baseline_prob == pytest.approx(0.5)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is True
    assert pred.dominant_segment_share == pytest.approx(hv["share"])
    assert pred.dominant_segment == 3  # 起点 5 所在的段（权重略大）
    assert pred.decision_segment == 5  # 决策日 7 所在的段
    assert pred.effective_segments == pytest.approx(2.0)
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 4
    assert pred.bucket_train_n == 2
    assert pred.outcome == 1


def test_segment_hand_computed_not_triggered():
    # 半衰期 10000 天：<5% 档三段各约三分之一，主导段占比约 0.333 < 0.5，
    # 门槛不触发，状态概率 = v2 未加门槛值。
    hv = _hand_values_day9()
    pred = weighted_predict_at_v10(
        NAV_ALT, 9, 2, _nontrig_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.baseline_prob == pytest.approx(0.5)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is False
    assert pred.dominant_segment_share == pytest.approx(hv["share"])
    assert pred.dominant_segment == 5  # 起点 7 所在的段（权重最大）
    assert pred.decision_segment == 7  # 决策日 9 所在的段
    assert pred.effective_segments == pytest.approx(3.0)
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 6
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_threshold_boundary():
    # 以触发情形（决策日 7、主导段占比约 0.500035）为基底：
    # 门槛 0.5 时触发（达到即触发）；门槛 0.51 时不触发；门槛恰好等于实
    # 测占比时触发；门槛 0.6 时不触发；默认门槛 0.5 时触发。
    v2 = weighted_predict_at_v2(
        NAV_ALT, 7, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    pred_default = _pred_day7_trigger()
    assert pred_default is not None
    assert pred_default.gated is True
    assert pred_default.state_prob == pytest.approx(
        pred_default.baseline_weighted
    )
    pred_high = _pred_day7_trigger(max_dominant_share=0.51)
    assert pred_high is not None
    assert pred_high.gated is False
    assert pred_high.state_prob == pytest.approx(v2.state_prob)
    pred_exact = _pred_day7_trigger(
        max_dominant_share=_hand_values_day7_trigger()["share"]
    )
    assert pred_exact is not None
    assert pred_exact.gated is True
    assert pred_exact.state_prob == pytest.approx(
        pred_exact.baseline_weighted
    )
    pred_higher = _pred_day7_trigger(max_dominant_share=0.6)
    assert pred_higher is not None
    assert pred_higher.gated is False
    assert pred_higher.state_prob == pytest.approx(v2.state_prob)


def _long_series():
    # 1500 天、横跨 2010–2014 五个日历年（与 v6/v7/v8/v9 测试同一序列）：
    # 默认参数下 A/B 两类触发与未触发两种情形都出现（草稿脚本已核实：
    # A 类 2 天触发、B 类 5 天触发），递推与直算的一致性用它。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(1500)]
    assert min(nav) > 0
    return nav


def _sine_series():
    # 1500 天正弦净值（周期约 157 天，无趋势），振幅在第 750 天切换：
    # 前半段振幅 30（峰谷跌幅约 5.8% < 10%，B 类标签恒为 0），后半段
    # 振幅 120（峰谷跌幅约 21% > 10%，B 类标签恒为 1）。
    return [
        1000.0 + (30.0 if i < 750 else 120.0) * math.sin(i / 25.0)
        for i in range(1500)
    ]


def test_relation_matches_v2():
    # v10 的定义：未触发日状态概率 = v2；触发日 = 加权基准率；其余字段
    # 与 v2 逐点一致（A/B 两类）。长序列（窗口 30）上 A/B 两类触发与未
    # 触发两种情形都出现（草稿脚本核实：A 类 2 天触发、B 类 5 天触发）。
    nav = _long_series()
    for kind in ("A", "B"):
        v10_preds = generate_predictions_v10(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert len(v10_preds) == len(v2_preds)
        assert v10_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p10, p2 in zip(v10_preds, v2_preds):
            assert p10.index == p2.index
            assert p10.bucket == p2.bucket
            assert p10.bucket_weight_n == pytest.approx(p2.bucket_weight_n, abs=1e-12)
            assert p10.gated == (
                p2.bucket_weight_n > 0
                and p10.dominant_segment_share >= REGIME_MAX_DOMINANT_SHARE
            )
            assert 0.0 <= p10.dominant_segment_share <= 1.0
            if p2.bucket_weight_n > 0:
                assert p10.dominant_segment is not None
                assert p10.effective_segments >= 1.0
            assert p10.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            if p10.gated:
                gated_seen += 1
                assert p10.state_prob == pytest.approx(p10.baseline_weighted, abs=1e-12)
            else:
                ungated_seen += 1
                assert p10.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p10.baseline_prob == pytest.approx(p2.baseline_prob, abs=1e-12)
            assert p10.baseline_weighted == pytest.approx(p2.baseline_weighted, abs=1e-12)
            assert p10.outcome == p2.outcome
            assert p10.train_n == p2.train_n
            assert p10.bucket_train_n == p2.bucket_train_n
            assert p10.state_fallback == p2.state_fallback
        assert gated_seen > 0, f"{kind} 应有触发门槛的决策日"
        assert ungated_seen > 0, f"{kind} 应有未触发门槛的决策日"


def test_none_signal_identity():
    # 无信号：该态即全部训练集，触发时状态概率本就等于加权基准率，
    # 所以状态概率恒等于 v2（门槛不改变状态概率，只可能改变 gated 标记）。
    # 正弦序列上 A/B 两类都应与 v2 逐点相同。
    nav = _sine_series()
    for kind in ("A", "B"):
        v10_preds = generate_predictions_v10(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        assert len(v10_preds) == len(v2_preds)
        for p10, p2 in zip(v10_preds, v2_preds):
            assert p10.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p10.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。段归属只用当天的训练
    # 集（t 之前的数据），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    before = {
        t: weighted_predict_at_v10(
            base, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5,
        )
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v10(
            mutated, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5,
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
        assert before[idx].dominant_segment_share == pytest.approx(
            after[idx].dominant_segment_share
        )
        assert before[idx].dominant_segment == after[idx].dominant_segment
        assert before[idx].decision_segment == after[idx].decision_segment
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
        preds = generate_predictions_v10(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v10(
                nav, pred.index, horizon, label_fn, SIGNAL_DRAWDOWN, window=30,
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
            assert direct.dominant_segment_share == pytest.approx(
                pred.dominant_segment_share, abs=1e-9
            )
            assert direct.dominant_segment == pred.dominant_segment
            assert direct.decision_segment == pred.decision_segment
            assert direct.effective_segments == pytest.approx(
                pred.effective_segments, abs=1e-9
            )
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0；净值恒在均线之下，
    # 全程只有一个趋势段，主导段占比恒为 1.0，门槛触发，状态概率 =
    # 加权基准率 = 0（与 v8 不同：v8 的相对差距在此为 0、门槛不触发；
    # 与 v9 相同：v9 的多年一边倒在此同样触发）。
    nav = [1000.0 - i for i in range(200)]
    pred = weighted_predict_at_v10(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5,
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.gated is True
    assert pred.dominant_segment_share == pytest.approx(1.0)
    assert pred.effective_segments == pytest.approx(1.0)
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：趋势段门槛 0.5（与 v6 的年份门槛取同一值、同一“过半”
    # 理由）、趋势窗口即回撤窗口 250 天（不另引新常数）、半衰期 756 天、
    # 收缩伪计数 50（均从 v1 继承、未改）。
    assert REGIME_MAX_DOMINANT_SHARE == 0.5
    assert WINDOW_DAYS == 250
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    assert UNDEFINED_SEGMENT == -1
    nav = _long_series()
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v10([10.0 + 0.01 * i for i in range(30)], "A") == []
    with pytest.raises(ValueError):
        generate_predictions_v10(nav, "A", "nope")
    with pytest.raises(ValueError):
        generate_predictions_v10(nav, "C")
    with pytest.raises(ValueError):
        weighted_predict_at_v10(NAV, 8, 2, label_positive_return, "nope")
