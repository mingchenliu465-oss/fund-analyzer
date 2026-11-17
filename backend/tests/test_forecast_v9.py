"""概率预测实验 v9 的测试：多年一边倒门槛定义、手算、防未来函数、递推一致性。

期望值全部在测试内手算（用与模块无关的直接表达式 ``0.5 ** x``），
不调用模块内部函数反推；v9 与 v2 的关系测试以 v2 的公开输出为参照
（v9 的定义本身就是“对 v2 输出做多年一边倒门槛判断”）；小参数
（窗口/期限/半衰期）只用于让手算可行，默认参数口径由实验报告的真实
数据运行覆盖。v9 需要日期输入（逐年占比按训练起点所在日历年分组）。
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
from experiments.forecast_v9 import (
    MIN_YEAR_N,
    ONE_SIDED_SHARE,
    WINDOW_YEARS,
    generate_predictions_v9,
    weighted_predict_at_v9,
)

# 与 test_forecast_baseline / test_forecast_v1 / ... / test_forecast_v8
# 共用的同一条手算序列。
NAV = [10.0, 10.0, 10.0, 12.0, 9.0, 10.0, 11.0, 10.0, 12.0, 11.0, 13.0, 12.0]

# 手算序列的日期：<5% 档的三个训练起点分属三年——
# 起点 2 在 2010 年、起点 3 在 2011 年、起点 6 在 2012 年；
# 其余下标的年份只须可解析，不进入 <5% 档的逐年统计。
DATES = [
    "2010-01-05", "2010-02-05", "2010-03-05", "2011-04-05",
    "2011-05-05", "2012-06-05", "2012-07-05", "2012-08-05",
    "2012-09-05", "2012-10-05", "2012-11-05", "2012-12-05",
]

# 决策日 8 的触发情形（窗口 3、期限 2、半衰期 10000 天、收缩伪计数 1，
# 每年最少标签数 1）：训练起点 s in [2, 6]，自定义标签 [1, 1, 0, 0, 1]，
# 回撤档位 [<5%, <5%, >10%, >10%, <5%]；决策日 8 属 <5% 档，标签为 1。
# <5% 档逐年占比：2010 年 1.0、2011 年 1.0、2012 年 1.0——最近 3 年全
# 部强烈为正，方向 +1，门槛触发。
_TRIGGER_LABELS = {2: 1, 3: 1, 4: 0, 5: 0, 6: 1, 8: 1}


def _trigger_label_fn(nav, start, horizon):
    """触发情形的测试用标签函数。"""
    return _TRIGGER_LABELS.get(start)


def _hand_values_day8_trigger(half_life: float = 10000.0):
    """决策日 8 触发情形的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((8 - s) / half_life) for s in (2, 3, 4, 5, 6)}
    weight_n = sum(w.values())
    baseline_w = (w[2] + w[3] + w[6]) / weight_n
    bucket_wn = w[2] + w[3] + w[6]
    bucket_ws = w[2] + w[3] + w[6]
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "ungated": ungated,
    }


# 决策日 8 的不触发情形（窗口 3、期限 2、半衰期 1 天、收缩伪计数 1，
# 每年最少标签数 1）：与 v8 测试同一组数，训练起点 s in [2, 6]，自定
# 义标签 [0, 1, 1, 0, 1]，回撤档位 [<5%, <5%, >10%, >10%, <5%]。
# <5% 档逐年占比：2010 年 0.0、2011 年 1.0、2012 年 1.0——三年不同向，
# 方向 0，门槛不触发。注意 v7 在此触发（该档总体正占比约 0.9474、多数
# 占比 >= 0.9），v9 不触发：这是 v7 与 v9 分得开的直接证据（总体一边
# 倒、但不是一年接一年地一边倒）。
_CUSTOM_LABELS = {2: 0, 3: 1, 4: 1, 5: 0, 6: 1, 8: 1}


def _custom_label_fn(nav, start, horizon):
    """测试用标签函数：只在手算表里有值的起点返回标签，其余返回 None。"""
    return _CUSTOM_LABELS.get(start)


