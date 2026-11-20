"""概率预测实验 v12（离线实验，不进产品页面、不注册接口）。

条目 13 第十二轮：检验“门槛叠加”——v10 的趋势段集中度门槛与 v11
的多段一致性门槛合取（v11 报告第 9 节开放问题 1 指定的第一种叠加；
v10 报告第 9 节开放问题 1 的剩余部分）。

为什么是这条路：v11 的证据表明，门槛成败的决定量不是“触发了多少
天”，而是“触发日上状态信号本来比回退准还是差”——v11 在 110020 B
上扔掉的是差信号（立功，十一个候选里最好 −1.4%），在 110022 B 上扔
掉的是好信号（犯错，十一个候选里最差 −7.3%）；v10 在 110020 B 上扔
掉的是好信号（犯错，十个候选里最差 −11.1%）。而两种门槛的触发日几
乎不重叠（110020 B 交集 0 天、161725 A 交集 0 天、110022 A 交集只有
44 天）——“证据集中在一段里”与“各段标签构成不一致”在真实数据上
几乎是正交的两种警告。本轮问的是：**要求两种警告同时成立才回退，
能不能把两处伤害互相抵消、只留下共同认出的坏日子**——而不是再换
一种门槛定义或再调门槛值。

叠加定义（事先固定、写死在本模块中并在报告中披露，**不做参数扫描、
不按测试集调参**）：

    v12 状态概率 = 时效加权基准率，若该决策日同时触发 v10 门槛与
    v11 门槛（v10 主导段占比 >= REGIME_MAX_DOMINANT_SHARE = 0.5，
    且 v11 有证据段之间正标签占比极差 >= CONSISTENCY_MAX_RANGE = 0.5）；
    否则 = v2 状态概率（门槛前）。

    即 v12 = v2 回撤档位状态概率 + (v10 ∧ v11) 合取门槛。两个门槛的
    定义、常数、边界语义（“达到即触发”）全部从 v10/v11 原样继承、
    未改；不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份门槛、
    不叠加 v7 绝对极性门槛、不叠加 v8 相对极性门槛、不叠加 v9 多年
    门槛——本轮只检验“合取叠加”这一个因素。合取（AND）不是或（OR）：
    选合取的理由事先写死——v10 与 v11 各自的触发日集合都已证明会扔
    掉本来是对的状态信号（v11 报告第 7.3 节触发日分解：7 个非退化组
    里 5 组状态本来更准），放宽为或只会扔掉更多；合取是最保守的叠加
    方式，只在两种警告一致时才回退。或叠加（v10 ∨ v11）是另一轮的
    干净问题，本轮不做、不预判。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v12 在各组上约等于 v1（技能差在 0.5 个百分点以内、触发日约等
  于 v11 报告预测的交集：110020 B 与 161725 A 上 0 天、110022 A 上
  约 44 天），说明合取叠加没有增加超出 v1 的信息——两种门槛认出的
  “不可信的日子”几乎没有交集，要求两者一致等于几乎不回退；叠加
  不能把两处伤害互相抵消了事，合取这条路不成立；
- 若 v12 只在 110022 A 上与 v1 有实质差别（该组交集约 44 天），口
  袋与 2014 年案例单独报告；n=44 太小，不得据此宣称“机制对了”——
  交集日本身的触发日分解（状态 Brier vs 回退 Brier）才是判断依据；
- 若 v12 在某组上比 v1 更差超过 1 个百分点，说明即使两种警告一致
  的日子，状态信号本来仍可能是对的——合取门槛同样过激；
- 若 v12 在某组上比 v1 更好超过 1 个百分点且触发日分解显示交集日
  上回退确实更准，说明交集认出的是真正坏信号的日子——这是合取叠
  加成立的唯一情形，须同时满足“更好”与“分解为证”两个条件，缺一
  个都只能写“证据不足”；
- 2014 年案例单独报告：事先写明不预判——v11 报告的数字是 2014 年
  33 个决策日 v10 全部触发、v11 全部未触发（有证据的段数为 0），按
  定义合取应为 0 天触发、v12 应逐点等于 v1；若实测如此，合取叠加修
  不掉 2014 年案例，不得事后把任一门槛放宽去“刚好抓住”它；
- 110022 A 高估口袋单独报告：事先写明不预判——v11 报告的数字是口
  袋 62 天 v10 触发 34 天、v11 触发 0 天，按定义合取应为 0 天触发、
  口袋原样保留；若实测如此，合取叠加抓不住口袋，不得事后把任一门
  槛放宽去“刚好抓住”它；
- B 类组事先说明：合取门槛预计在 B 类上触发极少（v11 报告：110020
  B 交集 0 天），v12 在 B 类上约等于 v1 是预期内的结果，不是“门槛
  失灵”的新证据；若某 B 组实测触发较多且比 v1 更差，触发日分解须
  逐项列出，不得只凭总技能下结论；
- 近退化组（217022 A）事先说明：v10 在该组上触发 2152/2184 天、
  v11 触发 843/2185 天，两者交集有多大由数据决定；v12 约等于 v1
  或约等于加权基准率都可能，千分位差别不得读作改善；
- **触发日分解是本轮的必报口径**（v11 报告第 9 节开放问题 1 的要
  求）：报告必须列出 v12 触发日上“未加门槛的状态 Brier vs 回退
  Brier”与“状态本来更准的天数占比”，并与 v10/v11 同口径的分解并
  排；叠加的触发日集合（每组 v10 触发天数、v11 触发天数、交集天数）
  须逐项列出，不得把两处伤害互相抵消了事；尤其不得从本轮实测的触
  发日 Brier 反推一个“刚好只在 110020 B 上触发”的叠加定义。

v12 只改预测器口径，不改评估口径：档位、两类标签、期限、测试起点、
训练资格、比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩
单仍用条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier
为分母——v12 与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9/v10/v11 的数字可直接
并排比较。时效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、未改。

实现上 v12 是 v2 的薄封装：``weighted_predict_at_v12`` 对 v2 的逐项
直算结果做合取门槛判断（v10 的主导段占比与 v11 的段内占比极差另行
直算，分别复用 ``forecast_v10._segment_stats`` 与
``forecast_v11._segment_shares``）；``generate_predictions_v12`` 对
v10 与 v11 的递推结果按 index 对齐后逐项做同样的合取判断（两者各
自的递推已在 v10/v11 的测试中守住与直算一致）——两者口径同一，测
试守住逐点一致。本轮运行只用 ``"drawdown"`` 信号（问题针对的是回
撤档位状态项）；其余信号的叠加公式同样适用，但本轮不跑、不下结论。

因果纪律与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9/v10/v11 相同：决策日 t 的
预测只用 t（含）之前的数据；训练标签必须在 t 之前已完整观测；两个
门槛的量只用决策日当天的训练集（已是 t 之前数据的加权统计），不引
入任何未来信息。改动 t 之后的净值，t 之前（含 t）的预测必须逐点不
变（测试守住）。

本轮不做 v11 报告第 9 节开放问题 2（段间不一致的“程度”与“可测性”
的更细定义——加权极差、有效段数加权、分段质量门槛放宽，须事先写死
定义与门槛并给出独立于测试集的事前依据）、开放问题 3（更宽松的多
年定义，v9 报告的数据窥探警告仍然有效）、开放问题 4（门槛的证据要
求在历史早期与薄态上量不到任何段）、开放问题 5（校准映射，须事先
写死拟合窗口与更新频率并单独报告映射本身的样本外表现）、开放问题
6（110020 B 与 110022 B 的反向教训），以及或叠加（v10 ∨ v11）与
v11 + v3/v5 混合——三者留待下一轮另起版本号。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v12 未达产品化门槛前不得以任何
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
class PredictionV12:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 合取门槛后状态概率：双门槛同时触发时 = 加权基准率；否则 = v2 状态概率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否同时触发 v10 与 v11 两道门槛（合取）
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


def _gate_both(pred: PredictionV2, share: float, dominant_segment: int | None,
               effective_segments: float, consistency_range: float,
               segment_shares: dict[int, float], n_evidence_segments: int,
               decision_segment: int | None,
               max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
               max_range: float = CONSISTENCY_MAX_RANGE) -> PredictionV12:
    """把一条 v2 预测按 v10 ∧ v11 合取门槛转成 v12 预测（只用当天的量）。"""
    gated_v10 = pred.bucket_weight_n > 0 and share >= max_dominant_share
    gated_v11 = (
        pred.bucket_weight_n > 0
        and n_evidence_segments >= 2
        and consistency_range >= max_range
    )
    gated = gated_v10 and gated_v11
    return PredictionV12(
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


def weighted_predict_at_v12(nav: list[float], decision: int, horizon: int, label_fn,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                            max_range: float = CONSISTENCY_MAX_RANGE,
                            min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                            ) -> PredictionV12 | None:
    """单个决策日的 v12 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下合取门槛是恒等变换（该态即全部训练集，触发时状态
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
    return _gate_both(
        base, share, dominant_segment, effective, consistency_range, shares,
        n_evidence, decision_segment, max_dominant_share, max_range,
    )


