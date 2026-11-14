"""概率预测实验 v6 的测试：行情集中度门槛定义、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v6 与 v2 的关系测试以 v2 的公开输出为参照
（v6 的定义本身就是“对 v2 输出做行情集中度门槛判断”）；小参数
（窗口/期限/半衰期）只用于让手算可行，默认参数口径由实验报告的真实
数据运行覆盖。日期全部用 ``"YYYY-MM-DD"`` 字符串显式给出。
"""

import pytest
from datetime import date, timedelta

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
from experiments.forecast_v6 import (
    REGIME_MAX_DOMINANT_SHARE,
    generate_predictions_v6,
    weighted_predict_at_v6,
)

# 与 test_forecast_baseline / test_forecast_v1 / ... / test_forecast_v5
# 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]

# 决策日 8 的手算情形（窗口 3、期限 2、半衰期 2 天、收缩伪计数 1）：
# 训练起点 s in [2, 6]，标签 [0, 0, 1, 0, 1]，回撤档位
# [<5%, <5%, >10%, >10%, <5%]；决策日 8 属 <5% 档。
# 权重 w = 0.5 ** ((8 - s) / 2)：
#   s=2: 0.125；s=3: 0.5**2.5；s=4: 0.25；s=5: 0.5**1.5；s=6: 0.5。
# 权重和 = 0.125 + 0.5**2.5 + 0.25 + 0.5**1.5 + 0.5；
# 加权标签和 = 0.25（s=4）+ 0.5（s=6）= 0.75；
# 加权基准率 = 0.75 / 权重和。
# 同态（<5%）加权标签和 = 0.5（s=6），加权样本量 =
#   0.125 + 0.5**2.5 + 0.5；未触发门槛的状态概率 =
#   (0.5 + 1 × 加权基准率) / (同态加权样本量 + 1)。
# 无加权基准率（比较基准）= 2/5 = 0.4；决策日结果标签为 1。
DATES_GATED = [
    "2009-01-05", "2009-02-05", "2010-01-05", "2010-06-05",
    "2011-01-05", "2011-06-05", "2010-12-05", "2012-01-05",
    "2012-02-05", "2012-03-05", "2012-04-05", "2012-05-05",
]
# <5% 档的三个训练起点 s=2、3、6 在 DATES_GATED 里全部落在 2010 年，
# 主导年份占比 = 1.0 >= 0.5 ——门槛触发。
DATES_SPREAD = [
    "2009-01-05", "2009-02-05", "2010-01-05", "2011-06-05",
    "2013-01-05", "2014-06-05", "2012-12-05", "2015-01-05",
    "2015-02-05", "2015-03-05", "2015-04-05", "2015-05-05",
]
# DATES_SPREAD 里 <5% 档起点 s=2→2010、s=3→2011、s=6→2012，各一年。


