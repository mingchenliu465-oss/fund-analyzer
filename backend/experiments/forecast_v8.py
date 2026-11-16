"""概率预测实验 v8（离线实验，不进产品页面、不注册接口）。

条目 13 第八轮：检验“标签极性的相对化”（v7 报告第 9 节开放问题 1）。
v7 的绝对极性门槛（多数占比 >= 0.9）触发了 36.1% 的决策日，远宽于
v4 的 1.0% 与 v6 的 8.0%——不是因为“到处都是单一行情”，而是因为事
件本身高频时标签一边倒是常态：B 类事件发生率 79%–87%，217022 A 为正
率 99.82%，这些组里多数态的训练标签天然就是九成以上一边倒。绝对极性
量的是“标签一边倒”，量不到“标签一边倒是不是因为单一行情”。本轮问
的是：**把极性相对化——某态的标签构成与全局构成差得足够远时才不信任
状态项——能不能分开“事件本身高频”与“单一行情扭曲”**。

“相对极性”的定义（事先固定、写死在本模块中并在报告中披露，**不做参
数扫描、不按测试集调参**）：对某决策日、某状态，取该态的时效加权训练
标签正占比 ``pos_label_frac``（与 v7 同口径：该态加权正标签质量 / 该
态加权样本量；权重与 v1 相同，半衰期 756 天；标签 1 的含义与类别口径一
致：A 类为“未来 6 个月收益为正”，B 类为“未来 12 个月内最大回撤超
10%”），再取同一天的时效加权基准率 ``baseline_weighted``（v2 已算出
的全局加权正标签占比，同一权重、同一训练集），定义相对差距
``gap = |pos_label_frac - baseline_weighted|``。全局构成就是“只看事
件发生频率时你会预期的标签构成”——某态的标签构成与它差得越远，该态
的证据就越“出格”。

门槛（事先固定）：``RELATIVE_POLARITY_GAP = 0.5``。若 gap >= 0.5（即
该态的标签构成与全局构成相差至少半个概率尺度），该日不用状态项、回退
为时效加权基准率。取值理由事先写死：0.5 是 [0, 1] 概率尺度的中点，
是“差半个尺度”的唯一对称分界，与 v6 的 0.5（“过半”）同族，不是从测
试集上挑的；边界语义为“达到即触发”（>=），与 v6/v7 门槛的方向一致。
**尤其不得事后下调门槛**：v7 报告已写明 110022 A 高估口袋 62 天的正标
签占比为 0.805–0.848、加权基准率约 0.55–0.64，相对差距约 0.2–0.3，
在 0.5 之下——若实测口袋一天也没触发，结论就是“半个尺度的相对极性
修不掉这个口袋”，而不是把门槛改成 0.25 去“刚好抓住”它；那是用测试
集调参。同样，2014 年案例与 2015 年初 4 个极端日的相对差距约
0.35–0.45（按 v7 报告的数字估算），也在 0.5 之下——本轮不预判它们是
否触发，实测如何就如实报告；若 v8 约等于 v1，结论就是“半个尺度的相
对极性没有增加超出 v1 的信息”，下一轮换更松的相对定义须另起版本号并
给出独立于测试集的事前依据，不得在 v8 下悄悄改数。

检验方式（事先固定）：门槛式回退（与 v4/v6/v7 同构），不是限制训练样
本覆盖、不是按标签加权。理由：与 v4/v6/v7 可比——v4 问“样本量够不够”，
v6 问“样本够不够分散”，v7 问“标签够不够一边倒”，v8 问“标签构成与全
局差得够不够远”；四种门槛的触发日集合与效果可直接并排比较。

v8 只改预测器口径，不改评估口径：v8 = v2 回撤档位状态概率 + 相对极性
门槛（不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份集中度门槛、
不叠加 v7 绝对极性门槛——本轮只检验相对极性这一个因素；与混合/样本
量门槛/年份门槛/绝对极性门槛的叠加是下一轮的干净问题）。档位、两类标
签、期限、测试起点、训练资格、比较基准（v0 无加权历史基准率）全部与条
目 8/9 一致；成绩单仍用条目 9 的 ``build_scorecard``，技能分数仍以
v0 基准率 Brier 为分母——v8 与 v0/v1/v2/v3/v4/v5/v6/v7 的数字可直接并
排比较。时效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、未改。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v8 在 B 类高事件率组（161725 B、110020 B）上不再犯 v7 的错（技
  能不再比 v1 更差），同时在 110020 A 上修掉 2014 年案例和/或 2015 年
  初极端日，说明相对极性分得开“事件高频”与“行情扭曲”——相对极性
  值得保留为候选；
- 若 v8 在各组上约等于 v1（触发极少、或触发日与 v1 无差别），说明半
  个尺度的相对极性没有增加超出 v1 的信息——这条路在该严格度下不成
  立，结论不是“调松门槛再试”，而是“须另起版本号并给出新的事前依据”；
- 若 v8 比 v1 更差，说明相对极性门槛同样过激——这条路不成立；
- 2014 年案例单独报告：v8 是否让 110020 A 类 2014 年不再失效（当年
  Brier 是否低于基准率 Brier 0.419）。事先说明：按 v7 报告的数字估算，
  该年 <5% 态的相对差距约 0.35–0.45，在 0.5 之下，门槛按定义可能不触
  发；实测触发与否都如实记录，不得事后改口径去“补救”；
- 近退化组（217022 A：实际 99.82% 为正；217022 B：事件从未发生）事先
  说明：该组态内正占比与全局加权基准率都约等于 1（A 类）或 0（B 类），
  相对差距约等于 0，门槛预计几乎不触发，v8 约等于 v1；Brier 差别全在
  千分位量级，不得把其中任何一个读作“预测变好了”。

实现上 v8 是 v2 的薄封装：``weighted_predict_at_v8`` 对 v2 的逐项直算
结果做门槛判断（相对差距另行直算），``generate_predictions_v8`` 对
v2 的递推结果逐项做同样的判断——态内正标签占比由一趟与 v2/v7 递推同
构的并行递推算出（每态的加权质量与加权正标签质量同步衰减、同步进入），
全局加权基准率直接取 v2 递推输出的 ``baseline_weighted``，两者口径同
一，测试守住逐点一致。本轮运行只用 ``"drawdown"`` 信号（问题针对的
是回撤档位状态项）；其余信号的门槛公式同样适用，但本轮不跑、不下结
论。v8 不需要日期输入（相对极性只用标签与全局构成，不用年份）。

因果纪律与 v0/v1/v2/v3/v4/v5/v6/v7 相同：决策日 t 的预测只用 t（含）
之前的数据；训练标签必须在 t 之前已完整观测；相对极性只用决策日当天
的训练集（已是 t 之前数据的加权统计），不引入任何未来信息。改动 t 之
后的净值，t 之前（含 t）的预测必须逐点不变（测试守住）。

本轮不做 v7 报告第 9 节开放问题 2（口袋的真实构成是“八成以上一边倒、
且持续多年”——“多年一边倒”须事先写死“多年”的窗口与计数方式；“按
净值趋势划分牛熊段”的另一条行情定义仍未检验）、开放问题 3（校准映
射，须事先写死拟合窗口与更新频率并单独报告映射本身的样本外表现）、
开放问题 4（门槛叠加的解读规则，须另起版本号；叠加之前须先回答“为什
么 B 类上门槛总犯错”）、开放问题 5（高事件发生率组的信号无力问题），
四者留待下一轮。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v8 未达产品化门槛前不得以任何
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
# 某态时效加权训练标签的正占比与全局时效加权基准率之差达到半个概率
# 尺度及以上，即算“该态的标签构成与全局差得足够远”：0.5 是 [0, 1]
# 尺度的中点，是“差半个尺度”的唯一对称分界，不是从测试集上挑的。
RELATIVE_POLARITY_GAP = 0.5


@dataclass
class PredictionV8:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发相对极性门槛（相对差距 >= 0.5）
    pos_label_frac: float  # 该态时效加权训练标签里标签 1 的占比（0.0–1.0）；无训练样本时为 0.0
    gap: float  # |pos_label_frac - baseline_weighted|；无训练样本时为 0.0
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率（全局构成）
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _state_pos_frac(nav: list[float], decision: int, horizon: int, label_fn,
                    signal: str, window: int, half_life: float,
                    ) -> tuple[float, float]:
    """逐项直算某决策日、某状态的时效加权正标签占比（参照实现）。

    返回 ``(正标签占比, 该态加权样本量)``。该态无训练样本时返回
    ``(0.0, 0.0)``——此时 v2 已回退为加权基准率，门槛不触发（没有状态
    项可不信任）。
    """
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return 0.0, 0.0
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
        return 0.0, 0.0
    return bucket_ws / bucket_wn, bucket_wn


def _gate(pred: PredictionV2, pos_frac: float,
          gap_threshold: float = RELATIVE_POLARITY_GAP) -> PredictionV8:
    """把一条 v2 预测按相对极性门槛转成 v8 预测（只用当天的量）。"""
    gap = abs(pos_frac - pred.baseline_weighted) if pred.bucket_weight_n > 0 else 0.0
    gated = pred.bucket_weight_n > 0 and gap >= gap_threshold
    return PredictionV8(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        pos_label_frac=pos_frac,
        gap=gap,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v8(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           gap_threshold: float = RELATIVE_POLARITY_GAP,
                           ) -> PredictionV8 | None:
    """单个决策日的 v8 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下门槛是恒等变换（该态即全部训练集，态内正占比恒等
    于加权基准率，相对差距恒为 0）。v8 不需要日期输入。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    pos_frac, _ = _state_pos_frac(
        nav, decision, horizon, label_fn, signal, window, half_life
    )
    return _gate(base, pos_frac, gap_threshold)


