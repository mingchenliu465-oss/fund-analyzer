"""概率基线实验 v0 的测试：已知答案、防未来函数、回退分支、Brier 计算。

期望值全部在测试内手算（或用与模块无关的直接表达式），不调用
模块内部函数反推；小参数（窗口/期限）只用于让手算可行，默认参数
口径由实验报告的真实数据运行覆盖。
"""

import pytest

from experiments.forecast_baseline import (
    BUCKET_5_10,
    BUCKET_GT10,
    BUCKET_LT5,
    brier_score,
    bucket_for_drawdown,
    drawdown_at,
    generate_predictions,
    label_drawdown_breach,
    label_positive_return,
    non_overlapping_count,
    predict_at,
)


def test_drawdown_and_buckets_hand_computed():
    # 窗口 3：[100, 100, 90] 高点 100，回撤 -10% -> 5%-10% 档（含 10%）
    assert drawdown_at([100.0, 100.0, 90.0], 2, window=3) == pytest.approx(-0.10)
    assert bucket_for_drawdown(-0.10) == BUCKET_5_10
    # [100, 100, 89] 回撤 -11% -> >10% 档
    assert bucket_for_drawdown(drawdown_at([100.0, 100.0, 89.0], 2, window=3)) == BUCKET_GT10
    # [100, 101, 100] 回撤约 -0.99% -> <5% 档
    assert bucket_for_drawdown(drawdown_at([100.0, 101.0, 100.0], 2, window=3)) == BUCKET_LT5
    assert bucket_for_drawdown(-0.049) == BUCKET_LT5
    assert bucket_for_drawdown(-0.05) == BUCKET_5_10
    assert bucket_for_drawdown(0.0) == BUCKET_LT5


def test_labels_hand_computed():
    # A 类：期限 2，起点 0：1.0 -> 0.9 为负 -> 0；起点 1：1.1 -> 1.2 为正 -> 1
    nav = [1.0, 1.1, 0.9, 1.2]
    assert label_positive_return(nav, 0, horizon=2) == 0
    assert label_positive_return(nav, 1, horizon=2) == 1
    assert label_positive_return(nav, 2, horizon=2) is None  # 未来不足
    # B 类：起点 0 窗口 [10, 9, 8.5]：滚动高点 10，最低回撤 -15% -> 1
    assert label_drawdown_breach([10.0, 9.0, 8.5, 9.5, 11.0], 0, horizon=2) == 1
    # [10, 9.5, 10.5]：最低回撤 -5% -> 0
    assert label_drawdown_breach([10.0, 9.5, 10.5, 11.0], 0, horizon=2) == 0
    # 期限 2 需用到下标 2：长度仅 2 的序列未来不足 -> None
    assert label_drawdown_breach([10.0, 9.5], 0, horizon=2) is None


def test_predict_at_known_answer_a():
    # 手算（窗口 3、期限 2、决策日 8）：
    # 净值：0:10 1:10 2:10 3:12 4:9 5:10 6:11 7:10 8:12 9:11 10:13
    # 训练起点 s in [2, 6]（s>=2 且 s<=8-2）：
    #   s=2: 标签 nav4=9 vs 10 -> 0，档位 [10,10,10] 回撤 0 -> <5%
    #   s=3: 标签 nav5=10 vs 12 -> 0，档位 [10,10,12] 回撤 0 -> <5%
    #   s=4: 标签 nav6=11 vs 9 -> 1，档位 [10,12,9] 回撤 -25% -> >10%
    #   s=5: 标签 nav7=10 vs 10 -> 0（不大于），档位 [12,9,10] 回撤约 -16.7% -> >10%
    #   s=6: 标签 nav8=12 vs 11 -> 1，档位 [9,10,11] 回撤 0 -> <5%
    # 基准率 = 2/5 = 0.4；决策日档位 [11,10,12] 回撤 0 -> <5%，
    # 同档训练 {2,3,6} 标签 [0,0,1] -> 1/3；决策日结果 nav10=13 > 12 -> 1。
    nav = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0]
    pred = predict_at(nav, 8, 2, label_positive_return, window=3)
    assert pred is not None
    assert pred.bucket == BUCKET_LT5
    assert pred.baseline_prob == pytest.approx(0.4)
    assert pred.state_prob == pytest.approx(1 / 3)
    assert pred.outcome == 1
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.state_fallback is False