def _hand_values(half_life: float = 2.0):
    """决策日 8 的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w2 = 0.5 ** ((8 - 2) / half_life)
    w3 = 0.5 ** ((8 - 3) / half_life)
    w4 = 0.5 ** ((8 - 4) / half_life)
    w5 = 0.5 ** ((8 - 5) / half_life)
    w6 = 0.5 ** ((8 - 6) / half_life)
    weight_n = w2 + w3 + w4 + w5 + w6
    baseline_w = (w4 + w6) / weight_n
    bucket_wn = w2 + w3 + w6
    ungated = (w6 + baseline_w) / (bucket_wn + 1.0)
    return {
        "w2": w2, "w3": w3, "w4": w4, "w5": w5, "w6": w6,
        "weight_n": weight_n, "baseline_w": baseline_w,
        "bucket_wn": bucket_wn, "ungated": ungated,
    }


def test_regime_gate_hand_computed_triggered():
    # DATES_GATED：<5% 档三个训练起点全在 2010 年，主导年份占比 1.0，
    # 有效年数 1.0，门槛触发，状态概率 = 加权基准率。
    hv = _hand_values()
    pred = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, dates=DATES_GATED,
    )
    assert pred is not None
    assert pred.bucket == BUCKET_LT5
    assert pred.signal == SIGNAL_DRAWDOWN
    assert pred.baseline_prob == pytest.approx(0.4)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is True
    assert pred.dominant_year_share == pytest.approx(1.0)
    assert pred.dominant_year == 2010
    assert pred.effective_years == pytest.approx(1.0)
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_regime_gate_hand_computed_not_triggered():
    # DATES_SPREAD + 半衰期 10000 天：权重几乎相等，<5% 档三起点分属
    # 三年，主导年份占比 = w6 / (w2 + w3 + w6) ≈ 1/3 < 0.5，不触发。
    hv = _hand_values(half_life=10000.0)
    share = hv["w6"] / hv["bucket_wn"]
    assert 0.30 < share < 0.35
    pred = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0, dates=DATES_SPREAD,
    )
    assert pred is not None
    assert pred.gated is False
    assert pred.dominant_year_share == pytest.approx(share)
    assert pred.dominant_year == 2012
    assert pred.effective_years == pytest.approx(
        1.0 / sum((w / hv["bucket_wn"]) ** 2 for w in (hv["w2"], hv["w3"], hv["w6"]))
    )
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])


def test_gate_threshold_parameter_and_boundary():
    # 以未触发情形（DATES_SPREAD、半衰期 10000 天、占比约 1/3）为基底：
    # 门槛 0.30 时触发（占比约 0.3334 >= 0.30）；门槛恰好等于占比时触发
    # （触发条件是 >=）；门槛 0.5 时不触发；门槛 0 时恒触发。
    hv = _hand_values(half_life=10000.0)
    share = hv["w6"] / hv["bucket_wn"]
    v2 = weighted_predict_at_v2(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    pred_low = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        max_dominant_share=0.30, dates=DATES_SPREAD,
    )
    assert pred_low is not None
    assert pred_low.gated is True
    assert pred_low.state_prob == pytest.approx(pred_low.baseline_weighted)
    pred_boundary = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        max_dominant_share=share, dates=DATES_SPREAD,
    )
    assert pred_boundary is not None
    assert pred_boundary.gated is True
    assert pred_boundary.state_prob == pytest.approx(pred_boundary.baseline_weighted)
    pred_default = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0, dates=DATES_SPREAD,
    )
    assert pred_default is not None
    assert pred_default.gated is False
    assert pred_default.state_prob == pytest.approx(v2.state_prob)
    pred_zero = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
        max_dominant_share=0.0, dates=DATES_SPREAD,
    )
    assert pred_zero is not None
    assert pred_zero.gated is True
    assert pred_zero.state_prob == pytest.approx(pred_zero.baseline_weighted)


def _long_series():
    # 1500 天、横跨 2010–2014 五个日历年：测试期初年训练质量集中在 2010 年
    # （门槛触发）、后期训练质量分散到多年（门槛不触发），两种情形都出现。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(1500)]
    assert min(nav) > 0
    start = date(2010, 1, 4)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(1500)]
    return nav, dates


def test_relation_matches_v2():
    # v6 的定义：未触发日状态概率 = v2；触发日 = 加权基准率；其余字段
    # 与 v2 逐点一致（A/B 两类）。长序列上触发与未触发两种情形都应出现。
    nav, dates = _long_series()
    for kind in ("A", "B"):
        v6_preds = generate_predictions_v6(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250, dates=dates
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert len(v6_preds) == len(v2_preds)
        assert v6_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p6, p2 in zip(v6_preds, v2_preds):
            assert p6.index == p2.index
            assert p6.bucket == p2.bucket
            assert p6.bucket_weight_n == pytest.approx(p2.bucket_weight_n, abs=1e-12)
            assert p6.gated == (
                p2.bucket_weight_n > 0
                and p6.dominant_year_share >= REGIME_MAX_DOMINANT_SHARE
            )
            assert 0.0 <= p6.dominant_year_share <= 1.0
            if p2.bucket_weight_n > 0:
                assert p6.effective_years >= 1.0
                assert p6.dominant_year is not None
            else:
                assert p6.gated is False
                assert p6.dominant_year is None
            assert p6.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            if p6.gated:
                gated_seen += 1
                assert p6.state_prob == pytest.approx(p6.baseline_weighted, abs=1e-12)
            else:
                ungated_seen += 1
                assert p6.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p6.baseline_prob == pytest.approx(p2.baseline_prob, abs=1e-12)
            assert p6.baseline_weighted == pytest.approx(p2.baseline_weighted, abs=1e-12)
            assert p6.outcome == p2.outcome
            assert p6.train_n == p2.train_n
            assert p6.bucket_train_n == p2.bucket_train_n
            assert p6.state_fallback == p2.state_fallback
        assert gated_seen > 0, f"{kind} 应有触发门槛的决策日"
        assert ungated_seen > 0, f"{kind} 应有未触发门槛的决策日"


def test_none_signal_identity():
    # 无信号：v2 的状态概率已等于加权基准率，门槛是恒等变换（触发与否
    # 状态概率都不变）。
    nav, dates = _long_series()
    for kind in ("A", "B"):
        v6_preds = generate_predictions_v6(
            nav, kind, SIGNAL_NONE, window=30, test_start=250, dates=dates
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        assert len(v6_preds) == len(v2_preds)
        for p6, p2 in zip(v6_preds, v2_preds):
            assert p6.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p6.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。年份占比只用当天的训练
    # 集（t 之前的数据），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    start = date(2010, 1, 4)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(200)]
    before = {
        t: weighted_predict_at_v6(
            base, t, 2, label_positive_return, SIGNAL_DRAWDOWN,
            window=5, dates=dates,
        )
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v6(
            mutated, t, 2, label_positive_return, SIGNAL_DRAWDOWN,
            window=5, dates=dates,
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
        assert before[idx].dominant_year_share == pytest.approx(
            after[idx].dominant_year_share
        )
        assert before[idx].dominant_year == after[idx].dominant_year
        assert before[idx].bucket == after[idx].bucket
    for idx in range(130, 158):
        assert before[idx].outcome == after[idx].outcome
    assert before[158].outcome != after[158].outcome


def test_generate_matches_direct():
    # 递推实现与逐项直算在决策日上逐点一致（A/B 两类）。
    # B 类期限 252 天：序列须足够长，取 700 天使 A/B 两类都有充足预测；
    # B 类只抽查部分决策日以控运行时长。
    nav, dates = _long_series()
    for kind in ("A", "B"):
        preds = generate_predictions_v6(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250, dates=dates
        )
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v6(
                nav, pred.index, horizon, label_fn, SIGNAL_DRAWDOWN,
                window=30, dates=dates,
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
            assert direct.dominant_year_share == pytest.approx(
                pred.dominant_year_share, abs=1e-9
            )
            assert direct.dominant_year == pred.dominant_year
            assert direct.effective_years == pytest.approx(
                pred.effective_years, abs=1e-9
            )
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0，门槛后状态概率仍为 0。
    nav = [1000.0 - i for i in range(200)]
    start = date(2010, 1, 4)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(200)]
    pred = weighted_predict_at_v6(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN, window=5, dates=dates
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：主导年份占比门槛 0.5（“过半”的唯一对称分界，见模块
    # docstring）、半衰期 756 天、收缩伪计数 50（均从 v1 继承、未改）。
    assert REGIME_MAX_DOMINANT_SHARE == 0.5
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    nav, dates = _long_series()
    # 未传 dates、dates 长度不符、日期无法解析时抛错（不静默用序号代替年份）。
    with pytest.raises(ValueError):
        generate_predictions_v6(nav, "A")
    with pytest.raises(ValueError):
        generate_predictions_v6(nav, "A", dates=dates[:-1])
    with pytest.raises(ValueError):
        weighted_predict_at_v6(
            NAV, 8, 2, label_positive_return, dates=["xx"] * len(NAV)
        )
    # 日期对象同样可用（取 .year）。
    date_objs = [date(2010, 1, 4) + timedelta(days=i) for i in range(len(NAV))]
    pred_obj = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, dates=date_objs,
    )
    pred_str = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0, dates=DATES_GATED,
    )
    assert pred_obj is not None and pred_str is not None
    assert pred_obj.dominant_year == pred_str.dominant_year
    assert pred_obj.state_prob == pytest.approx(pred_str.state_prob)
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v6(
        [10.0 + 0.01 * i for i in range(30)], "A", dates=[
            (date(2010, 1, 4) + timedelta(days=i)).isoformat() for i in range(30)
        ]
    ) == []
    with pytest.raises(ValueError):
        generate_predictions_v6(nav, "A", "nope", dates=dates)
    with pytest.raises(ValueError):
        generate_predictions_v6(nav, "C", dates=dates)
    with pytest.raises(ValueError):
        weighted_predict_at_v6(NAV, 8, 2, label_positive_return, "nope", dates=DATES_GATED)
    # 门槛为 0 时恒触发，退化为加权基准率（定义检查）。
    pred_gate0 = weighted_predict_at_v6(
        NAV, 8, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=3, half_life=2.0, shrinkage_m=1.0,
        max_dominant_share=0.0, dates=DATES_GATED,
    )
    assert pred_gate0 is not None
    assert pred_gate0.gated is True
    assert pred_gate0.state_prob == pytest.approx(pred_gate0.baseline_weighted)
