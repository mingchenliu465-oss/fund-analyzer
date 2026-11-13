"""概率预测实验 v5（离线实验，不进产品页面、不注册接口）。

条目 13 第五轮：检验“门槛与混合是否叠加”（v4 报告第 8 节开放问题 2）。
v3 的混合让 110020 A 的技能好 3.7 个百分点（−9.4% → −5.7%），v4 的
门槛让它好 1.1 个百分点（−9.4% → −8.3%），两者作用在不同的决策日
集合上——混合改全部决策日、门槛只改 53 天（A 类）。本轮问的是：
**把门槛用在混合后的概率上，是叠加变好、还是互相抵消**——而不是
再换一种状态定义或再调权重。

叠加定义（事先固定、写死在本模块中并在报告中披露，**不做参数扫描、
不按测试集调参**）：

    v5 状态概率 = 混合后概率，若该决策日所处状态的时效加权训练
    样本量（``bucket_weight_n``）>= GATE_MIN_WEIGHT_N；
    否则 = 时效加权基准率（即 ``"none"`` 候选在该日的概率）。

    混合后概率 = BLEND_W × v2 状态概率 + (1 − BLEND_W) × 时效加权基准率。

先混合、后门槛：门槛判断只看 ``bucket_weight_n``，与 v4 同一条线；
混合权重 0.5 与门槛 30.0 均从 v3/v4 原样继承、未改（分别从
``forecast_v3`` / ``forecast_v4`` 导入）。另一种叠加顺序（先门槛、
后混合：触发日 = 0.5 × 加权基准率 + 0.5 × 加权基准率 = 加权基准率，
与本定义在触发日上相同；未触发日 = 0.5 × v2 + 0.5 × 加权基准率，
与本定义也相同）——两种顺序在本定义下逐点等价，所以不存在“顺序
选错”的歧义；本轮只报告这一种定义。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v5 在 110020 A/B 上同时优于 v3 与 v4，说明门槛的薄态修正与混
  合的弱化状态项叠加成立——两者是互补的修补；
- 若 v5 在各组上约等于 v3（与 v3 的技能差在 0.5 个百分点以内），说
  明门槛的贡献已被混合覆盖——混合把状态项砍半之后，薄态里已没有
  值得门槛再修的东西，门槛是多余的一层；
- 若 v5 比 v3 更差，说明门槛伤害了混合：薄态里被砍半的状态项仍有
  价值，门槛把它整个拿掉是过激的——门槛这条路在混合之后不成立；
- 2014 年案例单独报告：v5 是否让 110020 A 类 2014 年不再失效
  （当年 Brier 是否低于基准率 Brier 0.419；该年 33 个决策日全部被
  门槛触发，v5 在该年应逐点等于无信号）。

v5 只改预测器口径，不改评估口径：档位、两类标签、期限、测试起点、
训练资格、比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单
仍用条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier 为
分母——v5 与 v0/v1/v2/v3/v4 的数字可直接并排比较。时效加权半衰期
756 天、收缩伪计数 50 从 v1 继承、未改（从 ``forecast_v1`` 导入）。

实现上 v5 是 v2 的薄封装：``weighted_predict_at_v5`` 对 v2 的逐项直算
结果先混合、后门槛，``generate_predictions_v5`` 对 v2 的递推结果逐项
做同样的两步——两者口径同一，测试守住逐点一致。本轮运行只用
``"drawdown"`` 信号（问题针对的是回撤档位状态项）；其余信号的叠加
公式同样适用，但本轮不跑、不下结论。

因果纪律与 v0/v1/v2/v3/v4 相同：决策日 t 的预测只用 t（含）之前的数据；
训练标签必须在 t 之前已完整观测。改动 t 之后的净值，t 之前（含 t）的
预测必须逐点不变（测试守住）。混合与门槛判断只用决策日当天的量
（v2 状态概率、加权基准率、``bucket_weight_n``，已是 t 之前数据的
加权统计），不引入任何未来信息。

本轮不做 v4 报告第 8 节开放问题 1（训练样本行情构成检验，须先定义
“行情”）与开放问题 3（校准映射，须事先写死拟合窗口与更新频率并单独
报告映射本身的样本外表现），两者留待下一轮。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v5 未达产品化门槛前不得以任何
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
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNALS,
    PredictionV2,
    generate_predictions_v2,
    weighted_predict_at_v2,
)
from experiments.forecast_v3 import BLEND_W
from experiments.forecast_v4 import GATE_MIN_WEIGHT_N


@dataclass
class PredictionV5:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 叠加后状态概率：未触发门槛时 = 混合后概率；触发时 = 加权基准率
    blended_state_prob: float  # 混合后、门槛前概率 = BLEND_W × v2 + (1−BLEND_W) × 加权基准率
    ungated_state_prob: float  # v2 的状态概率（混合与门槛前）
    gated: bool  # 该日是否触发门槛（该态加权训练样本量 < GATE_MIN_WEIGHT_N）
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _blend_and_gate(pred: PredictionV2, blend_w: float = BLEND_W,
                    gate_min_weight_n: float = GATE_MIN_WEIGHT_N) -> PredictionV5:
    """把一条 v2 预测先混合、后门槛，转成 v5 预测（只用当天的量，不引入未来信息）。"""
    blended = blend_w * pred.state_prob + (1.0 - blend_w) * pred.baseline_weighted
    gated = pred.bucket_weight_n < gate_min_weight_n
    return PredictionV5(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else blended,
        blended_state_prob=blended,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v5(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           blend_w: float = BLEND_W,
                           gate_min_weight_n: float = GATE_MIN_WEIGHT_N) -> PredictionV5 | None:
    """单个决策日的 v5 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下混合与门槛都是恒等变换（状态概率已等于加权基准率）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    return _blend_and_gate(base, blend_w, gate_min_weight_n)


def generate_predictions_v5(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            blend_w: float = BLEND_W,
                            gate_min_weight_n: float = GATE_MIN_WEIGHT_N) -> list[PredictionV5]:
    """滚动原点样本外 v5 预测（与 ``weighted_predict_at_v5`` 同口径）。

    直接对 v2 的递推结果逐项先混合、后门槛；``kind`` 为 ``"A"`` / ``"B"``，
    其余口径（期限、测试起点、训练资格）全部与 v2 一致。
    """
    if kind == "A":
        horizon = HORIZON_A_DAYS
    elif kind == "B":
        horizon = HORIZON_B_DAYS
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    return [
        _blend_and_gate(pred, blend_w, gate_min_weight_n)
        for pred in generate_predictions_v2(
            nav, kind, signal, window, test_start, half_life, shrinkage_m
        )
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "BLEND_W",
    "GATE_MIN_WEIGHT_N",
    "PredictionV5",
    "generate_predictions_v5",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v5",
]
