"""概率预测实验 v11（离线实验，不进产品页面、不注册接口）。

条目 13 第十一轮：检验“多段一致性”——证据分散在多个趋势段里时，
各段的态内正标签占比是否同向（v10 报告第 9 节开放问题 2；v6 报告
第 9 节开放问题 1、v8 报告第 9 节开放问题 2 之后仍未检验的另一条路）。

为什么是这条路：v10 的两个已知口袋共同指向同一个未解问题——口袋
晚期 28 天（主导段占比 0.389–0.418）与 2015 年初 4 个极端日（主导
段占比 0.27–0.28）的训练证据都分散在多段里，v10 的定义只量“一段占
多少”，量不到“多段之间标签构成是否一致”。本轮检验的正是后者。

定义（事先固定、写死在本模块中并在报告中披露，**不做参数扫描、不按
测试集调参**）：
- “趋势段”复用 v10 已注册的定义——累计净值与近 250 日简单均线的
  关系（``"above"`` / ``"below"``，窗口取 ``WINDOW_DAYS``），一段行情
  = 趋势状态连续相同的一段交易日（最大连续 run）；每个训练标签归属
  其训练起点所在的那一段。段的边界、滞后性等局限与 v10 相同，不另述。
- 段内正标签占比（事先固定）：对某决策日、某状态，取该态的时效加权
  训练标签（权重与 v1 相同，半衰期 756 天），按起点所在的趋势段分组，
  每段的加权正标签占比 = 该段内 Σ(权重 × 标签) / Σ权重。占比量的是
  “该段里的证据说什么”，与 v10 的主导段占比（“证据从哪来”）是两个
  不同的量——本轮的门槛不是从 v10 实测的主导段占比（0.389–0.418、
  0.27–0.28）反推的：那些是质量占比，本轮量的是段内标签占比之差，
  定义与数值来源都不同。
- 有证据的段（事先固定）：某段算“有证据”当且仅当该段的加权样本量
  （权重和）>= ``MIN_SEGMENT_WEIGHT_N = 30.0``。取值理由事先写死：
  借用 v4 样本量门槛 ``GATE_MIN_WEIGHT_N = 30.0`` 的已有证据标准——
  同一个“30 个加权样本才算证据”的尺度，只是从“全态”移到“每段”，
  不是从测试集上挑的；质量不足 30 的段不进入一致性计算，防止一段
  只有一两个标签的噪声段凭一个极端占比触发门槛。
- 一致性度量（事先固定）：有证据的段不少于 2 个时，一致性极差 =
  各段加权正标签占比的最大值 − 最小值；少于 2 个有证据的段时极差记
  为 0.0（量不到“段与段不一致”，门槛不触发）。极差不依赖段数多少，
  只问“最乐观的段与最悲观的段差多远”。
- 门槛（事先固定）：``CONSISTENCY_MAX_RANGE = 0.5``。若某态有证据
  的段之间正标签占比极差 >= 0.5，该态算“段间不一致”，该日不用状态
  项、回退为时效加权基准率。取值理由事先写死：0.5 是概率尺度的一半、
  唯一对称分界，与 v8 的相对极性门槛取同一值、同一理由——两段的标
  签占比差半个尺度，意味着一段说“大概率发生”、另一段说“大概率不
  发生”，证据在方向上自相矛盾；不是从测试集上挑的；边界语义为“达
  到即触发”（>=），与 v6/v7/v8/v9/v10 门槛的方向一致。

检验方式（事先固定）：门槛式回退（与 v4/v6/v7/v8/v9/v10 同构），不
是限制训练样本覆盖、不是按段加权。理由：与 v10 可比——v10 问“样本
够不够集中在一段里”，v11 问“各段的标签构成是否一致”；两种门槛的
触发日集合与效果可直接并排比较。

v11 只改预测器口径，不改评估口径：v11 = v2 回撤档位状态概率 + 多段
一致性门槛（不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份门
槛、不叠加 v7 绝对极性门槛、不叠加 v8 相对极性门槛、不叠加 v9 多年
门槛、不叠加 v10 趋势段集中度门槛——本轮只检验多段一致性这一个因
素；与混合/样本量门槛/年份门槛/极性门槛/多年门槛/集中度门槛的叠加
是下一轮的干净问题）。档位、两类标签、期限、测试起点、训练资格、
比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单仍用条目
9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier 为分母——
v11 与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9/v10 的数字可直接并排比较。时
效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、未改。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v11 缩小 110022 A 高估口袋（80%–100% 校准档差值明显缩小）和/
  或修掉 2015 年初 4 个极端日所在的低估档、和/或让 110020 A 类 2014
  年不再失效，同时在 161725 A 上没有大幅丢掉优势，说明多段一致性
  是问题的一部分——多段一致性门槛值得保留为候选；
- 若 v11 在各组上约等于 v1（触发极少、或触发日与 v1 无差别），说明
  多段一致性门槛没有增加超出 v1 的信息；
- 若 v11 比 v1 更差，说明段间不一致的态恰恰有信息、门槛过激——这
  条路不成立；
- 2014 年案例单独报告：v11 是否让 110020 A 类 2014 年不再失效（当
  年 Brier 是否低于基准率 Brier）。事先写明不预判：2014 年案例的
  <5% 档训练标签全来自 2009–2010 两年，这两年在净值趋势上是几段、
  各段的正标签占比是否差到半个尺度，由数据决定；若修不掉，那正是
  “多段一致性”与“样本量/年份/极性/集中度”几种门槛覆盖情形不同的
  证据；
- 110022 A 高估口袋单独报告：事先写明不预判——口袋 62 天的训练标
  签分属哪几段、各段的正标签占比极差是否达到 0.5，由数据决定；若口
  袋 0 天触发，不得事后把段的定义（如窗口、均线类型）或极差门槛改
  成“刚好抓住”它；尤其不得从 v10 实测的占比（0.389–0.418）反推一
  个“刚好触发晚期口袋”的定义——那是质量占比，不是标签占比；
- B 类组事先说明（v10 报告第 9 节开放问题 1 的可检验版本）：事件本
  身高频时，各段的正标签占比天然都高，段间极差天然小，门槛预计在
  B 类上很少触发、很少扔掉本来是对的状态信号——若实测如此，这是
  “为什么 B 类上门槛总犯错”的一块拼图：v4/v6/v7/v9/v10 的门槛量
  的是样本量、年份、极性、集中度，这些量在事件高频组里天然偏大；
  而段间一致性量的是“各段是否同向”，在事件高频组里天然不触发。
  反之，若 v11 在 B 类上同样大面积触发且比 v1 更差，说明这个解释
  是错的，B 类问题另有原因；报告须用触发日分解（触发日上状态信号
  本来对不对）作证，不得只凭总技能下结论；
- 近退化组（217022 A）事先说明：各段正标签占比都接近 1.0，极差接
  近 0，门槛预计几乎不触发、v11 约等于 v1（与 v10 在该组上触发
  2152/2184 天不同），千分位差别不得读作改善。

实现上 v11 是 v2 的薄封装：``weighted_predict_at_v11`` 对 v2 的逐项
直算结果做门槛判断（段内占比另行直算），``generate_predictions_v11``
对 v2 的递推结果逐项做同样的判断——段内占比由一趟与 v2 递推同构的
并行递推算出（每态、每段的加权质量与加权正标签质量同步衰减、同步
进入），两者口径同一，测试守住逐点一致。本轮运行只用 ``"drawdown"``
信号（问题针对的是回撤档位状态项）；其余信号的门槛公式同样适用，
但本轮不跑、不下结论。

段归属只用训练起点（含）之前的数据：某日所属的趋势段由该日（含）
之前的趋势状态序列决定（run 的起点在过去；run 的终点在未来不影响
该日的段归属——段编号按 run 出现顺序递增，只依赖起点及之前的状
态）。因果纪律与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9/v10 相同：决策日 t
的预测只用 t（含）之前的数据；训练标签必须在 t 之前已完整观测；段
内占比只用决策日当天的训练集（已是 t 之前数据的加权统计），不引入
任何未来信息。改动 t 之后的净值，t 之前（含 t）的预测必须逐点不变
（测试守住）。

本轮不做 v10 报告第 9 节开放问题 3（更宽松的多年定义，v9 报告的数
据窥探警告仍然有效）、开放问题 4（门槛的证据要求改按加权质量——本
轮借用的 30.0 已是加权质量口径，但“一年证据”的定义未动）、开放问
题 5（校准映射，须事先写死拟合窗口与更新频率并单独报告映射本身的
样本外表现）、开放问题 6（B 类高事件发生率组信号分不出什么——本轮
的 B 类诊断是其中一块拼图，不是全部答案），以及门槛叠加（须另起版
本号并事先写死解读规则）。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v11 未达产品化门槛前不得以任何
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
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M, _weight
from experiments.forecast_v10 import UNDEFINED_SEGMENT, trend_segment_ids
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNALS,
    PredictionV2,
    _training_starts,
    generate_predictions_v2,
    signal_state,
    weighted_predict_at_v2,
)
from experiments.forecast_v4 import GATE_MIN_WEIGHT_N

# 事先固定的门槛（见模块 docstring，不得运行时调参）。
# 有证据的段之间正标签占比极差达到半个概率尺度，即算“段间不一致”：
# 0.5 是概率尺度的一半、唯一对称分界，与 v8 的相对极性门槛取同一值、
# 同一理由，不是从测试集上挑的。
CONSISTENCY_MAX_RANGE = 0.5

# 某段算“有证据”当且仅当该段的加权样本量（权重和）达到此值：借用 v4
# 样本量门槛 GATE_MIN_WEIGHT_N = 30.0 的已有证据标准（同一个“30 个加
# 权样本才算证据”的尺度，从“全态”移到“每段”），不是从测试集上挑的。
MIN_SEGMENT_WEIGHT_N = GATE_MIN_WEIGHT_N


@dataclass
class PredictionV11:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发多段一致性门槛（有证据段之间正标签占比极差 >= 0.5）
    consistency_range: float  # 有证据的段之间加权正标签占比的极差；少于 2 个有证据段时为 0.0
    segment_shares: dict[int, float] = field(default_factory=dict)  # 有证据的段 -> 加权正标签占比
    n_evidence_segments: int = 0  # 有证据的段数；少于 2 个时门槛不触发
    dominant_segment: int | None = None  # 占比最大的有证据段；无有证据段时为 None（诊断用）
    decision_segment: int | None = None  # 决策日当天的趋势段编号；决策日趋势未定义时为 None
    outcome: int = 0
    train_n: int = 0
    bucket_train_n: int = 0
    state_fallback: bool = False  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float = 0.0  # 时效加权基准率
    weight_n: float = 0.0  # 训练集加权样本量（权重和）
    bucket_weight_n: float = 0.0  # 该态加权样本量


def _segment_shares(nav: list[float], decision: int, horizon: int, label_fn,
                    signal: str, window: int, half_life: float,
                    segments: list[int],
                    min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                    ) -> tuple[float, dict[int, float], int]:
    """逐项直算某决策日、某状态的段内正标签占比极差（参照实现）。

    返回 ``(极差, 有证据的段 -> 加权正标签占比, 有证据的段数)``。该态
    无训练样本、或有证据的段少于 2 个时返回 ``(0.0, {}, 段数)``——此
    时门槛不触发（v2 若已回退为加权基准率，更无状态项可不信任）。
    """
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return 0.0, {}, 0
    seg_mass: dict[int, float] = {}
    seg_pos: dict[int, float] = {}
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        if signal_state(nav, start, signal, window) != state:
            continue
        w = _weight(decision - start, half_life)
        seg = segments[start]
        seg_mass[seg] = seg_mass.get(seg, 0.0) + w
        seg_pos[seg] = seg_pos.get(seg, 0.0) + w * label
    shares: dict[int, float] = {}
    for seg, mass in seg_mass.items():
        if mass >= min_segment_weight_n:
            shares[seg] = seg_pos[seg] / mass
    if len(shares) < 2:
        return 0.0, shares, len(shares)
    values = list(shares.values())
    return max(values) - min(values), shares, len(shares)


def _gate(pred: PredictionV2, consistency_range: float,
          segment_shares: dict[int, float], n_evidence_segments: int,
          decision_segment: int | None,
          max_range: float = CONSISTENCY_MAX_RANGE) -> PredictionV11:
    """把一条 v2 预测按多段一致性门槛转成 v11 预测（只用当天的量）。"""
    gated = (
        pred.bucket_weight_n > 0
        and n_evidence_segments >= 2
        and consistency_range >= max_range
    )
    dominant_segment = (
        max(segment_shares, key=lambda s: segment_shares[s])
        if segment_shares
        else None
    )
    return PredictionV11(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        consistency_range=consistency_range,
        segment_shares=dict(segment_shares),
        n_evidence_segments=n_evidence_segments,
        dominant_segment=dominant_segment,
        decision_segment=decision_segment,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v11(nav: list[float], decision: int, horizon: int, label_fn,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            max_range: float = CONSISTENCY_MAX_RANGE,
                            min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                            ) -> PredictionV11 | None:
    """单个决策日的 v11 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下门槛是恒等变换（该态即全部训练集，触发时状态概率
    本就等于加权基准率）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    segments = trend_segment_ids(nav, window)
    consistency_range, shares, n_evidence = _segment_shares(
        nav, decision, horizon, label_fn, signal, window, half_life, segments,
        min_segment_weight_n,
    )
    decision_segment = segments[decision]
    if decision_segment == UNDEFINED_SEGMENT:
        decision_segment = None
    return _gate(base, consistency_range, shares, n_evidence, decision_segment,
                 max_range)


