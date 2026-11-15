"""概率预测实验 v7（离线实验，不进产品页面、不注册接口）。

条目 13 第七轮：检验“训练样本标签极性”（v6 报告第 9 节开放问题 1 的
第一条路）。v6 的年份集中度门槛只量“证据从哪几年来的”，量不到“这几
年的标签是不是一边倒的”——110022 A 的高估口袋（80%–100% 校准档，
n=62，预测 0.81、实际 0.02，差 +0.80）就是直接证据：口袋 62 天的训练
证据分散在约 4 个有效年份里（主导年份占比最高 0.4899，贴着 0.5 的线，
一天也没触发），但**这几年的标签是一边倒的**（2015–2017 年消费股牛市
里 <5% 档的标签几乎全为正）。本轮问的是：**某态的训练标签如果九成以
上一边倒，状态项是不是就不该被信任**。

“标签极性”的定义（事先固定、写死在本模块中并在报告中披露，**不做参
数扫描、不按测试集调参**）：对某决策日、某状态，取该态的时效加权训练
标签（权重与 v1 相同，半衰期 756 天），计算加权正标签占比
``pos_label_frac = 该态加权正标签质量 / 该态加权样本量``（标签 1 的含
义与类别口径一致：A 类为“未来 6 个月收益为正”，B 类为“未来 12 个月内
最大回撤超 10%”），再取多数占比 ``majority_share = max(pos_frac,
1 - pos_frac)``。按权重而不是按标签计数——与预测器实际使用的证据一
致；年份不进入本轮计算（年份集中度是 v6 的问题，本轮只检验标签构成）。

门槛（事先固定）：``POLARITY_ONE_SIDED_SHARE = 0.9``。若多数占比
>= 0.9（即该态的时效加权训练标签里九成以上是同一边），该态算“标签一
边倒”，该日不用状态项、回退为时效加权基准率。取值理由事先写死：0.9
是“九成以上一边倒”的唯一对称分界，不是从测试集上挑的；边界语义为
“达到即触发”（>=），与 v6 门槛的方向一致。**尤其不得把门槛从 0.9 下
调去“刚好抓住”某个口袋——那是用测试集调参**；若 110022 A 的口袋在
0.9 下触发不足，结论就是“极性门槛修不掉这个口袋”，而不是调低门槛。

检验方式（事先固定）：门槛式回退（与 v4/v6 同构），不是限制训练样本
覆盖、不是按标签加权。理由：与 v4/v6 可比——v4 问“样本量够不够”，v6
问“样本够不够分散”，v7 问“标签够不够一边倒”；三种门槛的触发日集合
与效果可直接并排比较。

v7 只改预测器口径，不改评估口径：v7 = v2 回撤档位状态概率 + 标签极性
门槛（不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份集中度门槛
——本轮只检验标签极性这一个因素；与混合/样本量门槛/年份门槛的叠加是
下一轮的干净问题）。档位、两类标签、期限、测试起点、训练资格、比较
基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单仍用条目 9 的
``build_scorecard``，技能分数仍以 v0 基准率 Brier 为分母——v7 与
v0/v1/v2/v3/v4/v5/v6 的数字可直接并排比较。时效加权半衰期 756 天、收
缩伪计数 50 从 v1 继承、未改。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v7 在 110022 A 上缩小高估口袋（80%–100% 档的 n 或差值明显缩小）
  和/或在 110020 A 上修掉 2014 年案例，同时在 161725 A 上没有大幅丢
  掉优势，说明标签极性是问题的一部分——极性门槛值得保留为候选；
- 若 v7 在各组上约等于 v1（触发极少、或触发日与 v1 无差别），说明标
  签极性门槛没有增加超出 v1 的信息；
- 若 v7 比 v1 更差，说明一边倒的态恰恰有信息、门槛过激——这条路不
  成立；
- 2014 年案例单独报告：v7 是否让 110020 A 类 2014 年不再失效（当年
  Brier 是否低于基准率 Brier 0.419）。事先说明：按 v0 报告的诊断，2014
  年案例的 <5% 档训练标签几乎全为负，极性门槛按定义应触发；若实测未
  触发，须在报告中如实记录并修正这一诊断，不得事后改口径去“补救”；
- 近退化组（217022 A：实际 99.82% 为正）事先说明：该组标签本身就是一
  边倒的，门槛预计在多数决策日触发，v7 约等于加权基准率；Brier 差别
  全在千分位量级，不得把其中任何一个读作“预测变好了”。

实现上 v7 是 v2 的薄封装：``weighted_predict_at_v7`` 对 v2 的逐项直算
结果做门槛判断（标签极性另行直算），``generate_predictions_v7`` 对
v2 的递推结果逐项做同样的判断——标签极性由一趟与 v2 递推同构的并行
递推算出（每态的加权质量与加权正标签质量同步衰减、同步进入），两者
口径同一，测试守住逐点一致。本轮运行只用 ``"drawdown"`` 信号（问题
针对的是回撤档位状态项）；其余信号的门槛公式同样适用，但本轮不跑、
不下结论。v7 不需要日期输入（极性只用标签，不用年份）。

因果纪律与 v0/v1/v2/v3/v4/v5/v6 相同：决策日 t 的预测只用 t（含）之
前的数据；训练标签必须在 t 之前已完整观测；标签极性只用决策日当天的
训练集（已是 t 之前数据的加权统计），不引入任何未来信息。改动 t 之后
的净值，t 之前（含 t）的预测必须逐点不变（测试守住）。

本轮不做 v6 报告第 9 节开放问题 2（校准映射，须事先写死拟合窗口与更
新频率并单独报告映射本身的样本外表现）、开放问题 3（门槛叠加的解读规
则，须另起版本号）、开放问题 4（高事件发生率组的信号无力问题），三者
留待下一轮；也不做“按净值趋势划分牛熊段”的另一条行情定义，那是 v8
的干净问题。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v7 未达产品化门槛前不得以任何
形式在前端露出（条目 13）。
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.forecast_baseline import (
    HORIZON_A_DAYS,
    HORIZON_B_DAYS,
    TEST_START_INDEX,
    WINDOW_DAYS,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M, _weight
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNALS,
    PredictionV2,
    _states_for_signal,
    _training_starts,
    generate_predictions_v2,
    signal_state,
    weighted_predict_at_v2,
)

# 事先固定的门槛（见模块 docstring，不得运行时调参）。
# 某态时效加权训练标签里多数一边的占比达到九成及以上，即算“标签一边倒”：
# 0.9 是“九成以上”的唯一对称分界，不是从测试集上挑的。
POLARITY_ONE_SIDED_SHARE = 0.9


@dataclass
class PredictionV7:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发标签极性门槛（多数占比 >= 0.9）
    pos_label_frac: float  # 该态时效加权训练标签里标签 1 的占比（0.0–1.0）；无训练样本时为 0.0
    majority_share: float  # max(pos_label_frac, 1 - pos_label_frac)；无训练样本时为 0.0
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _polarity_stats(nav: list[float], decision: int, horizon: int, label_fn,
                    signal: str, window: int, half_life: float,
                    ) -> tuple[float, float, float]:
    """逐项直算某决策日、某状态的标签极性（参照实现）。

    返回 ``(正标签占比, 多数占比, 该态加权样本量)``。该态无训练样本时
    返回 ``(0.0, 0.0, 0.0)``——此时 v2 已回退为加权基准率，门槛不触发
    （没有状态项可不信任）。
    """
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return 0.0, 0.0, 0.0
    bucket_wn = 0.0
    bucket_ws = 0.0
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        if signal_state(nav, start, signal, window) != state:
            continue
        w = _weight(decision - start, half_life)
        bucket_wn += w
        bucket_ws += w * label
    if bucket_wn == 0:
        return 0.0, 0.0, 0.0
    pos_frac = bucket_ws / bucket_wn
    return pos_frac, max(pos_frac, 1.0 - pos_frac), bucket_wn


def _gate(pred: PredictionV2, pos_frac: float, majority_share: float,
          one_sided_share: float = POLARITY_ONE_SIDED_SHARE) -> PredictionV7:
    """把一条 v2 预测按标签极性门槛转成 v7 预测（只用当天的量）。"""
    gated = pred.bucket_weight_n > 0 and majority_share >= one_sided_share
    return PredictionV7(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        pos_label_frac=pos_frac,
        majority_share=majority_share,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v7(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           one_sided_share: float = POLARITY_ONE_SIDED_SHARE,
                           ) -> PredictionV7 | None:
    """单个决策日的 v7 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下门槛是恒等变换（该态即全部训练集，触发时状态概率
    本就等于加权基准率）。v7 不需要日期输入。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    pos_frac, majority_share, _ = _polarity_stats(
        nav, decision, horizon, label_fn, signal, window, half_life
    )
    return _gate(base, pos_frac, majority_share, one_sided_share)


