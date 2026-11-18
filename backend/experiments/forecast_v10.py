"""概率预测实验 v10（离线实验，不进产品页面、不注册接口）。

条目 13 第十轮：检验“训练样本行情构成”的另一条定义——按净值趋势
划分牛熊段（v9 报告第 9 节开放问题 2；v6 报告第 9 节开放问题 1 的第
二条路、v8 报告第 9 节开放问题 2 的第二条路一直未检验）。v9 的证据
让这条路更值得检验：110022 A 高估口袋的诊断已修正为“最近一两年一
边倒、再往前一年反向，时效加权让最近年份主导了加权平均”——若按净
值趋势切段，2015 年与 2018 年那两个反向年份是否会被划进与最近年份
同一段，正是本轮要量的。

为什么不先做 v9 报告第 9 节开放问题 1（更宽松的多年定义，如“多数年
份一边倒”）：v9 报告原文已把这条路标为数据窥探的高危区——口袋恰
好是“2 年同向、1 年反向”，把合取改成“2/3 年份”只因为口袋恰好如此，
就是用本轮的观测结果（逐年占比 0.298、0.0）反推下一轮的定义。本轮
不碰多年定义，改走与多年定义无关的另一条行情定义；多年定义的宽松
化留待后续轮次另行论证（须给出独立于测试集的事前依据，不得从口袋
的逐年占比反推）。

“行情段”的定义（事先固定、写死在本模块中并在报告中披露，**不做参
数扫描、不按测试集调参**）：复用 v2 已注册的趋势信号定义——决策日
累计净值与近 250 日简单均线的关系（``"above"`` / ``"below"``，窗口
取 ``WINDOW_DAYS``，不另引新常数）。一段行情 = 趋势状态连续相同的一
段交易日（最大连续 run）；每个训练标签归属其训练起点所在的那一段。
理由事先写死：趋势状态是项目已有的、最常见的行情状态划分之一，
250 日窗口与回撤窗口一致；连续 run 是“一段行情”的自然形式化——
与 v6 的“日历年”相比，它不按日历切分，而是按市场自身的趋势切换切
分；2015 年与 2018 年的反向年份若在净值趋势上属于同一段，就会被划
进同一段，若分属不同段则不会——哪一种成立由数据决定，定义本身不
预判。局限同样事先写明：均线趋势是滞后指标，段的边界由均线穿越决
定，不等于真实牛熊转折；本轮只检验“趋势段集中度”这一可度量的版本，
不宣称检验了真正的牛熊构成。

集中度度量（事先固定）：对某决策日、某状态，取该态的时效加权训练
标签（权重与 v1 相同，半衰期 756 天），按起点所在的趋势段分组，计算
**主导段占比** ``dominant_segment_share = 该态加权样本量中最大一段
的占比``，并附记有效段数 ``effective_segments = 1 / Σ share²``（诊
断用，不参与门槛判断）。按权重而不是按标签计数——与预测器实际使用
的证据一致；标签值本身不进入集中度计算（集中度量的是“证据从哪来”，
不是“证据说什么”）。

门槛（事先固定）：``REGIME_MAX_DOMINANT_SHARE = 0.5``。若某态加权
训练标签中单一趋势段的占比 >= 0.5（即“超过一半的有效证据来自同一
段行情”，一段的证据超过全部其他段之和），该态算“行情集中”，该日不
用状态项、回退为时效加权基准率。取值理由事先写死：0.5 是“过半”的
唯一对称分界，与 v6 的年份门槛取同一值、同一理由，不是从测试集上挑
的；边界语义为“达到即触发”（>=），与 v6/v7/v8 门槛的方向一致。

检验方式（事先固定）：门槛式回退（与 v4/v6/v7/v8/v9 同构），不是限
制训练样本覆盖、不是按行情加权。理由：与 v6 可比——v6 问“样本够不
够按年份分散”，v10 问“样本够不够按趋势段分散”；两种门槛的触发日
集合与效果可直接并排比较。

v10 只改预测器口径，不改评估口径：v10 = v2 回撤档位状态概率 + 趋势
段集中度门槛（不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份
门槛、不叠加 v7 绝对极性门槛、不叠加 v8 相对极性门槛、不叠加 v9 多
年门槛——本轮只检验趋势段集中度这一个因素；与混合/样本量门槛/年份
门槛/极性门槛/多年门槛的叠加是下一轮的干净问题）。档位、两类标签、
期限、测试起点、训练资格、比较基准（v0 无加权历史基准率）全部与条
目 8/9 一致；成绩单仍用条目 9 的 ``build_scorecard``，技能分数仍以
v0 基准率 Brier 为分母——v10 与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9 的数
字可直接并排比较。时效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、
未改。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v10 在 110022 A 上缩小高估口袋（80%–100% 校准档差值明显缩小）
  和/或修掉 2015 年初 4 个极端日所在的低估档、和/或让 110020 A 类
  2014 年不再失效，同时在 161725 A 上没有大幅丢掉优势，说明趋势段
  集中度是问题的一部分——趋势段门槛值得保留为候选；
- 若 v10 在各组上约等于 v1（触发极少、或触发日与 v1 无差别），说明
  趋势段集中度门槛没有增加超出 v1 的信息；
- 若 v10 比 v1 更差，说明集中度高的态恰恰有信息、门槛过激——这条路
  不成立；
- 2014 年案例单独报告：v10 是否让 110020 A 类 2014 年不再失效（当
  年 Brier 是否低于基准率 Brier 0.419）。事先写明不预判：2014 年案
  例的 <5% 档训练标签全来自 2009–2010 两年，这两年在净值趋势上是
  一段还是多段、主导段占比是否过半，由数据决定；若修不掉，那正是
  “趋势段集中度”与“样本量/年份/极性”几种门槛覆盖情形不同的证据；
- 110022 A 高估口袋单独报告：事先写明不预判——口袋 62 天的训练标
  签是否集中在单一趋势段、2015 年与 2018 年的反向年份是否与最近年
  份同段，由数据决定；若口袋 0 天触发，不得事后把段的定义（如窗口、
  均线类型）改成“刚好抓住”它；
- B 类组事先说明：事件本身高频时趋势段天然可能集中（一段长牛市里
  跌超 10% 的窗口到处都是），若门槛在 B 类上比 v1 更差，说明门槛分
  不清“事件高频”与“单一行情扭曲”（与 v7/v9 在 B 类上的教训相同）；
- 近退化组（217022 A）事先说明：门槛预计在多数决策日触发、v10 约
  等于加权基准率，千分位差别不得读作改善。

实现上 v10 是 v2 的薄封装：``weighted_predict_at_v10`` 对 v2 的逐项
直算结果做门槛判断（趋势段占比另行直算），``generate_predictions_v10``
对 v2 的递推结果逐项做同样的判断——趋势段占比由一趟与 v2 递推同构
的并行递推算出（每态、每段的加权质量同步衰减、同步进入），两者口径
同一，测试守住逐点一致。本轮运行只用 ``"drawdown"`` 信号（问题针对
的是回撤档位状态项）；其余信号的门槛公式同样适用，但本轮不跑、不下
结论。

段归属只用训练起点（含）之前的数据：某日所属的趋势段由该日（含）
之前的趋势状态序列决定（run 的起点在过去；run 的终点在未来不影响
该日的段归属——段编号按 run 出现顺序递增，只依赖起点及之前的状
态）。因果纪律与 v0/v1/v2/v3/v4/v5/v6/v7/v8/v9 相同：决策日 t 的预
测只用 t（含）之前的数据；训练标签必须在 t 之前已完整观测；段占比
只用决策日当天的训练集（已是 t 之前数据的加权统计），不引入任何未
来信息。改动 t 之后的净值，t 之前（含 t）的预测必须逐点不变（测试
守住）。

本轮不做 v9 报告第 9 节开放问题 1（更宽松的多年定义，须独立于测试
集的事前依据）、开放问题 3（门槛的证据要求改按加权质量）、开放问题
4（校准映射，须事先写死拟合窗口与更新频率并单独报告映射本身的样本
外表现）、开放问题 5（门槛叠加须先回答“为什么 B 类上门槛总犯错”），
四者留待下一轮。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v10 未达产品化门槛前不得以任何
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
    SIGNAL_TREND,
    SIGNALS,
    PredictionV2,
    _training_starts,
    generate_predictions_v2,
    signal_state,
    weighted_predict_at_v2,
)

# 事先固定的门槛（见模块 docstring，不得运行时调参）。
# 单一趋势段占某态加权训练样本量的一半及以上，即算“行情集中”：
# 0.5 是“过半”的唯一对称分界，与 v6 的年份门槛取同一值、同一理由，
# 不是从测试集上挑的。
REGIME_MAX_DOMINANT_SHARE = 0.5

# 趋势未定义的日子（下标 < window - 1，均线尚无完整窗口）的段编号。
# 训练起点恒 >= window - 1，永不落入该段；此处只作占位，不参与门槛
# 判断之外的任何统计。
UNDEFINED_SEGMENT = -1


def trend_segment_ids(nav: list[float],
                      window: int = WINDOW_DAYS) -> list[int]:
    """每下标所属的趋势段编号（与 ``signal_state`` 的趋势定义同口径）。

    趋势状态为净值与近 ``window`` 日简单均线的关系（``"above"`` /
    ``"below"``，见 v2）；一段 = 趋势状态连续相同的一段交易日（最大连
    续 run），段编号按 run 出现顺序从 0 递增。均线尚无完整窗口的日子
    （下标 < window - 1）趋势未定义，段编号记为 ``UNDEFINED_SEGMENT``
    （-1）。某日的段编号只依赖该日（含）之前的趋势状态——run 的终点
    在未来不影响该日的归属，不引入未来信息。
    """
    segments: list[int] = []
    current_state: str | None = None
    current_id = UNDEFINED_SEGMENT
    for i in range(len(nav)):
        state = signal_state(nav, i, SIGNAL_TREND, window)
        if state is None:
            segments.append(UNDEFINED_SEGMENT)
            continue
        if state != current_state:
            current_state = state
            current_id = 0 if current_id == UNDEFINED_SEGMENT else current_id + 1
        segments.append(current_id)
    return segments


@dataclass
class PredictionV10:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发趋势段集中度门槛（主导段占比 >= 0.5）
    dominant_segment_share: float  # 该态加权训练样本量中最大一段的占比（0.0–1.0）
    dominant_segment: int | None  # 占比最大的趋势段编号；该态无训练样本时为 None
    decision_segment: int | None  # 决策日当天的趋势段编号；决策日趋势未定义时为 None
    effective_segments: float  # 有效段数 = 1 / Σ share²；该态无训练样本时为 0.0
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _segment_stats(nav: list[float], decision: int, horizon: int, label_fn,
                   signal: str, window: int, half_life: float,
                   segments: list[int]) -> tuple[float, int | None, float, float]:
    """逐项直算某决策日、某状态的趋势段集中度（参照实现）。

    返回 ``(主导段占比, 主导段, 有效段数, 该态加权样本量)``。该态无训
    练样本时返回 ``(0.0, None, 0.0, 0.0)``——此时 v2 已回退为加权基准
    率，门槛不触发（没有状态项可不信任）。
    """
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return 0.0, None, 0.0, 0.0
    seg_mass: dict[int, float] = {}
    bucket_wn = 0.0
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        if signal_state(nav, start, signal, window) != state:
            continue
        w = _weight(decision - start, half_life)
        bucket_wn += w
        seg = segments[start]
        seg_mass[seg] = seg_mass.get(seg, 0.0) + w
    if bucket_wn == 0:
        return 0.0, None, 0.0, 0.0
    dominant_segment = max(seg_mass, key=lambda s: seg_mass[s])
    share = seg_mass[dominant_segment] / bucket_wn
    effective = 1.0 / sum((m / bucket_wn) ** 2 for m in seg_mass.values())
    return share, dominant_segment, effective, bucket_wn


def _gate(pred: PredictionV2, share: float, dominant_segment: int | None,
          decision_segment: int | None, effective_segments: float,
          max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE) -> PredictionV10:
    """把一条 v2 预测按趋势段集中度门槛转成 v10 预测（只用当天的量）。"""
    gated = pred.bucket_weight_n > 0 and share >= max_dominant_share
    return PredictionV10(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        dominant_segment_share=share,
        dominant_segment=dominant_segment,
        decision_segment=decision_segment,
        effective_segments=effective_segments,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v10(nav: list[float], decision: int, horizon: int, label_fn,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE) -> PredictionV10 | None:
    """单个决策日的 v10 预测（逐项直算参照实现）。

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
    share, dominant_segment, effective, _ = _segment_stats(
        nav, decision, horizon, label_fn, signal, window, half_life, segments
    )
    decision_segment = segments[decision]
    if decision_segment == UNDEFINED_SEGMENT:
        decision_segment = None
    return _gate(base, share, dominant_segment, decision_segment, effective,
                 max_dominant_share)


