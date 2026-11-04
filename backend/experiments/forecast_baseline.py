"""概率基线实验 v0（离线实验，不进产品页面、不注册接口）。

定位（按 BACKLOG 条目 7 规格，执行时不许放大）：只做两类“前景概率”，
并公开预测器自己的样本外成绩单；不做点位/涨跌预测，不做买卖推荐。

- 预测对象 A：未来 6 个月（126 个交易日）累计净值收益 > 0 的概率。
- 预测对象 B：未来 12 个月（252 个交易日）内最大回撤 <= -10%
  （即“跌超 10%”）的概率；回撤口径：决策日净值作为起始高点，
  未来窗口内相对滚动高点的最大跌幅。
- 预测器 v0 只用两类信号：
  1. 历史基准率：决策日之前已完成标签的全部历史窗口的无条件频率。
  2. 状态信号：决策日净值相对近 250 个交易日高点的回撤档位
     （<5% / 5%–10% / >10%，含边界：回撤绝对值 <=10% 归入 5%–10% 档），
     该档的历史条件频率即该档预测概率。
- 因果纪律：决策日 t 的预测只用 t（含）之前的数据；训练标签必须
  在 t 之前已完整观测（A 类训练起点 <= t-126，B 类起点 <= t-252）。
  改动 t 之后的净值，t 之前（含 t）的预测必须逐点不变。
- 样本外切分：滚动原点（expanding window）；测试起点为历史满 5 年后
  的第一个决策日，这里以 5*252=1260 个交易日近似 5 年（与条目 7 的
  252 日/年换算一致）；测试集只含标签已完整观测的决策日。
- 本模块只用纯 Python 列表运算，不依赖 pandas、不调用任何产品服务，
  与产品代码隔离；输入为按日期升序排列的累计净值列表。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露。
"""

from __future__ import annotations

from dataclasses import dataclass

WINDOW_DAYS = 250
HORIZON_A_DAYS = 126
HORIZON_B_DAYS = 252
TEST_START_INDEX = 5 * 252  # 1260，历史满 5 年的近似起点
DRAWDOWN_THRESHOLD = 0.10

BUCKET_LT5 = "<5%"
BUCKET_5_10 = "5%-10%"
BUCKET_GT10 = ">10%"


def drawdown_at(nav: list[float], index: int, window: int = WINDOW_DAYS) -> float:
    """决策日净值相对近 ``window`` 个交易日（含当日）高点的回撤（<=0）。"""
    start = max(0, index - window + 1)
    peak = max(nav[start : index + 1])
    return nav[index] / peak - 1.0


def bucket_for_drawdown(drawdown: float) -> str:
    """回撤档位：绝对值 <5% / 5%–10%（含 10%）/ >10%。”
    drawdown 本身为负数或 0。"""
    magnitude = abs(drawdown)
    if magnitude < 0.05:
        return BUCKET_LT5
    if magnitude <= 0.10:
        return BUCKET_5_10
    return BUCKET_GT10


def label_positive_return(nav: list[float], index: int, horizon: int = HORIZON_A_DAYS):
    """A 类标签：未来 ``horizon`` 个交易日后收益 > 0 为 1，否则为 0；
    未来数据不足时返回 None（该起点不得进入训练或测试集）。"""
    target = index + horizon
    if target >= len(nav):
        return None
    return 1 if nav[target] > nav[index] else 0


def label_drawdown_breach(nav: list[float], index: int, horizon: int = HORIZON_B_DAYS,
                          threshold: float = DRAWDOWN_THRESHOLD):
    """B 类标签：未来 ``horizon`` 个交易日内最大回撤 <= -threshold 为 1，
    否则为 0；未来数据不足时返回 None。滚动高点从决策日净值起算。"""
    end = index + horizon
    if end >= len(nav):
        return None
    peak = nav[index]
    worst = 0.0
    for value in nav[index : end + 1]:
        if value > peak:
            peak = value
        dd = value / peak - 1.0
        if dd < worst:
            worst = dd
    return 1 if worst <= -threshold else 0


@dataclass
class Prediction:
    index: int
    bucket: str
    baseline_prob: float
    state_prob: float
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该档训练样本为 0 时状态概率回退为基准率


def _training_labels(nav, decision, horizon, label_fn, window=WINDOW_DAYS):
    """决策日之前已完成标签的训练起点：起点需有完整回撤窗口
    （index >= window-1）且标签在决策日之前已完整观测
    （起点 <= decision - horizon）。"""
    out = []
    for start in range(window - 1, decision - horizon + 1):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        out.append((start, label))
    return out


