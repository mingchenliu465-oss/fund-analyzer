"""概率预测实验 v13（离线实验，不进产品页面、不注册接口）。

条目 13 第十三轮：检验“门槛叠加”的另一方向——v10 的趋势段集中度
门槛与 v11 的多段一致性门槛取或（v12 报告第 9 节开放问题 1 指定的第
二种叠加；v11 报告第 9 节开放问题 1 的剩余部分）。

为什么是这条路：v12 合取的教训是“交集太小、继承弱侧的覆盖面”——
合取只触发 937/17372 天（5.4%），除近退化组外仅 94/15186 天（0.6%），
结果约等于 v1；2014 年案例与 110022 A 高估口袋一个也没修掉，原因
正是合取只覆盖两个门槛都认出的日子。本轮问的是反方向：**任一门槛
触发就回退，能不能把两处各自的斩获加起来**——v10 单独修掉了 2014
年案例（33/33 天触发）并抓住口袋的 34 天，v11 单独在 110020 B 上
是十二个候选里最好（−1.4%）；或叠加的触发集是两集合的并集，覆盖面
最大。但代价同样事先写明：**或叠加继承的是两个门槛错误的并集**——
v10 在 110020 B 的触发日上扔掉的是好信号（595/702 天状态本来更准，
十个候选里最差 −11.1%），v11 在 110022 B 与 161725 A 的触发日上扔
掉的也是好信号（v11 报告第 7.3 节：7 个非退化组里 5 组状态本来更
准）；或叠加会把这两处伤害都继承下来。本轮的干净问题是：并集的净
效应是正是负——而不是再换一种门槛定义或再调门槛值。

叠加定义（事先固定、写死在本模块中并在报告中披露，**不做参数扫描、
不按测试集调参**）：

    v13 状态概率 = 时效加权基准率，若该决策日触发 v10 门槛或 v11
    门槛中任一个（v10 主导段占比 >= REGIME_MAX_DOMINANT_SHARE = 0.5，
    或 v11 有证据段之间正标签占比极差 >= CONSISTENCY_MAX_RANGE = 0.5）；
    否则 = v2 状态概率（门槛前）。

    即 v13 = v2 回撤档位状态概率 + (v10 ∨ v11) 或门槛。两个门槛的
    定义、常数、边界语义（“达到即触发”）全部从 v10/v11 原样继承、
    未改；不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份门槛、
    不叠加 v7 绝对极性门槛、不叠加 v8 相对极性门槛、不叠加 v9 多年
    门槛——本轮只检验“或叠加”这一个因素。或（OR）不是合取（AND）：
    v12 已证明合取约等于 v1，本轮检验的是覆盖面最大的叠加方式；或
    叠加的触发日将是两集合的并集，按 v12 报告第 4 节的数字（2026-11-19
    截止）预计：161725 A 约 892 天（262 + 630 − 0）、161725 B 约 593
    天（440 + 153 − 0）、110020 A 约 1496 天（560 + 936 − 0）、110020
    B 约 1790 天（702 + 1088 − 0）、217022 A 约 2154 天（v11 的触发
    集完全包含在 v10 的触发集里，并集 = v10 的 2154 天）、217022 B
    约 2060 天（v10 全触发、v11 0 天）、110022 A 约 1896 天（484 +
    1456 − 44）、110022 B 约 1070 天（660 + 460 − 50），合计约
    11951/17372 天（68.8%）。新数据日只会让每组样本外数 +1，不改变
    并集的量级；若实测并集与上述数字出入超过每组 5 天，须先核查取数
    与对齐，不得直接读作结论。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v13 在各组上约等于 v1（技能差在 0.5 个百分点以内），说明或叠加
  没有增加超出 v1 的信息——在 68.8% 的决策日上回退为加权基准率，
  结果却与 v1 相同，只能说明这些日子上状态概率与加权基准率本就接
  近；须逐组核对触发日分解，不得把“约等于”读作“门槛没起作用”；
- 若 v13 在某组上比 v1 更好超过 1 个百分点且触发日分解显示并集日
  上回退确实更准，才算或叠加在该组上成立的唯一情形，须同时满足
  “更好”与“分解为证”两个条件，缺一个都只能写“证据不足”；只满
  足“更好”而不满足“分解为证”时，优先怀疑是并集里某一个门槛的
  单独贡献，不得宣称“或叠加机制对了”；
- 若 v13 在某组上比 v1 更差超过 1 个百分点，说明或叠加过激——它
  继承了两个门槛错误的并集，扔掉了更多本来是对的状态信号；尤其
  110020 B 与 110022 B 两组事先写明是高危组（v10 在前者上最差、
  v11 在后者上最差，或叠加在两组上都可能比两个单门槛更差）；
- 2014 年案例事先写明**预期修掉**：v12 报告的数字是 2014 年 33 个
  决策日 v10 触发 33/33、v11 触发 0/33，按或定义并集应为 33/33、
  v13 在该年应逐点等于 v10（Brier 0.378，不再失效）。这是或定义
  的确定性推论，不是发现；若实测如此，只能写“继承了 v10 的修复”，
  不得宣称或叠加“发现”了 2014 年的修法；若实测未修掉，须先核查
  代码与对齐，不得事后改定义；
- 110022 A 高估口袋事先写明**预期与 v10 相同**：v12 报告的数字是
  口袋 62 天 v10 触发 34 天、v11 触发 0 天，按或定义并集应为 34 天、
  口袋应从 n=62 缩到 n=28、最大校准差约 0.771，与 v10 逐项相同。
  这同样是或定义的确定性推论；若实测如此，只能写“继承了 v10 的
  34 天”，不得宣称或叠加“修掉”了口袋（剩下的 28 天仍严重高估）；
- 2015 年初 4 个极端日事先写明**预期一个也抓不住**：v10 与 v11 各
  自都是 0/4 天触发，按或定义并集应为 0 天，0%–20% 极端档 −0.818
  原样保留；若实测如此，不得事后放宽任一门槛去“刚好抓住”它们；
- B 类组事先说明：或门槛在 B 类上触发极宽（110020 B 预计 1790/2675
  天、66.9%；110022 B 预计 1070/2416 天、44.3%），v13 在 B 类上与
  v1 有实质差别是预期内的结果；若某 B 组实测比 v1 更差，触发日分
  解须逐项列出，不得只凭总技能下结论；
- 近退化组（217022 A）事先说明：v11 的触发集完全包含在 v10 的触
  发集里，或门槛在该组上应逐点等于 v10（2154 天触发），v13 约等于
  加权基准率；217022 B 上 v10 全触发、v11 0 天，或门槛同样全触发、
  v13 应逐点等于加权基准率；千分位差别不得读作改善；
- **触发日分解是本轮的必报口径**（v11 报告第 9 节开放问题 1 的要
  求、v12 报告第 7.3 节的延续）：报告必须列出 v13 并集日上“未加门
  槛的状态 Brier vs 回退 Brier”与“状态本来更准的天数占比”，并与
  v10/v11/v12 同口径的分解并排；叠加的触发日集合（每组 v10 触发天
  数、v11 触发天数、并集天数）须逐项列出，不得把两处伤害互相抵消
  了事；尤其不得从本轮实测的触发日 Brier 反推一个“刚好只在 110020
  B 上触发”的或定义。

v13 只改预测器口径，不改评估口径：档位、两类标签、期限、测试起点、
训练资格、比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩
单仍用条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier
为分母——v13 与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9/v10/v11/v12 的数字可
直接并排比较。时效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、未改。

实现上 v13 是 v2 的薄封装：``weighted_predict_at_v13`` 对 v2 的逐项
直算结果做或门槛判断（v10 的主导段占比与 v11 的段内占比极差另行
直算，分别复用 ``forecast_v10._segment_stats`` 与
``forecast_v11._segment_shares``）；``generate_predictions_v13`` 对
v10 与 v11 的递推结果按 index 对齐后逐项做同样的或判断（两者各自
的递推已在 v10/v11 的测试中守住与直算一致）——两者口径同一，测
试守住逐点一致。本轮运行只用 ``"drawdown"`` 信号（问题针对的是回
撤档位状态项）；其余信号的叠加公式同样适用，但本轮不跑、不下结论。

因果纪律与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9/v10/v11/v12 相同：决策日 t
的预测只用 t（含）之前的数据；训练标签必须在 t 之前已完整观测；两
个门槛的量只用决策日当天的训练集（已是 t 之前数据的加权统计），不引
入任何未来信息。改动 t 之后的净值，t 之前（含 t）的预测必须逐点不
变（测试守住）。

本轮不做 v12 报告第 9 节开放问题 2（触发日分解本身需要一个“门槛的
门槛”——只在状态信号历史上表现差的态上回退，须事先写死“历史表现”
的窗口与阈值并单独报告其样本外表现）、开放问题 3（段间不一致的“程
度”与“可测性”的更细定义）、开放问题 4（更宽松的多年定义，v9 报告
的数据窥探警告仍然有效）、开放问题 5（门槛的证据要求在历史早期与薄
态上量不到任何段）、开放问题 6（校准映射，须事先写死拟合窗口与更新
频率并单独报告映射本身的样本外表现）、开放问题 7（110020 B 与
110022 B 的反向教训），以及 v11 + v3/v5 混合——留待下一轮另起版本号。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v13 未达产品化门槛前不得以任何
形式在前端露出（条目 13）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.forecast_baseline import (
    HORIZON_A_DAYS,
    HORIZON_B_DAYS,
    TEST_START_INDEX,
    WINDOW_DAYS,
    label_drawdown_breach,
    label_positive_return,
)
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M
from experiments.forecast_v10 import (
    REGIME_MAX_DOMINANT_SHARE,
    UNDEFINED_SEGMENT,
    _segment_stats,
    generate_predictions_v10,
    trend_segment_ids,
)
from experiments.forecast_v11 import (
    CONSISTENCY_MAX_RANGE,
    MIN_SEGMENT_WEIGHT_N,
    _segment_shares,
    generate_predictions_v11,
)
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNALS,
    PredictionV2,
    generate_predictions_v2,
    weighted_predict_at_v2,
)


@dataclass
class PredictionV13:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 或门槛后状态概率：任一门槛触发时 = 加权基准率；否则 = v2 状态概率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发 v10 与 v11 中任一道门槛（或）
    gated_v10: bool  # 该日是否触发 v10 趋势段集中度门槛（主导段占比 >= 0.5）
    gated_v11: bool  # 该日是否触发 v11 多段一致性门槛（有证据段之间正标签占比极差 >= 0.5）
    dominant_segment_share: float  # v10 的主导段占比（0.0–1.0）；该态无训练样本时为 0.0
    dominant_segment: int | None  # v10 的主导段编号；该态无训练样本时为 None
    effective_segments: float  # v10 的有效段数；该态无训练样本时为 0.0
    consistency_range: float  # v11 的有证据段之间加权正标签占比极差；少于 2 个有证据段时为 0.0
    segment_shares: dict[int, float] = field(default_factory=dict)  # v11 的有证据段 -> 加权正标签占比
    n_evidence_segments: int = 0  # v11 的有证据段数；少于 2 个时门槛不触发
    decision_segment: int | None = None  # 决策日当天的趋势段编号；决策日趋势未定义时为 None
    outcome: int = 0
    train_n: int = 0
    bucket_train_n: int = 0
    state_fallback: bool = False  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float = 0.0  # 时效加权基准率
    weight_n: float = 0.0  # 训练集加权样本量（权重和）
    bucket_weight_n: float = 0.0  # 该态加权样本量


def _gate_either(pred: PredictionV2, share: float, dominant_segment: int | None,
                 effective_segments: float, consistency_range: float,
                 segment_shares: dict[int, float], n_evidence_segments: int,
                 decision_segment: int | None,
                 max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                 max_range: float = CONSISTENCY_MAX_RANGE) -> PredictionV13:
    """把一条 v2 预测按 v10 ∨ v11 或门槛转成 v13 预测（只用当天的量）。"""
    gated_v10 = pred.bucket_weight_n > 0 and share >= max_dominant_share
    gated_v11 = (
        pred.bucket_weight_n > 0
        and n_evidence_segments >= 2
        and consistency_range >= max_range
    )
    gated = gated_v10 or gated_v11
    return PredictionV13(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        gated_v10=gated_v10,
        gated_v11=gated_v11,
        dominant_segment_share=share,
        dominant_segment=dominant_segment,
        effective_segments=effective_segments,
        consistency_range=consistency_range,
        segment_shares=dict(segment_shares),
        n_evidence_segments=n_evidence_segments,
        decision_segment=decision_segment,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v13(nav: list[float], decision: int, horizon: int, label_fn,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                            max_range: float = CONSISTENCY_MAX_RANGE,
                            min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                            ) -> PredictionV13 | None:
    """单个决策日的 v13 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下或门槛是恒等变换（该态即全部训练集，触发时状态
    概率本就等于加权基准率）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    segments = trend_segment_ids(nav, window)
    share, dominant_segment, effective, _ = _segment_stats(
        nav, decision, horizon, label_fn, signal, window, half_life, segments
    )
    consistency_range, shares, n_evidence = _segment_shares(
        nav, decision, horizon, label_fn, signal, window, half_life, segments,
        min_segment_weight_n,
    )
    decision_segment = segments[decision]
    if decision_segment == UNDEFINED_SEGMENT:
        decision_segment = None
    return _gate_either(
        base, share, dominant_segment, effective, consistency_range, shares,
        n_evidence, decision_segment, max_dominant_share, max_range,
    )


