"""概率预测实验 v12 的测试：合取门槛、单门槛不回退、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v12 与 v2/v10/v11 的关系测试以三者的公开输
出为参照（v12 的定义本身就是“对 v2 输出做 v10 ∧ v11 合取门槛判断”）；
小参数（窗口/期限/半衰期/每段最少加权样本量）只用于让手算可行，默认
参数口径由实验报告的真实数据运行覆盖。v12 不需要日期输入——趋势段
由净值自身的均线状态决定。
"""

import math

import pytest

from experiments.forecast_baseline import (
    WINDOW_DAYS,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M
from experiments.forecast_v10 import REGIME_MAX_DOMINANT_SHARE
from experiments.forecast_v11 import CONSISTENCY_MAX_RANGE, MIN_SEGMENT_WEIGHT_N
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNAL_NONE,
    generate_predictions_v2,
    weighted_predict_at_v2,
)
from experiments.forecast_v4 import GATE_MIN_WEIGHT_N
from experiments.forecast_v10 import generate_predictions_v10
from experiments.forecast_v11 import generate_predictions_v11
from experiments.forecast_v12 import (
    generate_predictions_v12,
    weighted_predict_at_v12,
)

# 与 test_forecast_baseline / test_forecast_v1 / ... / test_forecast_v11
# 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]

# 交替净值序列（窗口 3 时趋势每天翻转，每段恰为一天）：
# 下标 2 起趋势为 below/above 交替，段编号即下标 - 2；
# 回撤档位同样交替：偶数下标 >10%、奇数下标 <5%。
NAV_ALT = [10.0, 12.0] * 6

# 决策日 7 的双触发情形（窗口 3、期限 2、半衰期 10000 天、收缩伪计数 1、
# 每段最少加权样本量 0.5）：训练起点 s in [2, 5]，自定义标签
# [0, 1, 1, 0]，回撤档位 [>10%, <5%, >10%, <5%]；决策日 7 属 <5% 档，
# 标签为 1。<5% 档训练起点 3、5 分属两段（段 1、段 3）：v10 主导段占比
# w5/(w3+w5) 约 0.500035 >= 0.5 触发；v11 段内正标签占比分别为 1.0 与
# 0.0，极差 1.0 >= 0.5 触发；合取触发，状态概率 = 加权基准率。
_TRIGGER_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 7: 1}


def _trigger_label_fn(nav, start, horizon):
    """双触发情形的测试用标签函数。"""
    return _TRIGGER_LABELS.get(start)


