"""概率预测实验 v1（离线实验，不进产品页面、不注册接口）。

条目 13 第一轮：改进信号与校准。针对条目 9 报告第 5 节定案的 v0
结构性弱点——“单信号、全部历史等权重”：
- v0 的训练集是决策日之前全部已完成标签的等权重平均。行情切换后
  （如 161725 测试期 2020 年后白酒下行 vs 训练历史以上行段为主），
  旧历史仍占主导，导致全部校准档一致高估（平均状态概率 61.4% vs
  实际 26.6%）。
- 档位训练样本即使数量不小也可能全部来自单一行情（110020 A 类
  2014 年：<5% 档 37 个样本全来自 2009–2010 年熊市，33 个预测全错、
  Brier 恰 1.0）。等权重条件频率对这类档位过度自信。

v1 只改预测器口径，不改评估口径：档位定义、两类标签、期限、测试
起点、训练资格（起点 <= 决策日 − 期限且有完整 250 日窗口）、比较
基准（v0 无加权历史基准率）全部与条目 8/9 一致；成绩单仍用条目 9
的 ``forecast_scorecard.build_scorecard``，技能分数仍以 v0 基准率
Brier 为分母——v1 与 v0 的数字可直接并排比较。

v1 的两个机制（常数事先固定、写死在模块中并在本 docstring 与报告
中披露；**不做参数扫描、不按测试集调参**，下一轮如需换常数须另起
版本号并写清理由）：
1. 时效加权：训练起点权重 ``w = 0.5 ** ((决策日 − 起点) / HALF_LIFE_DAYS)``，
   ``HALF_LIFE_DAYS = 756``（约 3 个交易年）。越久的标签权重越低，
   预测器随行情切换而移动，但从不丢弃旧数据（权重趋近 0 而不是截断）。
2. 向基准率收缩：档位状态概率 = ``(档位置信加权标签和 + M × 加权基准率)
   / (档位置信加权样本量 + M)``，``SHRINKAGE_M = 50``（伪计数）。
   档位加权样本量越小、预测越贴近加权基准率；档位样本量大时收缩
   几乎不起作用。档位完全没有训练样本时回退为加权基准率（与 v0 的
   回退语义一致，只是回退目标由无加权基准率改为加权基准率）。

``Prediction.baseline_prob`` 字段仍填 v0 无加权基准率（比较基准），
加权基准率另存为 ``baseline_weighted`` 字段，供报告诊断用（加权
基准率本身的 Brier 可在运行脚本中单独算出，不与 v0 技能分数混用）。

因果纪律与 v0 相同：决策日 t 的预测只用 t（含）之前的数据；训练
标签必须在 t 之前已完整观测。改动 t 之后的净值，t 之前（含 t）的
预测必须逐点不变（测试守住）。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都
必须同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的
披露；禁止点位预测、涨跌断言、买卖推荐表述。v1 未达产品化门槛前
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

# 事先固定的常数（见模块 docstring，不得运行时调参）。
HALF_LIFE_DAYS = 756  # 时效加权半衰期，约 3 个交易年
SHRINKAGE_M = 50.0  # 向基准率收缩的伪计数


@dataclass
class PredictionV1:
    index: int
    bucket: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该档训练样本为 0 时状态概率回退为加权基准率
    baseline_weighted: float  # 时效加权基准率（诊断用）
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该档加权样本量


def _weight(age_days: int, half_life: float = HALF_LIFE_DAYS) -> float:
    """起点相对决策日的时效权重：半衰期 ``half_life`` 天的指数衰减。"""
    return 0.5 ** (age_days / half_life)


def _training_starts(decision: int, horizon: int, window: int = WINDOW_DAYS):
    """与 v0 相同的训练资格：起点需有完整回撤窗口（index >= window-1）
    且标签在决策日之前已完整观测（起点 <= decision - horizon）。"""
    return range(window - 1, decision - horizon + 1)


def weighted_predict_at(nav: list[float], decision: int, horizon: int, label_fn,
                       window: int = WINDOW_DAYS,
                       half_life: float = HALF_LIFE_DAYS,
                       shrinkage_m: float = SHRINKAGE_M,
                       mode: str = "v1") -> PredictionV1 | None:
    """单个决策日的 v1 预测（逐项直算参照实现）。

    mode：
    - ``"v1"``：时效加权档位频率 + 向加权基准率收缩（默认）。
    - ``"recency"``：只有时效加权，不收缩（``shrinkage_m`` 视为 0）。
      诊断用：把 v1 的改进拆成“加权”与“收缩”两部分。
    - ``"wbaseline"``：状态概率即加权基准率（不分档位）。诊断用：
      只看加权本身相对 v0 基准率是更好还是更差。
    """
    if mode not in ("v1", "recency", "wbaseline"):
        raise ValueError(f"unknown mode: {mode!r}")
    if decision < window - 1:
        return None
    if mode == "recency":
        shrinkage_m = 0.0
    outcome = label_fn(nav, decision, horizon)
    if outcome is None:
        return None
    bucket = bucket_for_drawdown(drawdown_at(nav, decision, window))
    total_n = 0
    total_sum = 0
    weight_n = 0.0
    weight_sum = 0.0
    bucket_n = 0
    bucket_wn = 0.0
    bucket_ws = 0.0
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        total_n += 1
        total_sum += label
        w = _weight(decision - start, half_life)
        weight_n += w
        weight_sum += w * label
        if bucket_for_drawdown(drawdown_at(nav, start, window)) == bucket:
            bucket_n += 1
            bucket_wn += w
            bucket_ws += w * label
    if total_n == 0:
        return None
    baseline = total_sum / total_n
    baseline_weighted = weight_sum / weight_n
    if mode == "wbaseline":
        state_prob = baseline_weighted
        fallback = False
    elif bucket_wn == 0:
        state_prob = baseline_weighted
        fallback = True
    else:
        state_prob = (bucket_ws + shrinkage_m * baseline_weighted) / (
            bucket_wn + shrinkage_m
        )
        fallback = False
    return PredictionV1(
        index=decision,
        bucket=bucket,
        baseline_prob=baseline,
        state_prob=state_prob,
        outcome=outcome,
        train_n=total_n,
        bucket_train_n=bucket_n,
        state_fallback=fallback,
        baseline_weighted=baseline_weighted,
        weight_n=weight_n,
        bucket_weight_n=bucket_wn,
    )


def generate_predictions_v1(nav: list[float], kind: str, mode: str = "v1",
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M) -> list[PredictionV1]:
    """滚动原点样本外 v1 预测（与 ``weighted_predict_at`` 同口径）。

    实现用递推：决策日每前进一天，全部旧权重乘一次衰减因子
    ``0.5 ** (1 / half_life)``，同时恰好一个新训练起点进入资格
    （起点 = 决策日 − 期限），其初始权重为 ``0.5 ** (期限 / half_life)``；
    无加权统计（v0 基准率）同步递增。首个决策日的统计直接逐项算出，
    之后每步 O(1)。``weighted_predict_at`` 保留为逐项直算的参照实现，
    两者在同一序列上的抽查一致性由测试与运行脚本核对。
    """
    if kind == "A":
        horizon, label_fn = HORIZON_A_DAYS, label_positive_return
    elif kind == "B":
        horizon, label_fn = HORIZON_B_DAYS, label_drawdown_breach
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    if mode not in ("v1", "recency", "wbaseline"):
        raise ValueError(f"unknown mode: {mode!r}")
    if mode == "recency":
        shrinkage_m = 0.0
    n = len(nav)
    buckets = [bucket_for_drawdown(drawdown_at(nav, i, window)) for i in range(n)]
    labels = [label_fn(nav, i, horizon) for i in range(n)]
    last_testable = n - 1 - horizon
    first_decision = max(test_start, window - 1)
    if first_decision > last_testable:
        return []
    decay = 0.5 ** (1.0 / half_life)
    new_weight = 0.5 ** (horizon / half_life)
    bucket_names = ("<5%", "5%-10%", ">10%")

    def _compute(decision: int):
        """直接逐项算出该决策日的全部统计（只用于首个决策日）。"""
        total_n = total_sum = 0
        weight_n = weight_sum = 0.0
        bucket_n: dict[str, int] = {b: 0 for b in bucket_names}
        bucket_wn: dict[str, float] = {b: 0.0 for b in bucket_names}
        bucket_ws: dict[str, float] = {b: 0.0 for b in bucket_names}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None:
                continue
            total_n += 1
            total_sum += label
            w = _weight(decision - start, half_life)
            weight_n += w
            weight_sum += w * label
            b = buckets[start]
            bucket_n[b] += 1
            bucket_wn[b] += w
            bucket_ws[b] += w * label
        return total_n, total_sum, weight_n, weight_sum, bucket_n, bucket_wn, bucket_ws

    def _make_pred(decision: int, total_n, total_sum, weight_n, weight_sum,
                   bucket_n, bucket_wn, bucket_ws) -> PredictionV1 | None:
        if total_n == 0:
            return None
        outcome = labels[decision]
        if outcome is None:
            return None
        bucket = buckets[decision]
        baseline = total_sum / total_n
        baseline_weighted = weight_sum / weight_n
        if mode == "wbaseline":
            state_prob, fallback = baseline_weighted, False
        elif bucket_wn[bucket] == 0:
            state_prob, fallback = baseline_weighted, True
        else:
            state_prob = (bucket_ws[bucket] + shrinkage_m * baseline_weighted) / (
                bucket_wn[bucket] + shrinkage_m
            )
            fallback = False
        return PredictionV1(
            index=decision,
            bucket=bucket,
            baseline_prob=baseline,
            state_prob=state_prob,
            outcome=outcome,
            train_n=total_n,
            bucket_train_n=bucket_n[bucket],
            state_fallback=fallback,
            baseline_weighted=baseline_weighted,
            weight_n=weight_n,
            bucket_weight_n=bucket_wn[bucket],
        )

    preds: list[PredictionV1] = []
    total_n, total_sum, weight_n, weight_sum, bucket_n, bucket_wn, bucket_ws = (
        _compute(first_decision)
    )
    pred = _make_pred(
        first_decision, total_n, total_sum, weight_n, weight_sum,
        bucket_n, bucket_wn, bucket_ws,
    )
    if pred is not None:
        preds.append(pred)
    # 之后每步：旧权重衰减 + 一个新训练起点进入（起点 = 决策日 − 期限）。
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        weight_n *= decay
        weight_sum *= decay
        for b in bucket_names:
            bucket_wn[b] *= decay
            bucket_ws[b] *= decay
        if new_start >= window - 1 and labels[new_start] is not None:
            label = labels[new_start]
            total_n += 1
            total_sum += label
            weight_n += new_weight
            weight_sum += new_weight * label
            b = buckets[new_start]
            bucket_n[b] += 1
            bucket_wn[b] += new_weight
            bucket_ws[b] += new_weight * label
        pred = _make_pred(
            decision, total_n, total_sum, weight_n, weight_sum,
            bucket_n, bucket_wn, bucket_ws,
        )
        if pred is not None:
            preds.append(pred)
    return preds