def predict_at(nav: list[float], decision: int, horizon: int, label_fn,
               window: int = WINDOW_DAYS) -> Prediction | None:
    """单个决策日的基准率 + 回撤档位条件频率预测；训练集为空返回 None。"""
    if decision < window - 1:
        return None
    training = _training_labels(nav, decision, horizon, label_fn, window)
    if not training:
        return None
    outcome = label_fn(nav, decision, horizon)
    if outcome is None:
        return None
    bucket = bucket_for_drawdown(drawdown_at(nav, decision, window))
    baseline = sum(label for _, label in training) / len(training)
    same_bucket = [
        label
        for start, label in training
        if bucket_for_drawdown(drawdown_at(nav, start, window)) == bucket
    ]
    if same_bucket:
        state_prob = sum(same_bucket) / len(same_bucket)
        fallback = False
    else:
        state_prob = baseline
        fallback = True
    return Prediction(
        index=decision,
        bucket=bucket,
        baseline_prob=baseline,
        state_prob=state_prob,
        outcome=outcome,
        train_n=len(training),
        bucket_train_n=len(same_bucket),
        state_fallback=fallback,
    )


def generate_predictions(nav: list[float], kind: str,
                         window: int = WINDOW_DAYS,
                         test_start: int = TEST_START_INDEX) -> list[Prediction]:
    """滚动原点样本外预测。kind 为 "A"（6 个月为正）或 "B"（12 个月跌超 10%）。
    测试集只含标签已完整观测的决策日。

    实现上与 ``predict_at`` 同口径，但用档位与标签的前缀和把每决策日
    的训练统计降为 O(1)（逐决策重算在 4000 天序列上是 O(N^2 * 窗口)，
    真实数据运行不可接受）；``predict_at`` 保留为逐项直算的参照实现，
    两者在同一序列上的抽查一致性由运行脚本核对。
    """
    if kind == "A":
        horizon, label_fn = HORIZON_A_DAYS, label_positive_return
    elif kind == "B":
        horizon, label_fn = HORIZON_B_DAYS, label_drawdown_breach
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    n = len(nav)
    buckets = [bucket_for_drawdown(drawdown_at(nav, i, window)) for i in range(n)]
    labels = [label_fn(nav, i, horizon) for i in range(n)]
    # 前缀和：count[i]/sum_[i] 为训练起点 s in [window-1, i] 的统计。
    count = [0] * n
    total = [0] * n
    bucket_count = {b: [0] * n for b in (BUCKET_LT5, BUCKET_5_10, BUCKET_GT10)}
    bucket_sum = {b: [0] * n for b in (BUCKET_LT5, BUCKET_5_10, BUCKET_GT10)}
    running_c = running_s = 0
    running_bc = {b: 0 for b in bucket_count}
    running_bs = {b: 0 for b in bucket_count}
    for i in range(n):
        if i >= window - 1 and labels[i] is not None:
            running_c += 1
            running_s += labels[i]
            running_bc[buckets[i]] += 1
            running_bs[buckets[i]] += labels[i]
        count[i] = running_c
        total[i] = running_s
        for b in bucket_count:
            bucket_count[b][i] = running_bc[b]
            bucket_sum[b][i] = running_bs[b]
    preds: list[Prediction] = []
    last_testable = n - 1 - horizon
    for decision in range(max(test_start, window - 1), last_testable + 1):
        cutoff = decision - horizon
        if cutoff < window - 1 or count[cutoff] == 0:
            continue
        outcome = labels[decision]
        if outcome is None:
            continue
        bucket = buckets[decision]
        baseline = total[cutoff] / count[cutoff]
        bc = bucket_count[bucket][cutoff]
        if bc:
            state_prob, fallback = bucket_sum[bucket][cutoff] / bc, False
        else:
            state_prob, fallback = baseline, True
        preds.append(
            Prediction(
                index=decision,
                bucket=bucket,
                baseline_prob=baseline,
                state_prob=state_prob,
                outcome=outcome,
                train_n=count[cutoff],
                bucket_train_n=bc,
                state_fallback=fallback,
            )
        )
    return preds


def brier_score(preds: list[Prediction], use_state: bool = True) -> float | None:
    """Brier 分数：预测概率与实际 0/1 的均方误差；空集返回 None。"""
    if not preds:
        return None
    total = 0.0
    for pred in preds:
        prob = pred.state_prob if use_state else pred.baseline_prob
        total += (prob - pred.outcome) ** 2
    return total / len(preds)


def non_overlapping_count(preds: list[Prediction], horizon: int) -> int:
    """不重叠 block 数近似：从第一个测试决策日起，每隔 horizon 取一个起点。
    与滚动起点数并列报告，不得用滚动数做显著性样本量。"""
    if not preds:
        return 0
    first = preds[0].index
    last = preds[-1].index
    return (last - first) // horizon + 1