def _hand_values_day8(half_life: float = 1.0):
    """决策日 8 不触发情形的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((8 - s) / half_life) for s in (2, 3, 4, 5, 6)}
    weight_n = sum(w.values())
    baseline_w = (w[3] + w[4] + w[6]) / weight_n
    bucket_wn = w[2] + w[3] + w[6]
    bucket_ws = w[3] + w[6]
    pos_frac = bucket_ws / bucket_wn
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "pos_frac": pos_frac,
        "ungated": ungated,
    }


# 决策日 8 的反向触发情形（窗口 3、期限 2、半衰期 10000 天、收缩伪计
# 数 1，每年最少标签数 1）：训练起点 s in [2, 6]，自定义标签
# [0, 0, 1, 1, 0]，回撤档位 [<5%, <5%, >10%, >10%, <5%]。
# <5% 档逐年占比：2010 年 0.0、2011 年 0.0、2012 年 0.0——最近 3 年全
# 部强烈为负，方向 -1，门槛触发。
_NEGATIVE_LABELS = {2: 0, 3: 0, 4: 1, 5: 1, 6: 0, 8: 0}


def _negative_label_fn(nav, start, horizon):
    """反向触发情形的测试用标签函数。"""
    return _NEGATIVE_LABELS.get(start)


def _hand_values_day8_negative(half_life: float = 10000.0):
    """决策日 8 反向触发情形的手算量（只用 ``0.5 ** x``，不调用模块内部函数）。"""
    w = {s: 0.5 ** ((8 - s) / half_life) for s in (2, 3, 4, 5, 6)}
    weight_n = sum(w.values())
    baseline_w = (w[4] + w[5]) / weight_n
    bucket_wn = w[2] + w[3] + w[6]
    bucket_ws = 0.0
    ungated = (bucket_ws + baseline_w) / (bucket_wn + 1.0)
    return {
        "w": w,
        "weight_n": weight_n,
        "baseline_w": baseline_w,
        "bucket_wn": bucket_wn,
        "bucket_ws": bucket_ws,
        "ungated": ungated,
    }


def _pred_day8_trigger(**kwargs):
    """触发情形的默认参数调用（每年最少标签数须传 1，否则三年各只有
    1 个标签、都不够 30 个，门槛按定义不触发）。"""
    params = dict(
        window=3, half_life=10000.0, shrinkage_m=1.0, min_year_n=1,
    )
    params.update(kwargs)
    return weighted_predict_at_v9(
        NAV, 8, 2, _trigger_label_fn, SIGNAL_DRAWDOWN, dates=DATES, **params
    )


def test_multiyear_hand_computed_triggered():
    # 半衰期 10000 天：<5% 档最近 3 年逐年占比全为 1.0，方向 +1，
    # 门槛触发，状态概率 = 加权基准率。
    hv = _hand_values_day8_trigger()
    pred = _pred_day8_trigger()
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.signal == SIGNAL_DRAWDOWN
    assert pred.baseline_prob == pytest.approx(0.6)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is True
    assert pred.direction == 1
    assert pred.years_checked == (2012, 2011, 2010)
    assert pred.year_pos_fracs == pytest.approx((1.0, 1.0, 1.0))
    assert pred.year_counts == (1, 1, 1)
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_multiyear_hand_computed_not_triggered():
    # 半衰期 1 天：<5% 档总体正占比约 0.9474（v7 在此触发），但逐年占比
    # 为 0.0 / 1.0 / 1.0——三年不同向，方向 0，v9 不触发，状态概率 =
    # v2 未加门槛值。
    hv = _hand_values_day8()
    assert hv["pos_frac"] == pytest.approx(0.28125 / 0.296875)
    pred = weighted_predict_at_v9(
        NAV, 8, 2, _custom_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=1.0, shrinkage_m=1.0, min_year_n=1, dates=DATES,
    )
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.baseline_prob == pytest.approx(0.6)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is False
    assert pred.direction == 0
    assert pred.years_checked == (2012, 2011, 2010)
    assert pred.year_pos_fracs == pytest.approx((1.0, 1.0, 0.0))
    assert pred.year_counts == (1, 1, 1)
    assert pred.state_prob == pytest.approx(hv["ungated"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 1


def test_multiyear_hand_computed_negative_triggered():
    # 半衰期 10000 天：<5% 档最近 3 年逐年占比全为 0.0，方向 -1，
    # 门槛触发，状态概率 = 加权基准率。
    hv = _hand_values_day8_negative()
    pred = weighted_predict_at_v9(
        NAV, 8, 2, _negative_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0, min_year_n=1,
        dates=DATES,
    )
    assert pred is not None
    assert pred.bucket == "<5%"
    assert pred.baseline_prob == pytest.approx(2.0 / 5.0)
    assert pred.baseline_weighted == pytest.approx(hv["baseline_w"])
    assert pred.weight_n == pytest.approx(hv["weight_n"])
    assert pred.bucket_weight_n == pytest.approx(hv["bucket_wn"])
    assert pred.gated is True
    assert pred.direction == -1
    assert pred.years_checked == (2012, 2011, 2010)
    assert pred.year_pos_fracs == pytest.approx((0.0, 0.0, 0.0))
    assert pred.year_counts == (1, 1, 1)
    assert pred.state_prob == pytest.approx(hv["baseline_w"])
    assert pred.ungated_state_prob == pytest.approx(hv["ungated"])
    assert pred.state_fallback is False
    assert pred.train_n == 5
    assert pred.bucket_train_n == 3
    assert pred.outcome == 0


def test_window_years_min_n_and_threshold_parameters():
    # 以触发情形（决策日 8、三年逐年占比全为 1.0）为基底：
    # 每年最少标签数 2 时三年各只有 1 个标签、有证据的年份为 0，门槛不
    # 触发；窗口改 4 年时只有 3 个有证据的年份，门槛不触发；窗口改 2 年
    # 时最近 2 年（2012、2011）全为 1.0，门槛仍触发；门槛恰好等于逐年
    # 占比 1.0 时触发（触发条件是 >=）；门槛 0.95 时仍触发；默认门槛
    # 0.8 时触发。
    v2 = weighted_predict_at_v2(
        NAV, 8, 2, _trigger_label_fn, SIGNAL_DRAWDOWN,
        window=3, half_life=10000.0, shrinkage_m=1.0,
    )
    assert v2 is not None
    pred_min_n = _pred_day8_trigger(min_year_n=2)
    assert pred_min_n is not None
    assert pred_min_n.gated is False
    assert pred_min_n.direction == 0
    assert pred_min_n.years_checked == ()
    assert pred_min_n.state_prob == pytest.approx(v2.state_prob)
    pred_window4 = _pred_day8_trigger(window_years=4)
    assert pred_window4 is not None
    assert pred_window4.gated is False
    assert pred_window4.direction == 0
    assert pred_window4.years_checked == ()
    assert pred_window4.state_prob == pytest.approx(v2.state_prob)
    pred_window2 = _pred_day8_trigger(window_years=2)
    assert pred_window2 is not None
    assert pred_window2.gated is True
    assert pred_window2.direction == 1
    assert pred_window2.years_checked == (2012, 2011)
    assert pred_window2.state_prob == pytest.approx(
        pred_window2.baseline_weighted
    )
    pred_boundary = _pred_day8_trigger(one_sided_share=1.0)
    assert pred_boundary is not None
    assert pred_boundary.gated is True
    assert pred_boundary.state_prob == pytest.approx(
        pred_boundary.baseline_weighted
    )
    pred_high = _pred_day8_trigger(one_sided_share=0.95)
    assert pred_high is not None
    assert pred_high.gated is True
    pred_default = _pred_day8_trigger()
    assert pred_default is not None
    assert pred_default.gated is True
    assert pred_default.state_prob == pytest.approx(
        pred_default.baseline_weighted
    )


def _long_series():
    # 1500 天、横跨 2010–2014 五个日历年（与 v6/v7/v8 测试同一序列）：
    # 默认参数下 A/B 两类触发与未触发两种情形都出现（草稿脚本已核实：
    # A 类 619 天触发、B 类 367 天触发），递推与直算的一致性用它。
    nav = [1000.0 + 3.0 * ((i * 7) % 13) - 0.5 * i for i in range(1500)]
    assert min(nav) > 0
    return nav


def _long_dates(n):
    # 每 300 天一个日历年，与 _long_series 的 2010–2014 跨度对应。
    return [f"{2010 + i // 300}-06-15" for i in range(n)]


def _sine_series():
    # 1500 天正弦净值（周期约 157 天，无趋势），振幅在第 750 天切换：
    # 前半段振幅 30（峰谷跌幅约 5.8% < 10%，B 类标签恒为 0），后半段
    # 振幅 120（峰谷跌幅约 21% > 10%，B 类标签恒为 1）。
    return [
        1000.0 + (30.0 if i < 750 else 120.0) * math.sin(i / 25.0)
        for i in range(1500)
    ]


def _crash_recovery_series():
    # 0–499 天平盘 1000；500–530 天跌到 600；530 天起每天 +0.35 缓慢修复：
    # 修复期回撤（250 天窗口）仍 >10%，126 天远期收益为正。
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
    # v9 的定义：未触发日状态概率 = v2；触发日 = 加权基准率；其余字段
    # 与 v2 逐点一致（A/B 两类）。长序列（窗口 30）上 A/B 两类触发与未
    # 触发两种情形都出现（草稿脚本核实：A 类 619 天触发、B 类 367 天触发）。
    nav = _long_series()
    dates = _long_dates(len(nav))
    for kind in ("A", "B"):
        v9_preds = generate_predictions_v9(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250, dates=dates
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250
        )
        assert len(v9_preds) == len(v2_preds)
        assert v9_preds, f"{kind} 应有预测"
        gated_seen = ungated_seen = 0
        for p9, p2 in zip(v9_preds, v2_preds):
            assert p9.index == p2.index
            assert p9.bucket == p2.bucket
            assert p9.bucket_weight_n == pytest.approx(p2.bucket_weight_n, abs=1e-12)
            assert p9.gated == (p2.bucket_weight_n > 0 and p9.direction != 0)
            assert p9.direction in (-1, 0, 1)
            if p9.direction != 0:
                assert len(p9.years_checked) == WINDOW_YEARS
                assert len(p9.year_pos_fracs) == WINDOW_YEARS
                assert len(p9.year_counts) == WINDOW_YEARS
                assert all(c >= MIN_YEAR_N for c in p9.year_counts)
                if p9.direction == 1:
                    assert all(f >= ONE_SIDED_SHARE for f in p9.year_pos_fracs)
                else:
                    assert all(
                        f <= 1.0 - ONE_SIDED_SHARE for f in p9.year_pos_fracs
                    )
            else:
                assert p9.years_checked == () or len(p9.years_checked) == WINDOW_YEARS
            assert p9.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            if p9.gated:
                gated_seen += 1
                assert p9.state_prob == pytest.approx(p9.baseline_weighted, abs=1e-12)
            else:
                ungated_seen += 1
                assert p9.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p9.baseline_prob == pytest.approx(p2.baseline_prob, abs=1e-12)
            assert p9.baseline_weighted == pytest.approx(p2.baseline_weighted, abs=1e-12)
            assert p9.outcome == p2.outcome
            assert p9.train_n == p2.train_n
            assert p9.bucket_train_n == p2.bucket_train_n
            assert p9.state_fallback == p2.state_fallback
        assert gated_seen > 0, f"{kind} 应有触发门槛的决策日"
        assert ungated_seen > 0, f"{kind} 应有未触发门槛的决策日"


def test_none_signal_identity():
    # 无信号：该态即全部训练集，逐年占比是全局逐年占比；触发时状态概
    # 率本就等于加权基准率，所以状态概率恒等于 v2（门槛不改变状态概率，
    # 只可能改变 gated 标记）。正弦序列上 A/B 两类都应与 v2 逐点相同。
    nav = _sine_series()
    dates = _long_dates(len(nav))
    for kind in ("A", "B"):
        v9_preds = generate_predictions_v9(
            nav, kind, SIGNAL_NONE, window=30, test_start=250, dates=dates
        )
        v2_preds = generate_predictions_v2(
            nav, kind, SIGNAL_NONE, window=30, test_start=250
        )
        assert len(v9_preds) == len(v2_preds)
        for p9, p2 in zip(v9_preds, v2_preds):
            assert p9.state_prob == pytest.approx(p2.state_prob, abs=1e-12)
            assert p9.ungated_state_prob == pytest.approx(p2.state_prob, abs=1e-12)


def test_no_future_leakage():
    # 前 160 天平稳微涨，后 40 天人为暴跌；改动决策日之后的净值，
    # 决策日之前（含决策日）的预测必须逐点不变。逐年占比只用当天的训练
    # 集（t 之前的数据），不引入未来信息。
    base = [10.0 + 0.01 * i for i in range(200)]
    mutated = base[:160] + [5.0] * 40
    dates = [f"{2010 + i // 50}-06-15" for i in range(200)]
    before = {
        t: weighted_predict_at_v9(
            base, t, 2, label_positive_return, SIGNAL_DRAWDOWN,
            window=5, min_year_n=1, dates=dates,
        )
        for t in range(130, 160)
    }
    after = {
        t: weighted_predict_at_v9(
            mutated, t, 2, label_positive_return, SIGNAL_DRAWDOWN,
            window=5, min_year_n=1, dates=dates,
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
        assert before[idx].direction == after[idx].direction
        assert before[idx].years_checked == after[idx].years_checked
        assert before[idx].year_pos_fracs == pytest.approx(
            after[idx].year_pos_fracs
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
    dates = _long_dates(len(nav))
    for kind in ("A", "B"):
        preds = generate_predictions_v9(
            nav, kind, SIGNAL_DRAWDOWN, window=30, test_start=250, dates=dates
        )
        assert preds, f"{kind} 应有预测"
        horizon = 126 if kind == "A" else 252
        label_fn = label_positive_return if kind == "A" else label_drawdown_breach
        checked = preds if kind == "A" else preds[::25]
        for pred in checked:
            direct = weighted_predict_at_v9(
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
            assert direct.direction == pred.direction
            assert direct.years_checked == pred.years_checked
            assert direct.year_pos_fracs == pytest.approx(
                pred.year_pos_fracs, abs=1e-9
            )
            assert direct.year_counts == pred.year_counts
            assert direct.bucket == pred.bucket
            assert direct.outcome == pred.outcome


def test_degenerate_all_zero_labels():
    # 单调递减但始终为正的序列：全部 A 类标签为 0，逐年占比全为 0.0，
    # 方向 -1，门槛触发，状态概率 = 加权基准率 = 0（与 v8 不同：v8 的
    # 相对差距在此为 0、门槛不触发；v9 的多年一边倒在此触发）。
    nav = [1000.0 - i for i in range(200)]
    dates = [f"{2010 + i // 50}-06-15" for i in range(200)]
    pred = weighted_predict_at_v9(
        nav, 150, 2, label_positive_return, SIGNAL_DRAWDOWN,
        window=5, dates=dates,
    )
    assert pred is not None
    assert pred.baseline_prob == pytest.approx(0.0)
    assert pred.baseline_weighted == pytest.approx(0.0)
    assert pred.gated is True
    assert pred.direction == -1
    assert len(pred.years_checked) == 3
    assert pred.year_pos_fracs == pytest.approx((0.0, 0.0, 0.0))
    assert pred.ungated_state_prob == pytest.approx(0.0)
    assert pred.state_prob == pytest.approx(0.0)


def test_constants_frozen_and_invalid_inputs():
    # 常数写死：多年窗口 3 年、“八成以上一边倒”0.8、每年最少标签数 30
    # （借用成绩单 MIN_BUCKET_N=30 的已有证据规则）、半衰期 756 天、收
    # 缩伪计数 50（均从 v1 继承、未改）。
    assert WINDOW_YEARS == 3
    assert ONE_SIDED_SHARE == 0.8
    assert MIN_YEAR_N == 30
    assert HALF_LIFE_DAYS == 756
    assert SHRINKAGE_M == 50.0
    nav = _long_series()
    dates = _long_dates(len(nav))
    # 默认参数下短序列无完整标签 -> 空集；非法信号/类别抛错。
    assert generate_predictions_v9(
        [10.0 + 0.01 * i for i in range(30)], "A",
        dates=[f"2010-06-15"] * 30,
    ) == []
    with pytest.raises(ValueError):
        generate_predictions_v9(nav, "A", "nope", dates=dates)
    with pytest.raises(ValueError):
        generate_predictions_v9(nav, "C", dates=dates)
    with pytest.raises(ValueError):
        weighted_predict_at_v9(NAV, 8, 2, label_positive_return, "nope", dates=DATES)
    # dates 未传、长度不符、无法解析的日期都抛错（不静默用序号代替年份）。
    with pytest.raises(ValueError):
        generate_predictions_v9(nav, "A")
    with pytest.raises(ValueError):
        generate_predictions_v9(nav, "A", dates=dates[:-1])
    bad_dates = list(dates)
    bad_dates[10] = "not-a-date"
    with pytest.raises(ValueError):
        generate_predictions_v9(nav, "A", dates=bad_dates)
    # 日期对象与字符串等价。
    import datetime

    date_objs = [datetime.date(2010 + i // 300, 6, 15) for i in range(len(nav))]
    preds_str = generate_predictions_v9(
        nav, "A", SIGNAL_DRAWDOWN, window=30, test_start=250, dates=dates
    )
    preds_obj = generate_predictions_v9(
        nav, "A", SIGNAL_DRAWDOWN, window=30, test_start=250, dates=date_objs
    )
    assert len(preds_str) == len(preds_obj)
    for p_str, p_obj in zip(preds_str, preds_obj):
        assert p_str.state_prob == pytest.approx(p_obj.state_prob, abs=1e-12)
        assert p_str.gated == p_obj.gated
