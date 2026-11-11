"""概率预测实验 v3（离线实验，不进产品页面、不注册接口）。

条目 13 第三轮：检验“信号与加权基准率的混合权重是否值得保留状态项”
（v2 报告第 7 节开放问题 1 的前半部分）。v2 的中心发现是“信号本身
贡献很小，加权基准率已占主导”——无信号在 3 组最优或并列最优，回撤
档位只在 161725 A 明显占优。本轮不换信号、不调加权常数，只在 v1/v2
的状态概率上再加一层事先固定的混合：

    v3 状态概率 = BLEND_W × v2 状态概率 + (1 − BLEND_W) × 时效加权基准率

``BLEND_W = 0.5``（等权重混合）。取值理由事先写死：等权重是唯一对称、
无参的混合选择——它问的是“把状态项的影响砍半，技能与校准是变好还是
变坏”，而不是“哪个权重在测试集上最优”；**不做参数扫描、不按测试集
调参**。解读规则同样事先写死：
- 若混合后 161725 A 的 +18% 大幅缩水、其余组不变或变差，说明状态项
  在该组确实有价值，砍半是损失；
- 若混合后各组技能普遍改善、失效年份减少，说明 v1 的状态项过强，
  值得保留的是“弱化版”状态项；
- 若混合后既无普遍改善、161725 A 的优势又消失，说明状态项不是可调
  的杠杆——换权重修不了问题。

v3 只改预测器口径，不改评估口径：档位、两类标签、期限、测试起点、
训练资格、比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单
仍用条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率 Brier 为
分母——v3 与 v0/v1/v2 的数字可直接并排比较。时效加权半衰期 756 天、
收缩伪计数 50 从 v1 继承、未改（从 ``forecast_v1`` 导入）。

实现上 v3 是 v2 的薄封装：``weighted_predict_at_v3`` 对 v2 的逐项直算
结果做混合，``generate_predictions_v3`` 对 v2 的递推结果逐项做同样的
混合——两者口径同一，测试守住逐点一致。``"none"`` 信号下混合是恒等
变换（v2 的状态概率已等于加权基准率），本轮运行只用 ``"drawdown"``
信号（问题针对的是回撤档位状态项）；其余信号的混合公式同样适用，
但本轮不跑、不下结论。

因果纪律与 v0/v1/v2 相同：决策日 t 的预测只用 t（含）之前的数据；
训练标签必须在 t 之前已完整观测。改动 t 之后的净值，t 之前（含 t）的
预测必须逐点不变（测试守住）。混合本身只用决策日当天的两个量（v2
状态概率与加权基准率），不引入任何未来信息。

本轮不做 v2 报告第 7 节开放问题 1 的后半部分以外的事：换同类基金复核
161725 A 的 +18% 是否只是个例，由运行脚本在同一轮内另行完成（新基金
的取数与成绩单见报告，不在本模块内）；校准映射（开放问题 2）仍未做，
门槛式状态项（开放问题 1 的另一备选解法）留待下一轮。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v3 未达产品化门槛前不得以任何
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

# 事先固定的混合权重（见模块 docstring，不得运行时调参）。
# 等权重：唯一对称、无参的选择，问“状态项影响砍半是变好还是变坏”。
BLEND_W = 0.5


@dataclass
class PredictionV3:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 混合后状态概率 = BLEND_W × 未混合状态概率 + (1−BLEND_W) × 加权基准率
    unblended_state_prob: float  # v2 的状态概率（混合前）
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时状态概率回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _blend(pred: PredictionV2, blend_w: float = BLEND_W) -> PredictionV3:
    """把一条 v2 预测混合成 v3 预测（只用当天的两个量，不引入未来信息）。"""
    return PredictionV3(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=blend_w * pred.state_prob + (1.0 - blend_w) * pred.baseline_weighted,
        unblended_state_prob=pred.state_prob,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v3(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           blend_w: float = BLEND_W) -> PredictionV3 | None:
    """单个决策日的 v3 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下混合是恒等变换（状态概率已等于加权基准率）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    return _blend(base, blend_w)


def generate_predictions_v3(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            blend_w: float = BLEND_W) -> list[PredictionV3]:
    """滚动原点样本外 v3 预测（与 ``weighted_predict_at_v3`` 同口径）。

    直接对 v2 的递推结果逐项混合；``kind`` 为 ``"A"`` / ``"B"``，
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
        _blend(pred, blend_w)
        for pred in generate_predictions_v2(
            nav, kind, signal, window, test_start, half_life, shrinkage_m
        )
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "BLEND_W",
    "PredictionV3",
    "generate_predictions_v3",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v3",
]