def _hand_values_day7_trigger(half_life: float = 10000.0):
    """决策日 7 双触发情形的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((7 - s) / half_life) for s in (2, 3, 4, 5)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4]) / weight_n
    bucket_wn = w[3] + w[5]
    bucket_ws = w[3]
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    share = w[5] / bucket_wn
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
    """双触发情形的默认参数调用（每段最少加权样本量 0.5，使单标签段有证据）。"""
    params = dict(window=3, half_life=10000.0, shrinkage_m=1.0,
                  min_segment_weight_n=0.5)
    params.update(kwargs)
    return weighted_predict_at_v12(
        NAV_ALT, 7, 2, _trigger_label_fn, SIGNAL_DRAWDOWN, **params
    )


# 决策日 7 的仅 v10 触发情形（同一组数，只改标签）：训练起点标签
# [0, 1, 1, 1]，<5% 档两段的正标签占比全为 1.0，v11 极差 0.0 不触发；
# v10 主导段占比仍约 0.500035，触发。合取不触发，状态概率 = v2 值。
_V10_ONLY_LABELS = {2: 0, 3: 1, 4: 1, 5: 1, 7: 1}


def _v10_only_label_fn(nav, start, horizon):
    """仅 v10 触发情形的测试用标签函数。"""
    return _V10_ONLY_LABELS.get(start)


def _hand_values_day7_v10_only(half_life: float = 10000.0):
    """决策日 7 仅 v10 触发情形的手算量（只用 ``0.5 ** x``）。"""
    w = {s: 0.5 ** ((7 - s) / half_life) for s in (2, 3, 4, 5)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4] + w[5]) / weight_n
    bucket_wn = w[3] + w[5]
    bucket_ws = w[3] + w[5]
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    share = w[5] / bucket_wn
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "ungated": ungated,
        "share": share,
    }


# 决策日 9 的仅 v11 触发情形（窗口 3、期限 2、半衰期 10000 天、收缩伪
# 计数 1、每段最少加权样本量 0.5）：训练起点 s in [2, 7]，自定义标签
# [0, 1, 1, 0, 0, 1]，回撤档位 [>10%, <5%, >10%, <5%, >10%, <5%]；
# 决策日 9 属 <5% 档，标签为 1。<5% 档训练起点 3、5、7 分属三段（段 1、
# 段 3、段 5），段内正标签占比分别为 1.0、0.0、1.0，极差 1.0 >= 0.5，
# v11 触发；v10 主导段占比 w7/(w3+w5+w7) 约 0.333 < 0.5，不触发。合
# 取不触发，状态概率 = v2 值。
_V11_ONLY_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 6: 0, 7: 1, 9: 1}


def _v11_only_label_fn(nav, start, horizon):
    """仅 v11 触发情形的测试用标签函数。"""
    return _V11_ONLY_LABELS.get(start)


def _hand_values_day9_v11_only(half_life: float = 10000.0):
    """决策日 9 仅 v11 触发情形的手算量（只用 ``0.5 ** x``）。"""
    w = {s: 0.5 ** ((9 - s) / half_life) for s in (2, 3, 4, 5, 6, 7)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4] + w[7]) / weight_n
    bucket_wn = w[3] + w[5] + w[7]
    bucket_ws = w[3] + w[7]
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    share = w[7] / bucket_wn
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "ungated": ungated,
        "share": share,
    }


def test_both_gates_trigger_hand_computed():
    # 半衰期 10000 天：v10 主导段占比约 0.500035 触发、v11 极差 1.0 触发，
    # 合取触发，状态概率 = 加权基准率。
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
    assert pred.gated_v10 is True
    assert pred.gated_v11 is True
    assert pred.dominant_segment_share == pytest.approx(hv["share"])
    assert pred.dominant_segment == 3  # 权重最大的段（起点 5 所在段）
    assert pred.effective_segments == pytest.approx(2.0, abs=1e-6)
    assert pred.consistency_range == pytest.approx(1.0)
    assert pred.segment_shares == {1: pytest.approx(1.0), 3: pytest.approx(0.0)}
    assert pred.n_evidence_segments == 2
    assert pred.decision_segment == 5  # 决策日 7 所在的段
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 4
    assert pred.bucket_train_n == 2
    assert pred.outcome == 1


def test_only_v10_triggers_no_fallback():
    # 同一组数、只改标签：v10 触发、v11 不触发，合取不触发，状态概率 = v2 值。
    hv = _hand_values_day7_v10_only()
    pred = weighted_predict_at_v12(
        NAV_ALT, 7, 2, _v10_only_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0, min_segment_weight_n=0.5,
    )
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.baseline_prob == pytest.approx(0.75)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is False
    assert pred.gated_v10 is True
    assert pred.gated_v11 is False
    assert pred.dominant_segment_share == pytest.approx(hv["share"])
    assert pred.dominant_segment == 3
    assert pred.consistency_range == pytest.approx(0.0)
    assert pred.segment_shares == {1: pytest.approx(1.0), 3: pytest.approx(1.0)}
    assert pred.n_evidence_segments == 2
    assert pred.decision_segment == 5
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 4
    assert pred.bucket_train_n == 2
    assert pred.outcome == 1


def test_only_v11_triggers_no_fallback():
    # 决策日 9：v11 触发、v10 不触发，合取不触发，状态概率 = v2 值。
    hv = _hand_values_day9_v11_only()
    pred = weighted_predict_at_v12(
        NAV_ALT, 9, 2, _v11_only_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0, min_segment_weight_n=0.5,
    )
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.baseline_prob == pytest.approx(0.5)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is False
    assert pred.gated_v10 is False
    assert pred.gated_v11 is True
    assert pred.dominant_segment_share == pytest.approx(hv["share"])
    assert pred.dominant_segment == 5  # 权重最大的段（起点 7 所在段）
    assert pred.consistency_range == pytest.approx(1.0)
    assert pred.segment_shares == {
        1: pytest.approx(1.0), 3: pytest.approx(0.0), 5: pytest.approx(1.0),
    }
    assert pred.n_evidence_segments == 3
    assert pred.decision_segment == 7  # 决策日 9 所在的段
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 6
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_threshold_boundaries():
    # 以双触发情形（决策日 7）为基底：任一门槛放宽到实测值之上，合取即
    # 不触发；两个门槛都恰等于实测值时触发（“达到即触发”）。
    hv = _hand_values_day7_trigger()
    v2 = weighted_predict_at_v2(
        NAV_ALT, 7, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    pred_default = _pred_day7_trigger()
    assert pred_default is not None
    assert pred_default.gated is True
    assert pred_default.state_prob == pytest.approx(pred_default.baseline_weighted)
    pred_share_above = _pred_day7_trigger(max_dominant_share=0.51)
    assert pred_share_above is not None
    assert pred_share_above.gated is False
    assert pred_share_above.gated_v10 is False
    assert pred_share_above.gated_v11 is True
    assert pred_share_above.state_prob == pytest.approx(v2.state_prob)
    pred_range_above = _pred_day7_trigger(max_range=1.0001)
    assert pred_range_above is not None
    assert pred_range_above.gated is False
    assert pred_range_above.gated_v10 is True
    assert pred_range_above.gated_v11 is False
    assert pred_range_above.state_prob == pytest.approx(v2.state_prob)
    pred_both_exact = _pred_day7_trigger(
        max_dominant_share=hv["share"], max_range=1.0
    )
    assert pred_both_exact is not None
    assert pred_both_exact.gated is True
    assert pred_both_exact.state_prob == pytest.approx(
        pred_both_exact.baseline_weighted
    )


def _sine_series():
    # 1500 天正弦净值（周期约 157 天，无趋势），振幅在第 750 天切换：
    # 前半段振幅 30（峰谷跌幅约 5.8% < 10%，B 类标签恒为 0），后半段
    # 振幅 120（峰谷跌幅约 21% > 10%，B 类标签恒为 1）。同一回撤档位
    # 的训练标签分属前后两段、段内占比一边倒（草稿脚本核实：A 类 v10
    # 触发 182 天、v11 触发 840 天、交集 20 天；B 类 v10 触发 270 天、
    # v11 触发 261 天、交集 0 天）。
    return [
        1000.0 + (30.0 if i < 750 else 120.0) * math.sin(i / 25.0)
        for i in range(1500)
    ]


def test_relation_matches_v2_v10_v11():
    # v12 的定义：双门槛同时触发时状态概率 = 加权基准率，否则 = v2；
    # gated_v10 / gated_v11 与 v10/v11 各自的 gated 标记逐点一致。
    nav = _sine_series()
    for kind in ("A", "B"):
        p12_preds = generate_predictions_v12(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        p10_preds = generate_predictions_v10(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        p11_preds = generate_predictions_v11(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        p2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert len(p12_preds) == len(p10_preds) == len(p11_preds) == len(p2_preds)
        assert p12_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p12, p10, p11, p2 in zip(p12_preds, p10_preds, p11_preds, p2_preds):
            assert p12.index == p10.index == p11.index == p2.index
            assert p12.bucket == p2.bucket
            assert p12.gated_v10 == p10.gated
            assert p12.gated_v11 == p11.gated
            assert p12.gated == (p10.gated and p11.gated)
            assert p12.dominant_segment_share == pytest.approx(
                p10.dominant_segment_share, abs=1e-12
            )
            assert p12.dominant_segment == p10.dominant_segment
            assert p12.effective_segments == pytest.approx(
                p10.effective_segments, abs=1e-12
            )
            assert p12.consistency_range == pytest.approx(
                p11.consistency_range, abs=1e-12
            )
            assert p12.segment_shares.keys() == p11.segment_shares.keys()
            assert p12.n_evidence_segments == p11.n_evidence_segments
            assert p12.decision_segment == p10.decision_segment
            assert p12.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p12.baseline_weighted == pytest.approx(p2.baseline_weighted, abs=1e-12)
            assert p12.outcome == p2.outcome
            if p12.gated:
                gated_seen += 1
                assert p12.state_prob == pytest.approx(p12.baseline_weighted, abs=1e-12)
            else:
                ungated_seen += 1
                assert p12.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
        if kind == "A":
            assert gated_seen == 20, "A 类交集应为 20 天（草稿脚本核实）"
            assert ungated_seen > 0
        else:
            # B 类：两门槛各自触发数百天、交集 0 天——合取门槛在该序列上
            # 是空门槛，v12 与 v2 逐点相同（草稿脚本核实）。
            assert gated_seen == 0, "B 类交集应为 0 天（草稿脚本核实）"
            assert ungated_seen > 0


def test_none_signal_identity():
    # 无信号：该态即全部训练集，触发时状态概率本就等于加权基准率，
    # 所以状态概率恒等于 v2（门槛不改变状态概率，只可能改变 gated 标记）。
    # 正弦切换序列上 A/B 两类都应与 v2 逐点相同。
    nav = _sine_series()
    for kind in ("A", "B"):
        p12_preds = generate_predictions_v12(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        p2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        assert len(p12_preds) == len(p2_preds)
        for p12, p2 in zip(p12_preds, p2_preds):
            assert p12.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p12.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。两个门槛的量只用当天
    # 的训练集（t 之前的数据），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    before = {
        t: weighted_predict_at_v12(
            base, t, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5,
        )
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v12(
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
        assert before[idx].gated_v10 == after[idx].gated_v10
        assert before[idx].gated_v11 == after[idx].gated_v11
        assert before[idx].dominant_segment_share == pytest.approx(
            after[idx].dominant_segment_share
        )
        assert before[idx].consistency_range == pytest.approx(
            after[idx].consistency_range
        )
        assert before[idx].segment_shares == after[idx].segment_shares
        assert before[idx].n_evidence_segments == after[idx].n_evidence_segments
        assert before[idx].dominant_segment == after[idx].dominant_segment
        assert before[idx].decision_segment == after[idx].decision_segment
        assert before[idx].bucket == after[idx].bucket
    for idx in range(130, 158):
        assert before[idx].outcome == after[idx].outcome
    assert before[158].outcome != after[158].outcome


def _long_series():
    # 1500 天、横跨 2010–2014 五个日历年（与 v6/v7/v8/v9/v10/v11 测试同一序列）：
    # 趋势段短、每段加权质量不足 30，v11 在默认参数下不触发；v12 的
    # 合取门槛同样不触发（草稿脚本核实：A/B 两类均为 0 天），递推与直
    # 算的一致性用它。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(1500)]
    assert min(nav) > 0
    return nav


def test_generate_matches_direct():
    # 递推实现与逐项直算在决策日上逐点一致（A/B 两类）。
    # B 类期限 252 天：序列须足够长，取 700 天使 A/B 两类都有充足预测；
    # B 类只抽查部分决策日以控运行时长。
    nav = _long_series()
    for kind in ("A", "B"):
        preds = generate_predictions_v12(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v12(
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
            assert direct.gated_v10 == pred.gated_v10
            assert direct.gated_v11 == pred.gated_v11
            assert direct.dominant_segment_share == pytest.approx(
                pred.dominant_segment_share, abs=1e-9
            )
            assert direct.consistency_range == pytest.approx(
                pred.consistency_range, abs=1e-9
            )
            assert direct.segment_shares.keys() == pred.segment_shares.keys()
            for seg in pred.segment_shares:
                assert direct.segment_shares[seg] == pytest.approx(
                    pred.segment_shares[seg], abs=1e-9
                )
            assert direct.n_evidence_segments == pred.n_evidence_segments
            assert direct.dominant_segment == pred.dominant_segment
            assert direct.decision_segment == pred.decision_segment
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0；净值恒在均线之下，
    # 全程只有一个趋势段：v10 主导段占比为 1.0、触发，v11 各段正标签占
    # 比都为 0.0、极差 0.0、不触发；合取不触发，v12 等于 v2（与 v10 不
    # 同、与 v11 相同）——单门槛会回退的日子，合取不回退的直接证据。
    nav = [1000.0 - i for i in range(200)]
    pred = weighted_predict_at_v12(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5,
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.gated is False
    assert pred.gated_v10 is True
    assert pred.gated_v11 is False
    assert pred.dominant_segment_share == pytest.approx(1.0)
    assert pred.consistency_range == pytest.approx(0.0)
    assert pred.segment_shares == {0: pytest.approx(0.0)}
    assert pred.n_evidence_segments == 1
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：v10 趋势段集中度门槛 0.5、v11 多段一致性极差门槛 0.5
    # （概率尺度的一半，与 v8 的相对极性门槛取同一值、同一理由）、每段
    # 最少加权样本量 30.0（借用 v4 样本量门槛的已有证据标准）、趋势窗
    # 口即回撤窗口 250 天（不另引新常数）、半衰期 756 天、收缩伪计数
    # 50（均从 v1 继承、未改）。
    assert REGIME_MAX_DOMINANT_SHARE == 0.5
    assert CONSISTENCY_MAX_RANGE == 0.5
    assert MIN_SEGMENT_WEIGHT_N == 30.0
    assert GATE_MIN_WEIGHT_N == 30.0
    assert WINDOW_DAYS == 250
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    nav = _long_series()
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v12([10.0 + 0.01 * i for i in range(30)], "A") == []
    with pytest.raises(ValueError):
        generate_predictions_v12(nav, "A", "nope")
    with pytest.raises(ValueError):
        generate_predictions_v12(nav, "C")
    with pytest.raises(ValueError):
        weighted_predict_at_v12(NAV, 8, 2, label_positive_return, "nope")