def generate_predictions_v7(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            one_sided_share: float = POLARITY_ONE_SIDED_SHARE,
                            ) -> list[PredictionV7]:
    """滚动原点样本外 v7 预测（与 ``weighted_predict_at_v7`` 同口径）。

    标签极性由一趟与 v2 递推同构的并行递推算出：每态的加权质量与加权
    正标签质量每步同步衰减、恰好一个新训练起点进入（起点 = 决策日 − 期
    限），首个决策日直接逐项算出；``kind`` 为 ``"A"`` / ``"B"``，其余口
    径（期限、测试起点、训练资格）全部与 v2 一致。v7 不需要日期输入。
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

    def _compute_polarity(decision: int) -> dict[str, tuple[float, float]]:
        """直接逐项算出该决策日每态的（加权样本量，加权正标签质量）。"""
        out: dict[str, tuple[float, float]] = {s: (0.0, 0.0) for s in state_names}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None or states[start] is None:
                continue
            w = _weight(decision - start, half_life)
            s = states[start]
            wn, ws = out[s]
            out[s] = (wn + w, ws + w * label)
        return out

    def _stats_for(polarity: dict[str, tuple[float, float]], state: str | None):
        """从极性表取某态的（正标签占比，多数占比）。"""
        if state is None:
            return 0.0, 0.0
        wn, ws = polarity[state]
        if wn == 0:
            return 0.0, 0.0
        pos_frac = ws / wn
        return pos_frac, max(pos_frac, 1.0 - pos_frac)

    # 先算出全部决策日的标签极性，再与 v2 的递推输出按 index 对齐。
    stats: dict[int, tuple[float, float]] = {}
    polarity = _compute_polarity(first_decision)
    stats[first_decision] = _stats_for(polarity, states[first_decision])
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        for s in state_names:
            wn, ws = polarity[s]
            polarity[s] = (wn * decay, ws * decay)
        if (
            new_start >= window - 1
            and labels[new_start] is not None
            and states[new_start] is not None
        ):
            s = states[new_start]
            wn, ws = polarity[s]
            polarity[s] = (
                wn + new_weight,
                ws + new_weight * labels[new_start],
            )
        stats[decision] = _stats_for(polarity, states[decision])
    v2_preds = generate_predictions_v2(
        nav, kind, signal, window, test_start, half_life, shrinkage_m
    )
    return [
        _gate(pred, *stats[pred.index], one_sided_share)
        for pred in v2_preds
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "POLARITY_ONE_SIDED_SHARE",
    "PredictionV7",
    "generate_predictions_v7",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v7",
]