def generate_predictions_v8(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            gap_threshold: float = RELATIVE_POLARITY_GAP,
                            ) -> list[PredictionV8]:
    """滚动原点样本外 v8 预测（与 ``weighted_predict_at_v8`` 同口径）。

    态内正标签占比由一趟与 v2 递推同构的并行递推算出：每态的加权质量与
    加权正标签质量每步同步衰减、恰好一个新训练起点进入（起点 = 决策日
    − 期限），首个决策日直接逐项算出；全局加权基准率直接取 v2 递推输出
    的 ``baseline_weighted``；``kind`` 为 ``"A"`` / ``"B"``，其余口径
    （期限、测试起点、训练资格）全部与 v2 一致。v8 不需要日期输入。
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

    def _compute_state_sums(decision: int) -> dict[str, tuple[float, float]]:
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

    def _pos_frac_for(sums: dict[str, tuple[float, float]], state: str | None):
        """从态求和表取某态的时效加权正标签占比（无样本时为 0.0）。"""
        if state is None:
            return 0.0
        wn, ws = sums[state]
        if wn == 0:
            return 0.0
        return ws / wn

    # 先算出全部决策日的态内正标签占比，再与 v2 的递推输出按 index 对齐。
    pos_fracs: dict[int, float] = {}
    sums = _compute_state_sums(first_decision)
    pos_fracs[first_decision] = _pos_frac_for(sums, states[first_decision])
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        for s in state_names:
            wn, ws = sums[s]
            sums[s] = (wn * decay, ws * decay)
        if (
            new_start >= window - 1
            and labels[new_start] is not None
            and states[new_start] is not None
        ):
            s = states[new_start]
            wn, ws = sums[s]
            sums[s] = (
                wn + new_weight,
                ws + new_weight * labels[new_start],
            )
        pos_fracs[decision] = _pos_frac_for(sums, states[decision])
    v2_preds = generate_predictions_v2(
        nav, kind, signal, window, test_start, half_life, shrinkage_m
    )
    return [
        _gate(pred, pos_fracs[pred.index], gap_threshold)
        for pred in v2_preds
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "RELATIVE_POLARITY_GAP",
    "PredictionV8",
    "generate_predictions_v8",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v8",
]
