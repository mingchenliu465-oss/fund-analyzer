"""概率预测实验 v2（离线实验，不进产品页面、不注册接口）。

条目 13 第二轮：检验信号本身。v1 报告第 7 节第 1 个开放问题——
v1 的改进主要来自时效加权，而不是回撤档位信号：在 161725 B 与
110020 A 两组，“只用加权基准率”本身就优于 v1。本轮不调加权常数
（半衰期 756 天、收缩伪计数 50 已冻结，见下），只换信号，与 v1 同
口径打分（同一评估、同一成绩单、同一技能分母）。

候选信号（全部只用决策日（含）之前的数据；定义事先固定、写死在
本模块中并在报告中披露，**不做参数扫描、不按测试集调参**）：
- ``"none"``：不要状态信号。状态概率即时效加权基准率（v1 里只作
  诊断的 ``wbaseline`` 变体，本轮升格为正式候选）。问的是：档位
  信号是否从一开始就是净负担。
- ``"trend"``：趋势信号。决策日累计净值与近 250 日简单均线的关系：
  ``"above"``（净值 >= 均线）或 ``"below"``（净值 < 均线）。
  事前依据：趋势跟踪类状态是最常见的行情状态划分之一；窗口取
  250 日与回撤窗口 ``WINDOW_DAYS`` 一致，不另引新常数。
- ``"momentum"``：动量信号。近 126 个交易日收益的正负：
  ``"up"``（净值高于 126 天前）或 ``"down"``（不高于）。
  事前依据：126 日即 A 类期限本身，不另引新常数；问的是“近期涨
  还是跌”是否比“离高点多远”更能区分未来。
- ``"drawdown"``：v1 的回撤档位信号（<5% / 5%–10% / >10%），只作
  参照：v2 用此信号必须逐点复现 v1（测试守住），v1 的数字不重算。

两个信号都是二值（相对回撤档位的三值），每态训练样本更大、收缩
起作用的空间更小——这是有意为之：若二值信号仍不如无信号，说明
问题不在档位粒度，而在“用历史状态条件频率预测未来”这条路本身。

v1 的两个机制原样保留：时效加权（半衰期 ``HALF_LIFE_DAYS = 756``，
约 3 个交易年）与向加权基准率收缩（伪计数 ``SHRINKAGE_M = 50``），
常数从 ``forecast_v1`` 导入、不得在本模块改写；下一轮如需换常数
须另起版本号（v3）并写清理由。档位定义、两类标签、期限、测试起点、
训练资格（起点需有完整信号窗口且标签在决策日之前已完整观测）、
比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单仍用
条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier 为分母。

``PredictionV2.bucket`` 字段存的是信号状态标签（回撤档位 / 趋势态 /
动量态 / ``"all"``），不是回撤档位——成绩单的校准、逐年、技能三部分
不依赖该字段；整体证据 verdict（样本外数与历史长度）与信号无关；
逐态样本数由运行脚本另行统计并按 ``MIN_BUCKET_N = 30`` 逐态判断，
不沿用成绩单里写死的回撤三档 verdict。

因果纪律与 v0/v1 相同：决策日 t 的预测只用 t（含）之前的数据；训练
标签必须在 t 之前已完整观测。改动 t 之后的净值，t 之前（含 t）的
预测必须逐点不变（测试守住）。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都
必须同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的
披露；禁止点位预测、涨跌断言、买卖推荐表述。v2 未达产品化门槛前
不得以任何形式在前端露出（条目 13）。
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.forecast_baseline import (
    HORIZON_A_DAYS,
    HORIZON_B_DAYS,
    TEST_START_INDEX,
    WINDOW_DAYS,
    bucket_for_drawdown,
    drawdown_at,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M

# 信号名（写死，不得运行时新增或改定义）。
SIGNAL_DRAWDOWN = "drawdown"
SIGNAL_TREND = "trend"
SIGNAL_MOMENTUM = "momentum"
SIGNAL_NONE = "none"
SIGNALS = (SIGNAL_DRAWDOWN, SIGNAL_TREND, SIGNAL_MOMENTUM, SIGNAL_NONE)

# 各信号的状态取值（写死；二值信号有意取 2 态，见模块 docstring）。
STATE_TREND_ABOVE = "above"
STATE_TREND_BELOW = "below"
STATE_MOMENTUM_UP = "up"
STATE_MOMENTUM_DOWN = "down"
STATE_ALL = "all"

# 动量信号的回看期：126 个交易日，即 A 类期限本身，不另引新常数。
MOMENTUM_LOOKBACK_DAYS = HORIZON_A_DAYS


@dataclass
class PredictionV2:
    index: int
    bucket: str  # 信号状态标签（见模块 docstring）；成绩单只用它做逐态计数
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时状态概率回退为加权基准率
    baseline_weighted: float  # 时效加权基准率（诊断用）
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _weight(age_days: int, half_life: float = HALF_LIFE_DAYS) -> float:
    """起点相对决策日的时效权重：半衰期 ``half_life`` 天的指数衰减。"""
    return 0.5 ** (age_days / half_life)


def signal_state(nav: list[float], index: int, signal: str,
                 window: int = WINDOW_DAYS) -> str | None:
    """决策日 ``index`` 的信号状态（只用 ``index``（含）之前的数据）。

    数据不足以定义该信号时返回 None（调用方不得把该起点/决策日计入
    训练或测试集）。``"none"`` 恒为 ``"all"``，永不返回 None。
    """
    if signal == SIGNAL_NONE:
        return STATE_ALL
    if signal == SIGNAL_DRAWDOWN:
        if index < window - 1:
            return None
        return bucket_for_drawdown(drawdown_at(nav, index, window))
    if signal == SIGNAL_TREND:
        if index < window - 1:
            return None
        start = index - window + 1
        mean = sum(nav[start : index + 1]) / window
        return STATE_TREND_ABOVE if nav[index] >= mean else STATE_TREND_BELOW
    if signal == SIGNAL_MOMENTUM:
        if index < MOMENTUM_LOOKBACK_DAYS:
            return None
        return (
            STATE_MOMENTUM_UP
            if nav[index] > nav[index - MOMENTUM_LOOKBACK_DAYS]
            else STATE_MOMENTUM_DOWN
        )
    raise ValueError(f"unknown signal: {signal!r}")


def _states_for_signal(signal: str) -> tuple[str, ...]:
    """该信号的全部状态取值（递推实现用它初始化每态统计）。"""
    if signal == SIGNAL_DRAWDOWN:
        return ("<5%", "5%-10%", ">10%")
    if signal == SIGNAL_TREND:
        return (STATE_TREND_ABOVE, STATE_TREND_BELOW)
    if signal == SIGNAL_MOMENTUM:
        return (STATE_MOMENTUM_UP, STATE_MOMENTUM_DOWN)
    if signal == SIGNAL_NONE:
        return (STATE_ALL,)
    raise ValueError(f"unknown signal: {signal!r}")


def _training_starts(decision: int, horizon: int, window: int = WINDOW_DAYS):
    """与 v0/v1 相同的训练资格：起点需有完整回撤窗口（index >= window-1）
    且标签在决策日之前已完整观测（起点 <= decision - horizon）。"""
    return range(window - 1, decision - horizon + 1)


def weighted_predict_at_v2(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str, window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M) -> PredictionV2 | None:
    """单个决策日的 v2 预测（逐项直算参照实现）。

    ``signal`` 为 ``"drawdown"`` / ``"trend"`` / ``"momentum"`` / ``"none"``；
    ``"none"`` 时状态概率即加权基准率（不分态、不收缩）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    if decision < window - 1:
        return None
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return None
    outcome = label_fn(nav, decision, horizon)
    if outcome is None:
        return None
    total_n = 0
    total_sum = 0
    weight_n = 0.0
    weight_sum = 0.0
    state_n = 0
    state_wn = 0.0
    state_ws = 0.0
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        start_state = signal_state(nav, start, signal, window)
        if start_state is None:
            continue
        total_n += 1
        total_sum += label
        w = _weight(decision - start, half_life)
        weight_n += w
        weight_sum += w * label
        if start_state == state:
            state_n += 1
            state_wn += w
            state_ws += w * label
    if total_n == 0:
        return None
    baseline = total_sum / total_n
    baseline_weighted = weight_sum / weight_n
    if signal == SIGNAL_NONE:
        state_prob = baseline_weighted
        fallback = False
    elif state_wn == 0:
        state_prob = baseline_weighted
        fallback = True
    else:
        state_prob = (state_ws + shrinkage_m * baseline_weighted) / (
            state_wn + shrinkage_m
        )
        fallback = False
    return PredictionV2(
        index=decision,
        bucket=state,
        signal=signal,
        baseline_prob=baseline,
        state_prob=state_prob,
        outcome=outcome,
        train_n=total_n,
        bucket_train_n=state_n,
        state_fallback=fallback,
        baseline_weighted=baseline_weighted,
        weight_n=weight_n,
        bucket_weight_n=state_wn,
    )