def generate_predictions_v10(nav: list[float], kind: str,
                             signal: str = SIGNAL_DRAWDOWN,
                             window: int = WINDOW_DAYS,
                             test_start: int = TEST_START_INDEX,
                             half_life: float = HALF_LIFE_DAYS,
                             shrinkage_m: float = SHRINKAGE_M,
                             max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE) -> list[PredictionV10]:
    """滚动原点样本外 v10 预测（与 ``weighted_predict_at_v10`` 同口径）。

    趋势段占比由一趟与 v2 递推同构的并行递推算出：每态、每段的加权质
    量每步同步衰减、恰好一个新训练起点进入（起点 = 决策日 − 期限），首
    个决策日直接逐项算出；``kind`` 为 ``"A"`` / ``"B"``，其余口径（期限、
    测试起点、训练资格）全部与 v2 一致。
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

    def _compute_seg_mass(decision: int) -> dict[tuple[str, int], float]:
        """直接逐项算出该决策日每态、每段的加权质量（只用于首个决策日）。"""
        mass: dict[tuple[str, int], float] = {}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None or states[start] is None:
                continue
            w = _weight(decision - start, half_life)
            key = (states[start], segments[start])
            mass[key] = mass.get(key, 0.0) + w
        return mass

    def _stats_for(mass: dict[tuple[str, int], float], state: str | None):
        """从加权质量表取某态的（主导段占比，主导段，有效段数）。"""
        if state is None:
            return 0.0, None, 0.0
        total = 0.0
        per_seg: dict[int, float] = {}
        for (s, seg), w in mass.items():
            if s == state:
                total += w
                per_seg[seg] = per_seg.get(seg, 0.0) + w
        if total == 0:
            return 0.0, None, 0.0
        dominant_segment = max(per_seg, key=lambda s: per_seg[s])
        share = per_seg[dominant_segment] / total
        effective = 1.0 / sum((m / total) ** 2 for m in per_seg.values())
        return share, dominant_segment, effective

    # 先算出全部决策日的趋势段占比，再与 v2 的递推输出按 index 对齐。
    stats: dict[int, tuple[float, int | None, float]] = {}
    mass = _compute_seg_mass(first_decision)
    stats[first_decision] = _stats_for(mass, states[first_decision])
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        for key in list(mass):
            mass[key] *= decay
        if (
            new_start >= window - 1
            and labels[new_start] is not None
            and states[new_start] is not None
        ):
            key = (states[new_start], segments[new_start])
            mass[key] = mass.get(key, 0.0) + new_weight
        stats[decision] = _stats_for(mass, states[decision])
    v2_preds = generate_predictions_v2(
        nav, kind, signal, window, test_start, half_life, shrinkage_m
    )
    return [
        _gate(
            pred,
            stats[pred.index][0],
            stats[pred.index][1],
            segments[pred.index] if segments[pred.index] != UNDEFINED_SEGMENT else None,
            stats[pred.index][2],
            max_dominant_share,
        )
        for pred in v2_preds
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "REGIME_MAX_DOMINANT_SHARE",
    "UNDEFINED_SEGMENT",
    "PredictionV10",
    "generate_predictions_v10",
    "label_drawdown_breach",
    "label_positive_return",
    "trend_segment_ids",
    "weighted_predict_at_v10",
]
