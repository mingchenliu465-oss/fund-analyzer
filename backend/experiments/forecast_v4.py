"""概率预测实验 v4（离线实验，不进产品页面、不注册接口）。

条目 13 第四轮：检验“门槛式状态项”（v2 报告第 7 节开放问题 1 的
另一备选解法、v3 报告第 8 节开放问题 1 的第一项）。v1→v3 三轮的
中心发现是：状态项的贡献很小，加权基准率已占主导；2014 年案例与
110022 A 高估口袋都指向同一个根因——训练样本的行情构成：状态项
在训练样本又薄又旧（全来自某一段旧行情）的态上照样给出“有信心”
的概率。本轮问的是：**状态项只在训练样本极充足时才起作用，会不
会更好**——而不是再换一种状态定义或再调权重。

门槛定义（事先固定、写死在本模块中并在报告中披露，**不做参数扫描、
不按测试集调参**）：

    v4 状态概率 = v2 状态概率，若该决策日所处状态的时效加权训练
    样本量（``bucket_weight_n``）>= GATE_MIN_WEIGHT_N；
    否则 = 时效加权基准率（即 ``"none"`` 候选在该日的概率）。

``GATE_MIN_WEIGHT_N = 30.0``。取值理由事先写死：项目已有的证据规则
（``forecast_scorecard.MIN_BUCKET_N = 30``）把样本外数低于 30 的档
定为“证据不足”；v4 把同一条 30 的线用在预测器真正使用的时效加权
证据上——一个态的加权样本量低于 30，就算“薄”。这个门槛不是从测试
集上挑出来的：它是借用已有的证据规则；一个原始计数超过 30、但全是
旧行情的态（如 2014 年案例：<5% 档训练起点 37 个，全来自 2009–2010
年熊市，半衰期 756 天加权后有效样本远低于 30），按本规则仍算薄——
这正是本轮要检验的情形。门槛只看加权样本量，不看标签构成：不引入
“行情”定义（那是 v3 报告第 8 节开放问题 1 的另一条路，留待下一轮）。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v4 在 v1/v3 失败的组（110020 A、161725 B、110020 B）上技能
  改善，且在 161725 A 上没有大幅丢掉优势，说明“薄态”是问题的一
  部分——门槛式状态项值得保留为候选；
- 若 v4 在各组上约等于无信号（``"none"``），说明门槛没有增加超出
  “不要状态项”的信息——状态项本身仍是净负担；
- 若 v4 比 v3 更差，说明门槛过于激进、或状态项的价值恰恰在薄态里
  ——门槛这条路不成立；
- 2014 年案例单独报告：v4 是否让 110020 A 类 2014 年不再失效
  （当年 Brier 是否低于基准率 Brier 0.419）。

v4 只改预测器口径，不改评估口径：档位、两类标签、期限、测试起点、
训练资格、比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单
仍用条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier 为
分母——v4 与 v0/v1/v2/v3 的数字可直接并排比较。时效加权半衰期 756 天、
收缩伪计数 50 从 v1 继承、未改（从 ``forecast_v1`` 导入）；混合权重
0.5 不用在本轮（v3 的混合与门槛是两个独立问题，本轮只检验门槛）。

实现上 v4 是 v2 的薄封装：``weighted_predict_at_v4`` 对 v2 的逐项直算
结果做门槛判断，``generate_predictions_v4`` 对 v2 的递推结果逐项做同
样的判断——两者口径同一，测试守住逐点一致。本轮运行只用
``"drawdown"`` 信号（问题针对的是回撤档位状态项）；其余信号的门槛
公式同样适用，但本轮不跑、不下结论。

因果纪律与 v0/v1/v2/v3 相同：决策日 t 的预测只用 t（含）之前的数据；
训练标签必须在 t 之前已完整观测。改动 t 之后的净值，t 之前（含 t）的
预测必须逐点不变（测试守住）。门槛判断只用决策日当天的
``bucket_weight_n``（已是 t 之前数据的加权统计），不引入任何未来信息。

本轮不做 v3 报告第 8 节开放问题 1 的另一条路（训练样本行情构成检验，
须先定义“行情”）与开放问题 2（校准映射，须事先写死拟合窗口与更新
频率并单独报告映射本身的样本外表现），两者留待下一轮。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v4 未达产品化门槛前不得以任何
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
from experiments.forecast_scorecard import MIN_BUCKET_N

# 事先固定的门槛（见模块 docstring，不得运行时调参）。
# 借用项目已有的证据规则 MIN_BUCKET_N = 30，用在时效加权样本量上：
# 某态加权训练样本量低于 30 即算“薄”，该日不用状态项、回退为加权基准率。
GATE_MIN_WEIGHT_N = float(MIN_BUCKET_N)


@dataclass
class PredictionV4:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发门槛（该态加权训练样本量 < GATE_MIN_WEIGHT_N）
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _gate(pred: PredictionV2, gate_min_weight_n: float = GATE_MIN_WEIGHT_N) -> PredictionV4:
    """把一条 v2 预测按门槛转成 v4 预测（只用当天的量，不引入未来信息）。"""
    gated = pred.bucket_weight_n < gate_min_weight_n
    return PredictionV4(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
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


def weighted_predict_at_v4(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           gate_min_weight_n: float = GATE_MIN_WEIGHT_N) -> PredictionV4 | None:
    """单个决策日的 v4 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下门槛几乎恒不触发（该态即全部训练集，加权样本量
    远大于门槛），且触发时状态概率本就等于加权基准率——恒等变换。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    return _gate(base, gate_min_weight_n)


def generate_predictions_v4(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            gate_min_weight_n: float = GATE_MIN_WEIGHT_N) -> list[PredictionV4]:
    """滚动原点样本外 v4 预测（与 ``weighted_predict_at_v4`` 同口径）。

    直接对 v2 的递推结果逐项做门槛判断；``kind`` 为 ``"A"`` / ``"B"``，
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
        _gate(pred, gate_min_weight_n)
        for pred in generate_predictions_v2(
            nav, kind, signal, window, test_start, half_life, shrinkage_m
        )
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "GATE_MIN_WEIGHT_N",
    "PredictionV4",
    "generate_predictions_v4",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v4",
]