def generate_predictions_v11(nav: list[float], kind: str,
                             signal: str = SIGNAL_DRAWDOWN,
                             window: int = WINDOW_DAYS,
                             test_start: int = TEST_START_INDEX,
                             half_life: float = HALF_LIFE_DAYS,
                             shrinkage_m: float = SHRINKAGE_M,
                             max_range: float = CONSISTENCY_MAX_RANGE,
                             min_segment_weight_n: float = MIN_SEGMENT_WEIGHT_N,
                             ) -> list[PredictionV11]:
    """滚动原点样本外 v11 预测（与 ``weighted_predict_at_v11`` 同口径）。

    段内占比由一趟与 v2 递推同构的并行递推算出：每态、每段的加权质量
    与加权正标签质量每步同步衰减、恰好一个新训练起点进入（起点 = 决
    策日 − 期限），首个决策日直接逐项算出；``kind`` 为 ``"A"`` / ``"B"``，
    其余口径（期限、测试起点、训练资格）全部与 v2 一致。
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
    segments = trend_segment_ids(nav, window)
    last_testable = n - 1 - horizon
    first_decision = max(test_start, window - 1)
    if first_decision > last_testable:
        return []
    decay = 0.5 ** (1.0 / half_life)
    new_weight = 0.5 ** (horizon / half_life)

    def _compute_seg(decision: int):
        """直接逐项算出该决策日每态、每段的加权质量与加权正标签质量（只用于首个决策日）。"""
        mass: dict[tuple[str, int], float] = {}
        pos: dict[tuple[str, int], float] = {}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None or states[start] is None:
                continue
            w = _weight(decision - start, half_life)
            key = (states[start], segments[start])
            mass[key] = mass.get(key, 0.0) + w
            pos[key] = pos.get(key, 0.0) + w * label
        return mass, pos

    def _stats_for(mass: dict[tuple[str, int], float],
                   pos: dict[tuple[str, int], float],
                   state: str | None):
        """从加权质量表取某态的（极差，有证据的段 -> 占比，有证据的段数）。"""
        if state is None:
            return 0.0, {}, 0
        per_seg_mass: dict[int, float] = {}
        per_seg_pos: dict[int, float] = {}
        for (s, seg), w in mass.items():
            if s == state:
                per_seg_mass[seg] = per_seg_mass.get(seg, 0.0) + w
                per_seg_pos[seg] = per_seg_pos.get(seg, 0.0) + pos.get((s, seg), 0.0)
        shares: dict[int, float] = {}
        for seg, m in per_seg_mass.items():
            if m >= min_segment_weight_n:
                shares[seg] = per_seg_pos[seg] / m
        if len(shares) < 2:
            return 0.0, shares, len(shares)
        values = list(shares.values())
        return max(values) - min(values), shares, len(shares)

    # 先算出全部决策日的段内占比极差，再与 v2 的递推输出按 index 对齐。
    stats: dict[int, tuple[float, dict[int, float], int]] = {}
    mass, pos = _compute_seg(first_decision)
    stats[first_decision] = _stats_for(mass, pos, states[first_decision])
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        for key in list(mass):
            mass[key] *= decay
            pos[key] *= decay
        if (
            new_start >= window - 1
            and labels[new_start] is not None
            and states[new_start] is not None
        ):
            key = (states[new_start], segments[new_start])
            mass[key] = mass.get(key, 0.0) + new_weight
            pos[key] = pos.get(key, 0.0) + new_weight * labels[new_start]
        stats[decision] = _stats_for(mass, pos, states[decision])
    v2_preds = generate_predictions_v2(
        nav, kind, signal, window, test_start, half_life, shrinkage_m
    )
    return [
        _gate(
            pred,
            stats[pred.index][0],
            stats[pred.index][1],
            stats[pred.index][2],
            segments[pred.index] if segments[pred.index] != UNDEFINED_SEGMENT else None,
            max_range,
        )
        for pred in v2_preds
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "CONSISTENCY_MAX_RANGE",
    "MIN_SEGMENT_WEIGHT_N",
    "PredictionV11",
    "generate_predictions_v11",
    "label_drawdown_breach",
    "label_positive_return",
    "trend_segment_ids",
    "weighted_predict_at_v11",
]