def generate_predictions_v2(nav: list[float], kind: str, signal: str,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M) -> list[PredictionV2]:
    """滚动原点样本外 v2 预测（与 ``weighted_predict_at_v2`` 同口径）。

    实现与 v1 的递推相同：决策日每前进一天，全部旧权重乘一次衰减因子
    ``0.5 ** (1 / half_life)``，同时恰好一个新训练起点进入资格
    （起点 = 决策日 − 期限），其初始权重为 ``0.5 ** (期限 / half_life)``；
    无加权统计（v0 基准率）同步递增。首个决策日的统计直接逐项算出，
    之后每步 O(1)。``weighted_predict_at_v2`` 保留为逐项直算的参照实现，
    两者在同一序列上的抽查一致性由测试与运行脚本核对。
    """
    if kind == "A":
        horizon, label_fn = HORIZON_A_DAYS, label_positive_return
    elif kind == "B":
        horizon, label_fn = HORIZON_B_DAYS, label_drawdown_breach
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    n = len(nav)
    states = [signal_state(nav, i, signal, window) for i in range(n)]
    labels = [label_fn(nav, i, horizon) for i in range(n)]
    last_testable = n - 1 - horizon
    first_decision = max(test_start, window - 1)
    if first_decision > last_testable:
        return []
    decay = 0.5 ** (1.0 / half_life)
    new_weight = 0.5 ** (horizon / half_life)
    state_names = _states_for_signal(signal)

    def _compute(decision: int):
        """直接逐项算出该决策日的全部统计（只用于首个决策日）。"""
        total_n = total_sum = 0
        weight_n = weight_sum = 0.0
        state_n: dict[str, int] = {s: 0 for s in state_names}
        state_wn: dict[str, float] = {s: 0.0 for s in state_names}
        state_ws: dict[str, float] = {s: 0.0 for s in state_names}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None or states[start] is None:
                continue
            total_n += 1
            total_sum += label
            w = _weight(decision - start, half_life)
            weight_n += w
            weight_sum += w * label
            s = states[start]
            state_n[s] += 1
            state_wn[s] += w
            state_ws[s] += w * label
        return total_n, total_sum, weight_n, weight_sum, state_n, state_wn, state_ws

    def _make_pred(decision: int, total_n, total_sum, weight_n, weight_sum,
                   state_n, state_wn, state_ws) -> PredictionV2 | None:
        if total_n == 0:
            return None
        outcome = labels[decision]
        if outcome is None or states[decision] is None:
            return None
        state = states[decision]
        baseline = total_sum / total_n
        baseline_weighted = weight_sum / weight_n
        if signal == SIGNAL_NONE:
            state_prob, fallback = baseline_weighted, False
        elif state_wn[state] == 0:
            state_prob, fallback = baseline_weighted, True
        else:
            state_prob = (state_ws[state] + shrinkage_m * baseline_weighted) / (
                state_wn[state] + shrinkage_m
            )
            fallback = False
        return PredictionV2(
            index=decision,
            bucket=state,
            signal=signal,
            baseline_prob=baseline,
            state_prob=state_prob,
            outcome=outcome,
            train_n=total_n,
            bucket_train_n=state_n[state],
            state_fallback=fallback,
            baseline_weighted=baseline_weighted,
            weight_n=weight_n,
            bucket_weight_n=state_wn[state],
        )

    preds: list[PredictionV2] = []
    total_n, total_sum, weight_n, weight_sum, state_n, state_wn, state_ws = (
        _compute(first_decision)
    )
    pred = _make_pred(
        first_decision, total_n, total_sum, weight_n, weight_sum,
        state_n, state_wn, state_ws,
    )
    if pred is not None:
        preds.append(pred)
    # 之后每步：旧权重衰减 + 一个新训练起点进入（起点 = 决策日 − 期限）。
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        weight_n *= decay
        weight_sum *= decay
        for s in state_names:
            state_wn[s] *= decay
            state_ws[s] *= decay
        if (
            new_start >= window - 1
            and labels[new_start] is not None
            and states[new_start] is not None
        ):
            label = labels[new_start]
            total_n += 1
            total_sum += label
            weight_n += new_weight
            weight_sum += new_weight * label
            s = states[new_start]
            state_n[s] += 1
            state_wn[s] += new_weight
            state_ws[s] += new_weight * label
        pred = _make_pred(
            decision, total_n, total_sum, weight_n, weight_sum,
            state_n, state_wn, state_ws,
        )
        if pred is not None:
            preds.append(pred)
    return preds
