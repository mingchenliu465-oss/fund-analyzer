"""概率预测实验 v2 的测试：信号定义、手算、放未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；小参数（窗口/期限/半衰期）只用于让手算可行，
默认参数口径由实验报告的真实数据运行覆盖。
"""

import pytest

from experiments.forecast_baseline import (
    BUCKET_LT5,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import (
    HALF_LIFE_DAYS,
    SHRINKAGE_M,
    generate_predictions_v1,
)
from experiments.forecast_v2 import (
    MOMENTUM_LOOKBACK_DAYS,
    SIGNAL_DRAWDOWN,
    SIGNAL_MOMENTUM,
    SIGNAL_NONE,
    SIGNAL_TREND,
    generate_predictions_v2,
    signal_state,
    weighted_predict_at_v2,
)

# 与 test_forecast_baseline / test_forecast_v1 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]


def test_trend_state_assignment():
    # 窗口 3：决策日 4 均值 (10+12+9)/3=10.33，净值 9 在均线下；
    # 决策日 8 均值 (10+11+10)/3=10.33，净值 12 在均线上。
    assert signal_state(NAV, 4, SIGNAL_TREND, window=3) == "below"
    assert signal_state(NAV, 8, SIGNAL_TREND, window=3) == "above"
    # 恰好等于均线归入 above（含边界）；窗口不足返回 None。
    assert signal_state([10.0, 10.0, 10.0], 2, SIGNAL_TREND, window=3) == "above"
    assert signal_state([10.0, 10.0], 1, SIGNAL_TREND, window=3) is None
    with pytest.raises(ValueError):
        signal_state(NAV, 8, "nope")


def test_momentum_state_assignment():
    # 回看 126 日：高于 126 天前为 up，不高于为 down（含相等）。
    rising = [10.0] * 130 + [11.0] * 10
    assert signal_state(rising, 139, SIGNAL_MOMENTUM) == "up"
    falling = [10.0] * 130 + [9.0] * 10
    assert signal_state(falling, 139, SIGNAL_MOMENTUM) == "down"
    flat = [10.0] * 140
    assert signal_state(flat, 139, SIGNAL_MOMENTUM) == "down"
    assert MOMENTUM_LOOKBACK_DAYS == 126
    assert signal_state([10.0] * 125, 124, SIGNAL_MOMENTUM) is None
    assert signal_state([10.0] * 130, 129, SIGNAL_MOMENTUM) == "down"


def test_trend_hand_computed():
    # 手算（窗口 3、期限 2、决策日 8、半衰期 2 天、收缩伪计数 1）：
    # 训练起点 s in [2, 6]，标签 [0, 0, 1, 0, 1]，趋势态
    # [above, above, below, below, above]（见 test_trend_state_assignment）。
    # 权重 w = 0.5 ** ((8 - s) / 2)：
    #   s=2: 0.125；s=3: 0.5**2.5；s=4: 0.25；s=5: 0.5**1.5；s=6: 0.5。
    # 权重和 = 0.125 + 0.5**2.5 + 0.25 + 0.5**1.5 + 0.5；
    # 加权标签和 = 0.25（s=4）+ 0.5（s=6）= 0.75；
    # 加权基准率 = 0.75 / 权重和。
    # 决策日态 above，同态加权标签和 = 0.5（s=6），加权样本量 =
    #   0.125 + 0.5**2.5 + 0.5；收缩后状态概率 =
    #   (0.5 + 1 × 加权基准率) / (同态加权样本量 + 1)。
    # 无加权基准率（比较基准）= 2/5 = 0.4，与 v0 一致。
    w2 = 0.5 ** 2.5
    w5 = 0.5 ** 1.5
    weight_n = 0.125 + w2 + 0.25 + w5 + 0.5
    baseline_w = 0.75 / weight_n
    state_wn = 0.125 + w2 + 0.5
    expected_state = (0.5 + baseline_w) / (state_wn + 1.0)
    pred = weighted_predict_at_v2(
        NAV, 8, 2, label_positive_return, SIGNAL_TREND,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == "above"
    assert pred.signal == SIGNAL_TREND
    assert pred.baseline_prob == pytest.approx(0.4)
    assert pred.baseline_weighted == pytest.approx(baseline_w)
    assert pred.weight_n == pytest.approx(weight_n)
    assert pred.bucket_weight_n == pytest.approx(state_wn)
    assert pred.state_prob == pytest.approx(expected_state)
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3


def test_none_signal_is_weighted_baseline():
    # 无信号：状态概率恒等于加权基准率，不分态、不收缩、不回退。
    pred = weighted_predict_at_v2(
        NAV, 8, 2, label_positive_return, SIGNAL_NONE,
        window=3, half_life=2.0, shrinkage_m=1.0,
    )
    assert pred is not None
    assert pred.bucket == "all"
    assert pred.state_prob == pytest.approx(pred.baseline_weighted)
    assert pred.state_fallback is False
    assert pred.bucket_train_n == pred.train_n == 5


def test_fallback_when_state_unseen_in_training():
    # 窗口 3、期限 2、决策日 6：训练起点 s in [2, 4] 趋势态全为 below，
    # 决策日净值跳升至 20、趋势态 above 从未在训练中出现：
    # 状态概率回退为加权基准率，回退标志为真。
    nav = [12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 20.0, 21.0, 22.0]
    pred = weighted_predict_at_v2(
        nav, 6, 2, label_positive_return, SIGNAL_TREND, window=3
    )
    assert pred is not None
    assert pred.bucket == "above"
    assert pred.bucket_train_n == 0
    assert pred.bucket_weight_n == pytest.approx(0.0)
    assert pred.state_fallback is True
    assert pred.state_prob == pytest.approx(pred.baseline_weighted)


def test_no_future_leakage_all_signals():
    # 四种信号同构：前 160 天平稳微涨，后 40 天人为暴跌；改动决策日
    # 之后的净值，决策日之前（含决策日）的预测必须逐点不变。
    # 决策日取 130..159（动量信号需 index >= 126），期限 2、窗口 5。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    for signal in (SIGNAL_DRAWDOWN, SIGNAL_TREND, SIGNAL_MOMENTUM, SIGNAL_NONE):
        before = {
            t: weighted_predict_at_v2(base, t, 2, label_positive_return, signal, window=5)
            for t in range(130, 160)
        }
        after = {
            t: weighted_predict_at_v2(mutated, t, 2, label_positive_return, signal, window=5)
            for t in range(130, 160)
        }
        assert all(v is not None for v in before.values()), signal
        for idx in before:
            assert before[idx].baseline_prob == pytest.approx(after[idx].baseline_prob)
            assert before[idx].state_prob == pytest.approx(after[idx].state_prob)
            assert before[idx].baseline_weighted == pytest.approx(
                after[idx].baseline_weighted
            )
            assert before[idx].bucket == after[idx].bucket
        for idx in range(130, 158):
            assert before[idx].outcome == after[idx].outcome
        assert before[158].outcome != after[158].outcome


def test_generate_matches_direct():
    # 递推实现与逐项直算在决策日上逐点一致（四种信号、两种类别）。
    # B 类期限 252 天：序列须足够长（首个有训练样本的决策日约在 281），
    # 取 700 天使 A/B 两类都有充足预测；B 类只抽查部分决策日以控运行时长。
    nav = [10.0 + 0.3 * ((i * 7) % 13) - 0.02 * i for i in range(700)]
    for signal in (SIGNAL_DRAWDOWN, SIGNAL_TREND, SIGNAL_MOMENTUM, SIGNAL_NONE):
        for kind in ("A", "B"):
            preds = generate_predictions_v2(
                nav, kind, signal, window=30, test_start=250
            )
            assert preds, f"{kind}/{signal} 应有预测"
            horizon = 126 if kind == "A" else 252
            label_fn = (
                label_positive_return if kind == "A" else label_drawdown_breach
            )
            checked = preds if kind == "A" else preds[::25]
            for pred in checked:
                direct = weighted_predict_at_v2(
                    nav, pred.index, horizon, label_fn, signal, window=30,
                )
                assert direct is not None
                assert direct.state_prob == pytest.approx(pred.state_prob, abs=1e-9)
                assert direct.baseline_prob == pytest.approx(pred.baseline_prob)
                assert direct.baseline_weighted == pytest.approx(
                    pred.baseline_weighted, abs=1e-9
                )
                assert direct.bucket == pred.bucket
                assert direct.outcome == pred.outcome


def test_drawdown_reproduces_v1():
    # v2 用回撤档位信号必须逐点复现 v1（同一序列、同一参数、A/B 两类）。
    nav = [10.0 + 0.3 * ((i * 7) % 13) - 0.02 * i for i in range(700)]
    for kind in ("A", "B"):
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        v1_preds = generate_predictions_v1(
            nav, kind, window=30, test_start=250
        )
        assert len(v2_preds) == len(v1_preds)
        for p2, p1 in zip(v2_preds, v1_preds):
            assert p2.index == p1.index
            assert p2.bucket == p1.bucket
            assert p2.state_prob == pytest.approx(p1.state_prob, abs=1e-12)
            assert p2.baseline_prob == pytest.approx(p1.baseline_prob, abs=1e-12)
            assert p2.baseline_weighted == pytest.approx(
                p1.baseline_weighted, abs=1e-12
            )
            assert p2.outcome == p1.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0，三种有信号态与无信号的状态概率均为 0。
    nav = [1000.0 - i for i in range(200)]
    for signal in (SIGNAL_DRAWDOWN, SIGNAL_TREND, SIGNAL_MOMENTUM, SIGNAL_NONE):
        pred = weighted_predict_at_v2(
            nav, 150, 2, label_positive_return, signal, window=5
        )
        assert pred is not None, signal
        assert pred.baseline_prob == pytest.approx(0.0)
        assert pred.baseline_weighted == pytest.approx(0.0)
        assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数从 v1 继承、写死：半衰期 756 天（约 3 交易年）、收缩伪计数 50。
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v2([10.0 + 0.01 * i for i in range(30)], "A", SIGNAL_TREND) == []
    with pytest.raises(ValueError):
        generate_predictions_v2([10.0] * 30, "A", "nope")
    with pytest.raises(ValueError):
        generate_predictions_v2([10.0] * 30, "C", SIGNAL_NONE)
    with pytest.raises(ValueError):
        weighted_predict_at_v2(NAV, 8, 2, label_positive_return, "nope")
    # 回撤档位信号与 v0 的 bucket 常量一致。
    pred = weighted_predict_at_v2(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN, window=3
    )
    assert pred is not None
    assert pred.bucket == BUCKET_LT5