def generate_predictions_v12(nav: list[float], kind: str,
                             signal: str = SIGNAL_DRAWDOWN,
                             window: int = WINDOW_DAYS,
                             test_start: int = TEST_START_INDEX,
                             half_life: float = HALF_LIFE_DAYS,
                             shrinkage_m: float = SHRINKAGE_M,
                             max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                             max_range: float = CONSISTENCY_MAX_RANGE,
                             min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                             ) -> list[PredictionV12]:
    """滚动原点样本外 v12 预测（与 ``weighted_predict_at_v12`` 同口径）。

    对 v10 与 v11 的递推结果按 index 对齐后逐项做合取判断；``kind`` 为
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
    out: list[PredictionV12] = []
    for p10, p11 in zip(v10_preds, v11_preds):
        if p10.index != p11.index or p10.bucket != p11.bucket:
            raise ValueError(
                f"v10/v11 predictions misaligned at {p10.index}/{p11.index}"
            )
        if p10.ungated_state_prob != p11.ungated_state_prob:
            raise ValueError(
                f"v10/v11 ungated state prob differs at index {p10.index}"
            )
        gated = p10.gated and p11.gated
        out.append(
            PredictionV12(
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
    "PredictionV12",
    "generate_predictions_v12",
    "label_drawdown_breach",
    "label_positive_return",
    "trend_segment_ids",
    "weighted_predict_at_v12",
]