def generate_predictions_v13(nav: list[float], kind: str,
                             signal: str = SIGNAL_DRAWDOWN,
                             window: int = WINDOW_DAYS,
                             test_start: int = TEST_START_INDEX,
                             half_life: float = HALF_LIFE_DAYS,
                             shrinkage_m: float = SHRINKAGE_M,
                             max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                             max_range: float = CONSISTENCY_MAX_RANGE,
                             min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                             ) -> list[PredictionV13]:
    """滚动原点样本外 v13 预测（与 ``weighted_predict_at_v13`` 同口径）。

    对 v10 与 v11 的递推结果按 index 对齐后逐项做或判断；``kind`` 为
    ``"A"`` / ``"B"``，其余口径（期限、测试起点、训练资格）全部与 v2
    一致。两路递推的对齐由 index 与 bucket 守住，不一致时直接报错，
    不静默拼合。
    """
    if kind == "A":
        horizon, label_fn = HORIZON_A_DAYS, label_positive_return
    elif kind == "B":
        horizon, label_fn = HORIZON_B_DAYS, label_drawdown_breach
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    v10_preds = generate_predictions_v10(
        nav, kind, signal, window, test_start, half_life, shrinkage_m,
        max_dominant_share,
    )
    v11_preds = generate_predictions_v11(
        nav, kind, signal, window, test_start, half_life, shrinkage_m,
        max_range, min_segment_weight_n,
    )
    if len(v10_preds) != len(v11_preds):
        raise ValueError(
            f"v10/v11 prediction counts differ: {len(v10_preds)} vs {len(v11_preds)}"
        )
    out: list[PredictionV13] = []
    for p10, p11 in zip(v10_preds, v11_preds):
        if p10.index != p11.index or p10.bucket != p11.bucket:
            raise ValueError(
                f"v10/v11 predictions misaligned at {p10.index}/{p11.index}"
            )
        if p10.ungated_state_prob != p11.ungated_state_prob:
            raise ValueError(
                f"v10/v11 ungated state prob differs at index {p10.index}"
            )
        gated = p10.gated or p11.gated
        out.append(
            PredictionV13(
                index=p10.index,
                bucket=p10.bucket,
                signal=p10.signal,
                baseline_prob=p10.baseline_prob,
                state_prob=p10.baseline_weighted if gated else p10.ungated_state_prob,
                ungated_state_prob=p10.ungated_state_prob,
                gated=gated,
                gated_v10=p10.gated,
                gated_v11=p11.gated,
                dominant_segment_share=p10.dominant_segment_share,
                dominant_segment=p10.dominant_segment,
                effective_segments=p10.effective_segments,
                consistency_range=p11.consistency_range,
                segment_shares=dict(p11.segment_shares),
                n_evidence_segments=p11.n_evidence_segments,
                decision_segment=p10.decision_segment,
                outcome=p10.outcome,
                train_n=p10.train_n,
                bucket_train_n=p10.bucket_train_n,
                state_fallback=p10.state_fallback,
                baseline_weighted=p10.baseline_weighted,
                weight_n=p10.weight_n,
                bucket_weight_n=p10.bucket_weight_n,
            )
        )
    return out


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "CONSISTENCY_MAX_RANGE",
    "MIN_SEGMENT_WEIGHT_N",
    "REGIME_MAX_DOMINANT_SHARE",
    "PredictionV13",
    "generate_predictions_v13",
    "label_drawdown_breach",
    "label_positive_return",
    "trend_segment_ids",
    "weighted_predict_at_v13",
]
