"""概率预测实验 v6（离线实验，不进产品页面、不注册接口）。

条目 13 第六轮：检验“训练样本行情构成”（v5 报告第 8 节开放问题 1，
v3/v4 报告同题的另一条路）。v4 的门槛只量样本量，量不到“某态的训练
标签来自哪些年份/哪种行情”——2015 年初 110020 A 的 4 个极端日与
110022 A 的高估口袋都是样本量充足、标签构成单一的情形，门槛一次也
没碰到它们。本轮问的是：**某态的训练证据如果集中在单一行情里，状
态项是不是就不该被信任**。

“行情”的定义（事先固定、写死在本模块中并在报告中披露，**不做参数
扫描、不按测试集调参**）：以训练标签起点所在的**日历年**作为行情的
代理。理由事先写死：项目已有逐年失效清单与逐年表按日历年切分，日历
年是唯一不引入新参数、不依赖外部牛熊划分的现成切分。局限同样事先
写明：日历年是粗糙代理，同一日历年内也可能有牛熊切换；本轮只检验
“年份集中度”这一可度量的版本，不宣称检验了真正的牛熊构成。

集中度度量（事先固定）：对某决策日、某状态，取该态的时效加权训练
标签（权重与 v1 相同，半衰期 756 天），按起点年份分组，计算**主导
年份占比** ``dominant_year_share = 该态加权样本量中最大一年的占比``，
并附记有效年数 ``effective_years = 1 / Σ share²``（诊断用，不参与
门槛判断）。按权重而不是按标签计数——与预测器实际使用的证据一致；
标签值本身不进入集中度计算（集中度量的是“证据从哪来”，不是“证据
说什么”）。

门槛（事先固定）：``REGIME_MAX_DOMINANT_SHARE = 0.5``。若某态加权
训练标签中单一年的占比 >= 0.5（即“超过一半的有效证据来自同一年”，
单一年的证据超过全部其他年份之和），该态算“行情集中”，该日不用状
态项、回退为时效加权基准率。取值理由事先写死：0.5 是“过半”的唯一
对称分界，不是从测试集上挑的；边界语义为“达到即触发”（>=），与
v4 门槛的“低于即触发”（<）方向相反但各自写清。

检验方式（事先固定）：门槛式回退（与 v4 同构），不是限制训练样本
覆盖、不是按行情加权。理由：与 v4 可比——v4 问“样本量够不够”，v6
问“样本够不够分散”；两种门槛的触发日集合与效果可直接并排比较。

v6 只改预测器口径，不改评估口径：v6 = v2 回撤档位状态概率 + 行情
集中度门槛（不叠加 v3 混合、不叠加 v4 样本量门槛——本轮只检验行情
集中度这一个因素；与混合/样本量门槛的叠加是下一轮的干净问题）。
档位、两类标签、期限、测试起点、训练资格、比较基准（v0 无加权历史
基准率）全部与条目 8/9 一致；成绩单仍用条目 9 的 ``build_scorecard``，
技能分数仍以 v0 基准率 Brier 为分母——v6 与 v0/v1/v2/v3/v4/v5 的数
字可直接并排比较。时效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、
未改。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v6 在 110020 A 上修掉 2015 年初 4 个极端日所在的低估档
  （20%–40% 档差值明显缩小）或在 110022 A 上缩小高估口袋，同时在
  161725 A 上没有大幅丢掉优势，说明行情集中度是问题的一部分——
  行情门槛值得保留为候选；
- 若 v6 在各组上约等于 v1（触发极少、或触发日与 v1 无差别），说明年
  份集中度门槛没有增加超出 v1 的信息；
- 若 v6 比 v1 更差，说明集中度高的态恰恰有信息、门槛过激——这条路
  不成立；
- 2014 年案例单独报告：v6 是否让 110020 A 类 2014 年不再失效（当年
  Brier 是否低于基准率 Brier 0.419）。事先写明不预判：2014 年案例的
  <5% 档训练标签全来自 2009–2010 两年，主导年份占比可能低于 0.5
  （两熊市年份平分），v6 未必能修掉它；若修不掉，那正是“年份集中度”
  与“样本量”两种门槛覆盖情形不同的证据。

实现上 v6 是 v2 的薄封装：``weighted_predict_at_v6`` 对 v2 的逐项直算
结果做门槛判断（年份占比另行直算），``generate_predictions_v6`` 对
v2 的递推结果逐项做同样的判断——年份占比由一趟与 v2 递推同构的并行
递推算出（每态、每年的加权质量同步衰减、同步进入），两者口径同一，
测试守住逐点一致。本轮运行只用 ``"drawdown"`` 信号（问题针对的是回
撤档位状态项）；其余信号的门槛公式同样适用，但本轮不跑、不下结论。

日期输入：v6 必须知道每个交易日的日历年份。``dates`` 与 ``nav`` 等
长、按同一顺序排列，元素为 ``"YYYY-MM-DD"`` 形式的字符串或带
``.year`` 属性的日期对象；未传或长度不符时抛 ``ValueError``（不静默
用序号代替年份——序号年份是假数据）。

因果纪律与 v0/v1/v2/v3/v4/v5 相同：决策日 t 的预测只用 t（含）之前
的数据；训练标签必须在 t 之前已完整观测；年份占比只用决策日当天的
训练集（已是 t 之前数据的加权统计），不引入任何未来信息。改动 t 之
后的净值，t 之前（含 t）的预测必须逐点不变（测试守住）。

本轮不做 v5 报告第 8 节开放问题 2（校准映射，须事先写死拟合窗口与
更新频率并单独报告映射本身的样本外表现）与开放问题 4（门槛用于其他
信号的推广），两者留待下一轮。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v6 未达产品化门槛前不得以任何
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
    _training_starts,
    generate_predictions_v2,
    signal_state,
    weighted_predict_at_v2,
)

# 事先固定的门槛（见模块 docstring，不得运行时调参）。
# 单一年份占某态加权训练样本量的一半及以上，即算“行情集中”：
# 0.5 是“过半”的唯一对称分界，不是从测试集上挑的。
REGIME_MAX_DOMINANT_SHARE = 0.5


def _year_of(date) -> int:
    """从日期元素取日历年：``"YYYY-MM-DD"`` 字符串取前 4 位，日期对象取
    ``.year``；其余输入抛错（不猜年份）。"""
    if isinstance(date, str):
        text = date[:4]
        if len(text) == 4 and text.isdigit():
            return int(text)
        raise ValueError(f"cannot parse year from date string: {date!r}")
    year = getattr(date, "year", None)
    if isinstance(year, int):
        return year
    raise ValueError(f"cannot parse year from date: {date!r}")


def _check_dates(nav: list[float], dates) -> list[int]:
    """校验 ``dates`` 与 ``nav`` 等长，返回每下标的日历年列表。"""
    if dates is None:
        raise ValueError("v6 需要 dates（与 nav 等长的日期序列）才能计算年份集中度")
    if len(dates) != len(nav):
        raise ValueError(
            f"dates 长度 {len(dates)} 与 nav 长度 {len(nav)} 不一致"
        )
    return [_year_of(d) for d in dates]


@dataclass
class PredictionV6:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发行情集中度门槛（主导年份占比 >= 0.5）
    dominant_year_share: float  # 该态加权训练样本量中最大一年的占比（0.0–1.0）
    dominant_year: int | None  # 占比最大的年份；该态无训练样本时为 None
    effective_years: float  # 有效年数 = 1 / Σ share²；该态无训练样本时为 0.0
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float  # 时效加权基准率
    weight_n: float  # 训练集加权样本量（权重和）
    bucket_weight_n: float  # 该态加权样本量


def _regime_stats(nav: list[float], decision: int, horizon: int, label_fn,
                  signal: str, window: int, half_life: float,
                  years: list[int]) -> tuple[float, int | None, float, float]:
    """逐项直算某决策日、某状态的年份集中度（参照实现）。

    返回 ``(主导年份占比, 主导年份, 有效年数, 该态加权样本量)``。该态
    无训练样本时返回 ``(0.0, None, 0.0, 0.0)``——此时 v2 已回退为加权
    基准率，门槛不触发（没有状态项可不信任）。
    """
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return 0.0, None, 0.0, 0.0
    year_mass: dict[int, float] = {}
    bucket_wn = 0.0
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        if signal_state(nav, start, signal, window) != state:
            continue
        w = _weight(decision - start, half_life)
        bucket_wn += w
        year = years[start]
        year_mass[year] = year_mass.get(year, 0.0) + w
    if bucket_wn == 0:
        return 0.0, None, 0.0, 0.0
    dominant_year = max(year_mass, key=lambda y: year_mass[y])
    share = year_mass[dominant_year] / bucket_wn
    effective = 1.0 / sum((m / bucket_wn) ** 2 for m in year_mass.values())
    return share, dominant_year, effective, bucket_wn


def _gate(pred: PredictionV2, share: float, dominant_year: int | None,
          effective_years: float,
          max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE) -> PredictionV6:
    """把一条 v2 预测按行情集中度门槛转成 v6 预测（只用当天的量）。"""
    gated = pred.bucket_weight_n > 0 and share >= max_dominant_share
    return PredictionV6(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        dominant_year_share=share,
        dominant_year=dominant_year,
        effective_years=effective_years,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v6(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                           dates=None) -> PredictionV6 | None:
    """单个决策日的 v6 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下门槛是恒等变换（该态即全部训练集，触发时状态概率
    本就等于加权基准率）。``dates`` 必传（见模块 docstring）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    years = _check_dates(nav, dates)
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    share, dominant_year, effective, _ = _regime_stats(
        nav, decision, horizon, label_fn, signal, window, half_life, years
    )
    return _gate(base, share, dominant_year, effective, max_dominant_share)


