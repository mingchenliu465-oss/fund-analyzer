"""概率预测实验 v1 的测试：加权与收缩的手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；小参数（窗口/期限/半衰期）只用于让手算可行，
默认参数口径由实验报告的真实数据运行覆盖。
"""

import pytest

from experiments.forecast_baseline import (
    BUCKET_GT10,
    BUCKET_LT5,
    generate_predictions,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import (
    HALF_LIFE_DAYS,
    SHRINKAGE_M,
    generate_predictions_v1,
    weighted_predict_at,
)

# 与 test_forecast_baseline 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]


def test_weighted_baseline_and_shrinkage_hand_computed():
    # 手算（窗口 3、期限 2、决策日 8、半衰期 2 天、收缩伪计数 1）：
    # 训练起点 s in [2, 6]，标签 [0, 0, 1, 0, 1]，档位 [<5%, <5%, >10%, >10%, <5%]。
    # 权重 w = 0.5 ** ((8 - s) / 2)：
    #   s=2: 0.125；s=3: 0.5**2.5；s=4: 0.25；s=5: 0.5**1.5；s=6: 0.5。
    # 权重和 = 0.125 + 0.5**2.5 + 0.25 + 0.5**1.5 + 0.5；
    # 加权标签和 = 0.25（s=4）+ 0.5（s=6）= 0.75；
    # 加权基准率 = 0.75 / 权重和。
    # 决策日档位 <5%，同档加权标签和 = 0.5（s=6），加权样本量 =
    #   0.125 + 0.5**2.5 + 0.5；收缩后状态概率 =
    #   (0.5 + 1 × 加权基准率) / (同档加权样本量 + 1)。
    # 无加权基准率（比较基准）= 2/5 = 0.4，与 v0 一致。
    w2 = 0.5 ** 2.5
    w5 = 0.5 ** 1.5
    weight_n = 0.125 + w2 + 0.25 + w5 + 0.5
    baseline_w = 0.75 / weight_n
    bucket_wn = 0.125 + w2 + 0.5
    expected_state = (0.5 + baseline_w) / (bucket_wn + 1.0)
    pred = weighted_predict_at(
        NAV, 8, 2, label_positive_return, window=3, half_life=2.0, shrinkage_m=1.0
    )
    assert pred is not None
    assert pred.bucket == BUCKET_LT5
    assert pred.baseline_prob == pytest.approx(0.4)
    assert pred.baseline_weighted == pytest.approx(baseline_w)
    assert pred.weight_n == pytest.approx(weight_n)
    assert pred.bucket_weight_n == pytest.approx(bucket_wn)
    assert pred.state_prob == pytest.approx(expected_state)
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    # 收缩应把状态概率拉向基准率：无收缩的档位频率为 0.5/同档加权样本量，
    # 收缩后值应落在档位频率与加权基准率之间。
    unshrunk = 0.5 / bucket_wn
    assert min(unshrunk, baseline_w) < pred.state_prob < max(unshrunk, baseline_w)


def test_recency_and_wbaseline_modes_hand_computed():
    # 同一序列：recency 模式（不收缩）状态概率 = 0.5 / 同档加权样本量；
    # wbaseline 模式状态概率 = 加权基准率。
    w2 = 0.5 ** 2.5
    bucket_wn = 0.125 + w2 + 0.5
    weight_n = 0.125 + w2 + 0.25 + 0.5 ** 1.5 + 0.5
    pred_rec = weighted_predict_at(
        NAV, 8, 2, label_positive_return, window=3,
        half_life=2.0, shrinkage_m=1.0, mode="recency",
    )
    assert pred_rec is not None
    assert pred_rec.state_prob == pytest.approx(0.5 / bucket_wn)
    pred_wb = weighted_predict_at(
        NAV, 8, 2, label_positive_return, window=3,
        half_life=2.0, shrinkage_m=1.0, mode="wbaseline",
    )
    assert pred_wb is not None
    assert pred_wb.state_prob == pytest.approx(0.75 / weight_n)
    assert pred_wb.state_prob == pytest.approx(pred_wb.baseline_weighted)
    with pytest.raises(ValueError):
        weighted_predict_at(NAV, 8, 2, label_positive_return, mode="nope")


def test_fallback_when_bucket_unseen_in_training():
    # 训练起点全部 <5% 档且标签全 0，决策日跌至 -20%（>10% 档）：
    # 状态概率回退为加权基准率（此处为 0），回退标志为真。
    nav = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 8.0, 9.0, 9.5]
    pred = weighted_predict_at(nav, 6, 2, label_positive_return, window=3)
    assert pred is not None
    assert pred.bucket == BUCKET_GT10
    assert pred.bucket_train_n == 0
    assert pred.bucket_weight_n == pytest.approx(0.0)
    assert pred.state_fallback is True
    assert pred.state_prob == pytest.approx(pred.baseline_weighted)