def test_predict_at_known_answer_b():
    # 同一序列，B 类期限 3、决策日 8：
    # 训练起点 s in [2, 5]（s<=8-3）：
    #   s=2: 窗口 [10,12,9,10] 最低回撤 -25% -> 1，档位 <5%
    #   s=3: 窗口 [12,9,10,11] 最低回撤 -25% -> 1，档位 <5%
    #   s=4: 窗口 [9,10,11,10] 最低回撤 0 -> 0，档位 >10%
    #   s=5: 窗口 [10,11,10,12] 最低回撤 0 -> 0，档位 >10%
    # 基准率 = 2/4 = 0.5；决策日档位 <5%，同档 {2,3} 标签 [1,1] -> 1.0。
    # 决策日结果：窗口 [12,11,13,12] 最低回撤约 -8.3% -> 0（需补下标 11
    # 的值，否则决策日自身标签都不完整，predict_at 应返回 None）。
    nav = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]
    pred = predict_at(nav, 8, 3, label_drawdown_breach, window=3)
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.5)
    assert pred.state_prob == pytest.approx(1.0)
    assert pred.bucket_train_n == 2
    assert pred.outcome == 0


def test_predict_at_state_fallback_when_bucket_unseen_in_training():
    # 训练起点全部 <5% 档，决策日跌至 -20%（>10% 档）：状态概率回退为基准率。
    nav = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 8.0, 9.0, 9.5]
    pred = predict_at(nav, 6, 2, label_positive_return, window=3)
    assert pred is not None
    assert pred.bucket == BUCKET_GT10
    assert pred.bucket_train_n == 0
    assert pred.state_fallback is True
    assert pred.state_prob == pytest.approx(pred.baseline_prob)


def test_no_future_leakage():
    # 构造 60 天序列：前 40 天平稳微涨，后 20 天人为暴跌；改动决策日
    # 之后的净值，决策日之前（含决策日）的预测必须逐点不变。
    # 直接用 predict_at（小窗口/小期限让手算与运行都可行），因为
    # generate_predictions 的期限是写死的默认口径（126/252 天）。
    base = [10.0 + 0.01 * i for i in range(60)]
    mutated = base[:40] + [5.0] * 20
    before = {
        t: predict_at(base, t, 2, label_positive_return, window=5)
        for t in range(20, 40)
    }
    after = {
        t: predict_at(mutated, t, 2, label_positive_return, window=5)
        for t in range(20, 40)
    }
    assert all(v is not None for v in before.values())
    # 概率本身（只用决策日之前已完成标签）对 40 日后的改动逐点不变；
    # 结果标签是事后观测：决策日 38 的标签用到下标 40 的净值，改动后
    # 翻转是预期行为，不得把它误读为“预测泄漏”——防空转正用它证明
    # 改动不是空操作。
    for idx in before:
        assert before[idx].baseline_prob == pytest.approx(after[idx].baseline_prob)
        assert before[idx].state_prob == pytest.approx(after[idx].state_prob)
    for idx in range(20, 38):
        assert before[idx].outcome == after[idx].outcome
    assert before[38].outcome != after[38].outcome
    assert label_positive_return(base, 40, horizon=2) != label_positive_return(
        mutated, 40, horizon=2
    )


def test_brier_and_counts():
    class P:  # 轻量替身，只用 Brier 输入字段
        def __init__(self, state_prob, baseline_prob, outcome, index):
            self.state_prob = state_prob
            self.baseline_prob = baseline_prob
            self.outcome = outcome
            self.index = index

    preds = [P(0.5, 0.5, 1, 0), P(0.5, 0.5, 0, 1)]
    assert brier_score(preds, use_state=True) == pytest.approx(0.25)
    assert brier_score([], use_state=True) is None
    assert non_overlapping_count(preds, horizon=1) == 2
    assert non_overlapping_count([], horizon=126) == 0


def test_generate_predictions_only_complete_labels():
    # 短序列（30 天）下 A 类期限 126 无完整标签 -> 空集。
    nav = [10.0 + 0.01 * i for i in range(30)]
    assert generate_predictions(nav, "A") == []
    # 默认口径单调递增序列：长度 1400 时 A 类决策日为 1260..1273
    # （末尾 -126），共 14 个预测；标签全为 1，基准率与状态概率均为 1。
    long_nav = [10.0 + 0.01 * i for i in range(1400)]
    preds = generate_predictions(long_nav, "A")
    assert len(preds) == 14
    assert preds[0].index == 1260 and preds[-1].index == 1273
    assert all(p.outcome == 1 for p in preds)
    assert all(p.baseline_prob == pytest.approx(1.0) for p in preds)
    assert all(p.state_prob == pytest.approx(1.0) for p in preds)
    assert all(p.bucket == BUCKET_LT5 for p in preds)
    with pytest.raises(ValueError):
        generate_predictions(nav, "C")