def generate_predictions_v6(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            max_dominant_share: float = REGIME_MAX_DOMINANT_SHARE,
                            dates=None) -> list[PredictionV6]:
    """滚动原点样本外 v6 预测（与 ``weighted_predict_at_v6`` 同口径）。

    年份占比由一趟与 v2 递推同构的并行递推算出：每态、每年的加权质量
    每步同步衰减、恰好一个新训练起点进入（起点 = 决策日 − 期限），首个
    决策日直接逐项算出；``kind`` 为 ``"A"`` / ``"B"``，其余口径（期限、
    测试起点、训练资格）全部与 v2 一致。``dates`` 必传。
    """
    if kind == "A":
        horizon, label_fn = HORIZON_A_DAYS, label_positive_return
    elif kind == "B":
        horizon, label_fn = HORIZON_B_DAYS, label_drawdown_breach
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    years = _check_dates(nav, dates)
    n = len(nav)
    states = [signal_state(nav, i, signal, window) for i in range(n)]
    labels = [label_fn(nav, i, horizon) for i in range(n)]
    last_testable = n - 1 - horizon
    first_decision = max(test_start, window - 1)
    if first_decision > last_testable:
        return []
    decay = 0.5 ** (1.0 / half_life)
    new_weight = 0.5 ** (horizon / half_life)

    def _compute_year_mass(decision: int) -> dict[tuple[str, int], float]:
        """直接逐项算出该决策日每态、每年的加权质量（只用于首个决策日）。"""
        mass: dict[tuple[str, int], float] = {}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None or states[start] is None:
                continue
            w = _weight(decision - start, half_life)
            key = (states[start], years[start])
            mass[key] = mass.get(key, 0.0) + w
        return mass

    def _stats_for(mass: dict[tuple[str, int], float], state: str | None):
        """从加权质量表取某态的（主导年份占比，主导年份，有效年数）。"""
        if state is None:
            return 0.0, None, 0.0
        total = 0.0
        per_year: dict[int, float] = {}
        for (s, y), w in mass.items():
            if s == state:
                total += w
                per_year[y] = per_year.get(y, 0.0) + w
        if total == 0:
            return 0.0, None, 0.0
        dominant_year = max(per_year, key=lambda y: per_year[y])
        share = per_year[dominant_year] / total
        effective = 1.0 / sum((m / total) ** 2 for m in per_year.values())
        return share, dominant_year, effective

    # 先算出全部决策日的年份占比，再与 v2 的递推输出按 index 对齐。
    stats: dict[int, tuple[float, int | None, float]] = {}
    mass = _compute_year_mass(first_decision)
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
            key = (states[new_start], years[new_start])
            mass[key] = mass.get(key, 0.0) + new_weight
        stats[decision] = _stats_for(mass, states[decision])
    v2_preds = generate_predictions_v2(
        nav, kind, signal, window, test_start, half_life, shrinkage_m
    )
    return [
        _gate(pred, *stats[pred.index], max_dominant_share)
        for pred in v2_preds
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "REGIME_MAX_DOMINANT_SHARE",
    "PredictionV6",
    "generate_predictions_v6",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v6",
]