def test_recency_weights_recent_labels_more():
    # 前 30 天稳涨（A 类标签全 1），后 30 天稳跌（标签全 0）；决策日 50。
    # 训练起点 45 个中前 25 个标签为 1、后 20 个为 0：无加权基准率 25/45，
    # 时效加权基准率必须更低（近期的 0 权重更大）。
    nav = [10.0 + i for i in range(30)] + [40.0 - (i - 30) for i in range(30, 60)]
    pred = weighted_predict_at(nav, 50, 2, label_positive_return, window=5)
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(25 / 45)
    assert pred.baseline_weighted < pred.baseline_prob
    assert 0.0 < pred.baseline_weighted < pred.baseline_prob


def test_no_future_leakage():
    # 与 v0 测试同构：前 40 天平稳微涨，后 20 天人为暴跌；改动决策日
    # 之后的净值，决策日之前（含决策日）的预测必须逐点不变。
    base = [10.0 + 0.01 * i for i in range(60)]
    mutated = base[:40] + [5.0] * 20
    before = {
        t: weighted_predict_at(base, t, 2, label_positive_return, window=5)
        for t in range(20, 40)
    }
    after = {
        t: weighted_predict_at(mutated, t, 2, label_positive_return, window=5)
        for t in range(20, 40)
    }
    assert all(v is not None for v in before.values())
    for idx in before:
        assert before[idx].baseline_prob == pytest.approx(after[idx].baseline_prob)
        assert before[idx].state_prob == pytest.approx(after[idx].state_prob)
        assert before[idx].baseline_weighted == pytest.approx(
            after[idx].baseline_weighted
        )
    for idx in range(20, 38):
        assert before[idx].outcome == after[idx].outcome
    assert before[38].outcome != after[38].outcome


def test_generate_matches_direct():
    # 递推实现与逐项直算在全部决策日逐点一致（两种模式、两种类别）。
    # B 类期限 252 天：序列须足够长（首个有训练样本的决策日约在 281），
    # 取 700 天使 A/B 两类都有充足预测。
    nav = [10.0 + 0.3 * ((i * 7) % 13) - 0.02 * i for i in range(700)]
    for kind in ("A", "B"):
        for mode in ("v1", "recency", "wbaseline"):
            preds = generate_predictions_v1(
                nav, kind, mode=mode, window=30, test_start=250
            )
            assert preds, f"{kind}/{mode} 应有预测"
            horizon = 126 if kind == "A" else 252
            label_fn = (
                label_positive_return if kind == "A" else label_drawdown_breach
            )
            for pred in preds:
                direct = weighted_predict_at(
                    nav, pred.index, horizon, label_fn, window=30, mode=mode,
                )
                assert direct is not None
                assert direct.state_prob == pytest.approx(pred.state_prob, abs=1e-9)
                assert direct.baseline_prob == pytest.approx(pred.baseline_prob)
                assert direct.baseline_weighted == pytest.approx(
                    pred.baseline_weighted, abs=1e-9
                )
                assert direct.bucket == pred.bucket
                assert direct.outcome == pred.outcome


def test_limit_case_matches_v0():
    # 半衰期极大（权重≈1）且收缩为 0 时，v1 应退化回 v0：单调递增序列
    # A 类 14 个预测，状态概率与 v0 逐点一致（容差 1e-6）。
    long_nav = [10.0 + 0.01 * i for i in range(1400)]
    v1_preds = generate_predictions_v1(
        long_nav, "A", half_life=1e12, shrinkage_m=0.0
    )
    v0_preds = generate_predictions(long_nav, "A")
    assert len(v1_preds) == len(v0_preds) == 14
    for p1, p0 in zip(v1_preds, v0_preds):
        assert p1.index == p0.index
        assert p1.state_prob == pytest.approx(p0.state_prob, abs=1e-6)
        assert p1.baseline_weighted == pytest.approx(p0.baseline_prob, abs=1e-6)


def test_degenerate_all_zero_labels():
    # 单调递减序列：全部 A 类标签为 0，加权基准率与状态概率均为 0。
    nav = [100.0 - i for i in range(60)]
    pred = weighted_predict_at(nav, 30, 2, label_positive_return, window=5)
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_disclosed_and_defaults():
    # 常数写死在模块中：半衰期 756 天（约 3 交易年）、收缩伪计数 50。
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    # 默认参数下短序列无完整标签 -> 空集；非法类别抛错。
    assert generate_predictions_v1([10.0 + 0.01 * i for i in range(30)], "A") == []
    with pytest.raises(ValueError):
        generate_predictions_v1([10.0] * 30, "C")
