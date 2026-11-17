"""概率预测实验 v9（离线实验，不进产品页面、不注册接口）。

条目 13 第九轮：检验“训练样本多年一边倒”（v8 报告第 9 节开放问题 2
的第一条路）。v8 的直接证据是：110022 A 的高估口袋（80%–100% 校准
档，n=62，预测 0.81、实际 0.02，差 +0.80）错不在“态比全局更极端”
——口袋 62 天的态内加权正标签占比 0.805–0.848，而同一天的时效加权
基准率是 0.73–0.81，相对差距只有 0.043–0.074。态与全局在当时都高度
为正、而未来变了：2015–2017 年牛市的标签把加权基准率本身抬到了
0.75 上下。v7 报告把口袋的诊断修正为“八成以上一边倒、且持续多年”；
v6 的年份集中度门槛量的是“证据从哪几年来的”，v7 的绝对极性门槛量
的是“标签总体一边倒多少”，两者都量不到“**这几年的标签是不是一年
接一年地同向**”。本轮问的是：**某态的训练标签如果在最近连续几年里
一年接一年地一边倒，状态项是不是就不该被信任**。

“多年一边倒”的定义（事先固定、写死在本模块中并在报告中披露，**不
做参数扫描、不按测试集调参**）：对某决策日、某状态，取该态的时效加
权训练标签（权重与 v1 相同，半衰期 756 天），按训练起点所在的日历
年分组（与 v6 同一切分）；某年算“一年证据”当且仅当该态在该年里有
至少 ``MIN_YEAR_N`` 个训练标签（未加权计数）；取最近的
``WINDOW_YEARS`` 个有证据的年份，逐年算时效加权正标签占比；若这几
年的占比**全部** >= ``ONE_SIDED_SHARE``（全部强烈为正）或**全部**
<= ``1 - ONE_SIDED_SHARE``（全部强烈为负），该态算“多年一边倒”，
该日不用状态项、回退为时效加权基准率。按权重而不是按标签计数算逐年
占比——与预测器实际使用的证据一致；按年计数只决定“某年够不够格作
为一年证据”，不参与占比计算。

常数（事先固定，理由与测试集无关）：
- ``WINDOW_YEARS = 3``： “多年”的最小值——多于一年、跨越至少两个
  年份边界；一年是单年行情、两年是一段行情，只有三年才够格叫“多
  年”。取最近的 3 个有证据的年份（不要求连续日历——某年标签不足
  30 个时跳过该年、往前顺延；“最近”按日历年降序）。
- ``ONE_SIDED_SHARE = 0.8``： “八成以上一边倒”的对称分界（4/5 强
  多数）；v7 报告修正后的诊断原文即“八成以上一边倒、且持续多年”，
  本轮把“持续多年”形式化为逐年检验。这不是把 v7 的 0.9 下调到
  0.85 去贴线——0.8 是独立的常规分界，且本轮还要求“连续 3 年各自”
  一边倒，比 v7 的单年聚合条件更严，是不同的检验；v8 报告第 9 节
  禁止下调到 0.85“刚好抓住”口袋的禁令仍有效：0.8 下若口袋的某年
  占比低于 0.8，结论就是“多年门槛修不掉这个口袋”，而不是再调低
  门槛。
- ``MIN_YEAR_N = 30``：借用成绩单 ``MIN_BUCKET_N = 30`` 的已有证
  据规则（与 v4 借用方式相同）；一年里该态训练标签少于 30 个不算
  “一年证据”，不足 3 个有证据的年份时门槛不触发（没有多年一边倒
  的肯定证据，就不替状态项做决定）。
- 边界语义为“达到即触发”（>= 0.8 / <= 0.2），与 v6/v7/v8 门槛的
  方向一致。

检验方式（事先固定）：门槛式回退（与 v4/v6/v7/v8 同构），不是限制
训练样本覆盖、不是按标签加权。理由：与 v4/v6/v7/v8 可比——v4 问
“样本量够不够”，v6 问“样本够不够分散”，v7 问“标签够不够一边倒”，
v8 问“标签构成与全局差得够不够远”，v9 问“标签是不是一年接一年地
一边倒”；五种门槛的触发日集合与效果可直接并排比较。

v9 只改预测器口径，不改评估口径：v9 = v2 回撤档位状态概率 + 多年
一边倒门槛（不叠加 v3 混合、不叠加 v4 样本量门槛、不叠加 v6 年份集
中度门槛、不叠加 v7 绝对极性门槛、不叠加 v8 相对极性门槛——本轮只
检验多年一边倒这一个因素；与混合/样本量门槛/年份门槛/绝对极性门槛/
相对极性门槛的叠加是下一轮的干净问题）。档位、两类标签、期限、测试
起点、训练资格、比较基准（v0 无加权历史基准率）全部与条目 8/9 一致；
成绩单仍用条目 9 的 ``build_scorecard``，技能分数仍以 v0 基准率
Brier 为分母——v9 与 v0/v1/v2/v3/v4/v5/v6/v7/v8 的数字可直接并排比较。
时效加权半衰期 756 天、收缩伪计数 50 从 v1 继承、未改。

解读规则同样事先写死（在看到任何真实数据结果之前）：
- 若 v9 在 110022 A 上缩小高估口袋（80%–100% 档的 n 或差值明显缩小）
  和/或在 110020 A 上修掉 2014 年案例，同时在 161725 A 上没有大幅丢
  掉优势，说明多年一边倒是问题的一部分——多年门槛值得保留为候选；
- 若 v9 在各组上约等于 v1（触发极少、或触发日与 v1 无差别），说明多
  年一边倒门槛没有增加超出 v1 的信息；
- 若 v9 比 v1 更差，说明一年接一年一边倒的态恰恰有信息、门槛过激——
  这条路不成立；
- 2014 年案例单独报告：v9 是否让 110020 A 类 2014 年不再失效（当年
  Brier 是否低于基准率 Brier 0.419）。事先写明**不预判修掉**：按 v0
  报告的诊断，2014 年案例的 <5% 档训练标签全来自 2009–2010 两年，
  只有两个有证据的年份，3 年窗口按定义大概率不触发；若修不掉，那正
  是“多年”定义（3 年）与“样本量/年份集中度/绝对极性”三种门槛覆盖
  情形不同的证据，不得事后把窗口改成 2 年去“补救”；
- 2015 年初 4 个极端日单独报告：v6 说它们的主导年份是 2013（占比
  0.62–0.64），v7 说它们的多数占比是 0.93–0.97；v9 能否抓住它们取决
  于最近 3 个有证据的年份是否各自强烈为负——事先不预判，只如实记录
  触发与否与逐年占比；
- 近退化组（217022 A：实际 99.82% 为正）事先说明：该组标签在几乎每
  一年里都是一边倒的，门槛预计在多数决策日触发，v9 约等于加权基准率；
  Brier 差别全在千分位量级，不得把其中任何一个读作“预测变好了”；
- B 类组事先说明：事件本身高频（实际发生率 79%–87%）时，多数年份的
  逐年占比天然偏高，多年门槛可能在 B 类上大面积触发；若 v9 在 B 类上
  比 v1 更差，说明门槛分不清“事件高频”与“单一行情扭曲”——这是
  v7 的同一局限换了一种量法，不是新答案。

实现上 v9 是 v2 的薄封装：``weighted_predict_at_v9`` 对 v2 的逐项直算
结果做门槛判断（逐年占比另行直算），``generate_predictions_v9`` 对
v2 的递推结果逐项做同样的判断——逐年占比由一趟与 v2/v6 递推同构的
并行递推算出（每态、每年的加权质量与加权正标签质量同步衰减、同步进
入；逐年计数只增不减，与训练集只增不减一致；首个决策日直接逐项算
出），两者口径同一，测试守住逐点一致。本轮运行只用 ``"drawdown"``
信号（问题针对的是回撤档位状态项）；其余信号的门槛公式同样适用，但
本轮不跑、不下结论。

日期输入：v9 必须知道每个交易日的日历年份。``dates`` 与 ``nav`` 等
长、按同一顺序排列，元素为 ``"YYYY-MM-DD"`` 形式的字符串或带
``.year`` 属性的日期对象；未传或长度不符时抛 ``ValueError``（不静默
用序号代替年份——序号年份是假数据）。

因果纪律与 v0/v1/v2/v3/v4/v5/v6/v7/v8 相同：决策日 t 的预测只用 t（含）
之前的数据；训练标签必须在 t 之前已完整观测；逐年占比只用决策日当天
的训练集（已是 t 之前数据的加权统计），不引入任何未来信息。改动 t 之
后的净值，t 之前（含 t）的预测必须逐点不变（测试守住）。

本轮不做 v8 报告第 9 节开放问题 1（更松的相对定义，须事先写死新定义
与门槛并给出独立于测试集的事前依据，尤其不得从“最大差距 0.4191”
反推门槛）、开放问题 3（校准映射，须事先写死拟合窗口与更新频率并单
独报告映射本身的样本外表现）、开放问题 4（门槛叠加的解读规则，须另
起版本号；叠加之前须先回答“为什么 B 类上门槛总犯错”），三者留待下
一轮；也不做“按净值趋势划分牛熊段”的另一条行情定义，那是后续轮次
的干净问题。

文案红线：本模块输出的只是“概率预测/前景概率”，任何对外呈现都必须
同页附成绩单与“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。v9 未达产品化门槛前不得以任何
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
from experiments.forecast_scorecard import MIN_BUCKET_N
from experiments.forecast_v1 import HALF_LIFE_DAYS, SHRINKAGE_M, _weight
from experiments.forecast_v2 import (
    SIGNAL_DRAWDOWN,
    SIGNALS,
    PredictionV2,
    _states_for_signal,
    _training_starts,
    generate_predictions_v2,
    signal_state,
    weighted_predict_at_v2,
)

# 事先固定的门槛（见模块 docstring，不得运行时调参）。
# “多年”= 最近 3 个有证据的年份；“一边倒”= 逐年占比八成以上同向；
# 一年够格作证据须该态在该年里至少有 30 个训练标签（借用成绩单规则）。
WINDOW_YEARS = 3
ONE_SIDED_SHARE = 0.8
MIN_YEAR_N = MIN_BUCKET_N


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
        raise ValueError("v9 需要 dates（与 nav 等长的日期序列）才能计算逐年占比")
    if len(dates) != len(nav):
        raise ValueError(
            f"dates 长度 {len(dates)} 与 nav 长度 {len(nav)} 不一致"
        )
    return [_year_of(d) for d in dates]


@dataclass
class PredictionV9:
    index: int
    bucket: str  # 信号状态标签（与 v2 相同）
    signal: str
    baseline_prob: float  # v0 无加权历史基准率（比较基准，与条目 8/9 一致）
    state_prob: float  # 门槛后状态概率：未触发门槛时 = v2 状态概率；触发时 = 加权基准率
    ungated_state_prob: float  # v2 的状态概率（门槛前）
    gated: bool  # 该日是否触发多年一边倒门槛（最近 3 个有证据的年份逐年占比全同向超八成）
    years_checked: tuple[int, ...] = ()  # 本次检验的年份（最近的有证据年份，降序）；不足 3 年时为空
    year_pos_fracs: tuple[float, ...] = ()  # 与 years_checked 对应的逐年时效加权正标签占比
    year_counts: tuple[int, ...] = ()  # 与 years_checked 对应的逐年训练标签数（未加权）
    direction: int = 0  # +1：最近 3 年全部强烈为正；-1：全部强烈为负；0：不一边倒或证据不足
    outcome: int = 0
    train_n: int = 0
    bucket_train_n: int = 0
    state_fallback: bool = False  # 该态训练样本为 0 时 v2 已回退为加权基准率（与 v2 一致）
    baseline_weighted: float = 0.0  # 时效加权基准率
    weight_n: float = 0.0  # 训练集加权样本量（权重和）
    bucket_weight_n: float = 0.0  # 该态加权样本量


def _multiyear_stats(nav: list[float], decision: int, horizon: int, label_fn,
                     signal: str, window: int, half_life: float,
                     years: list[int],
                     window_years: int = WINDOW_YEARS,
                     one_sided_share: float = ONE_SIDED_SHARE,
                     min_year_n: int = MIN_YEAR_N,
                     ) -> tuple[tuple[int, ...], tuple[float, ...],
                                tuple[int, ...], int]:
    """逐项直算某决策日、某状态的多年一边倒统计（参照实现）。

    返回 ``(检验年份, 逐年正标签占比, 逐年标签数, 方向)``。方向 +1 /
    -1 表示最近 ``window_years`` 个有证据的年份逐年占比全部 >= 门槛 /
    全部 <= 1 - 门槛；有证据的年份不足 ``window_years`` 个、或该态无训
    练样本时返回 ``((), (), (), 0)``——此时门槛不触发（没有多年一边倒
    的肯定证据）。
    """
    state = signal_state(nav, decision, signal, window)
    if state is None:
        return (), (), (), 0
    # 每年：[加权质量，加权正标签质量，未加权计数]。
    per_year: dict[int, list[float]] = {}
    for start in _training_starts(decision, horizon, window):
        label = label_fn(nav, start, horizon)
        if label is None:
            continue
        if signal_state(nav, start, signal, window) != state:
            continue
        w = _weight(decision - start, half_life)
        entry = per_year.setdefault(years[start], [0.0, 0.0, 0.0])
        entry[0] += w
        entry[1] += w * label
        entry[2] += 1
    qualifying = sorted(
        (y for y, entry in per_year.items() if entry[2] >= min_year_n),
        reverse=True,
    )[:window_years]
    if len(qualifying) < window_years:
        return (), (), (), 0
    fracs = tuple(per_year[y][1] / per_year[y][0] for y in qualifying)
    counts = tuple(int(per_year[y][2]) for y in qualifying)
    if all(f >= one_sided_share for f in fracs):
        direction = 1
    elif all(f <= 1.0 - one_sided_share for f in fracs):
        direction = -1
    else:
        direction = 0
    return tuple(qualifying), fracs, counts, direction


def _gate(pred: PredictionV2,
          years_checked: tuple[int, ...],
          year_pos_fracs: tuple[float, ...],
          year_counts: tuple[int, ...],
          direction: int) -> PredictionV9:
    """把一条 v2 预测按多年一边倒门槛转成 v9 预测（只用当天的量）。"""
    gated = pred.bucket_weight_n > 0 and direction != 0
    return PredictionV9(
        index=pred.index,
        bucket=pred.bucket,
        signal=pred.signal,
        baseline_prob=pred.baseline_prob,
        state_prob=pred.baseline_weighted if gated else pred.state_prob,
        ungated_state_prob=pred.state_prob,
        gated=gated,
        years_checked=years_checked,
        year_pos_fracs=year_pos_fracs,
        year_counts=year_counts,
        direction=direction,
        outcome=pred.outcome,
        train_n=pred.train_n,
        bucket_train_n=pred.bucket_train_n,
        state_fallback=pred.state_fallback,
        baseline_weighted=pred.baseline_weighted,
        weight_n=pred.weight_n,
        bucket_weight_n=pred.bucket_weight_n,
    )


def weighted_predict_at_v9(nav: list[float], decision: int, horizon: int, label_fn,
                           signal: str = SIGNAL_DRAWDOWN,
                           window: int = WINDOW_DAYS,
                           half_life: float = HALF_LIFE_DAYS,
                           shrinkage_m: float = SHRINKAGE_M,
                           window_years: int = WINDOW_YEARS,
                           one_sided_share: float = ONE_SIDED_SHARE,
                           min_year_n: int = MIN_YEAR_N,
                           dates=None) -> PredictionV9 | None:
    """单个决策日的 v9 预测（逐项直算参照实现）。

    ``signal`` 为 v2 的四种信号之一；本轮运行只用 ``"drawdown"``。
    ``"none"`` 信号下门槛不是恒等变换（该态即全部训练集，逐年占比是全
    局逐年占比；触发时状态概率本就等于加权基准率，所以状态概率仍与
    v2 相同）。``dates`` 必传（见模块 docstring）。
    """
    if signal not in SIGNALS:
        raise ValueError(f"unknown signal: {signal!r}")
    years = _check_dates(nav, dates)
    base = weighted_predict_at_v2(
        nav, decision, horizon, label_fn, signal, window, half_life, shrinkage_m
    )
    if base is None:
        return None
    years_checked, fracs, counts, direction = _multiyear_stats(
        nav, decision, horizon, label_fn, signal, window, half_life, years,
        window_years, one_sided_share, min_year_n,
    )
    return _gate(base, years_checked, fracs, counts, direction)


def generate_predictions_v9(nav: list[float], kind: str,
                            signal: str = SIGNAL_DRAWDOWN,
                            window: int = WINDOW_DAYS,
                            test_start: int = TEST_START_INDEX,
                            half_life: float = HALF_LIFE_DAYS,
                            shrinkage_m: float = SHRINKAGE_M,
                            window_years: int = WINDOW_YEARS,
                            one_sided_share: float = ONE_SIDED_SHARE,
                            min_year_n: int = MIN_YEAR_N,
                            dates=None) -> list[PredictionV9]:
    """滚动原点样本外 v9 预测（与 ``weighted_predict_at_v9`` 同口径）。

    逐年占比由一趟与 v2/v6 递推同构的并行递推算出：每态、每年的加权质
    量与加权正标签质量每步同步衰减、恰好一个新训练起点进入（起点 =
    决策日 − 期限），逐年计数只增不减（训练集只增不减），首个决策日直
    接逐项算出；``kind`` 为 ``"A"`` / ``"B"``，其余口径（期限、测试起
    点、训练资格）全部与 v2 一致。``dates`` 必传。
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

    def _compute_year_stats(decision: int) -> dict[tuple[str, int], list[float]]:
        """直接逐项算出该决策日每态、每年的 [加权质量，加权正质量，计数]
        （只用于首个决策日）。"""
        stats: dict[tuple[str, int], list[float]] = {}
        for start in _training_starts(decision, horizon, window):
            label = labels[start]
            if label is None or states[start] is None:
                continue
            w = _weight(decision - start, half_life)
            key = (states[start], years[start])
            entry = stats.setdefault(key, [0.0, 0.0, 0.0])
            entry[0] += w
            entry[1] += w * label
            entry[2] += 1
        return stats

    def _stats_for(stats: dict[tuple[str, int], list[float]], state: str | None):
        """从逐年表取某态的（检验年份，逐年占比，逐年计数，方向）。"""
        if state is None:
            return (), (), (), 0
        per_year = {
            y: entry for (s, y), entry in stats.items() if s == state
        }
        qualifying = sorted(
            (y for y, entry in per_year.items() if entry[2] >= min_year_n),
            reverse=True,
        )[:window_years]
        if len(qualifying) < window_years:
            return (), (), (), 0
        fracs = tuple(per_year[y][1] / per_year[y][0] for y in qualifying)
        counts = tuple(int(per_year[y][2]) for y in qualifying)
        if all(f >= one_sided_share for f in fracs):
            direction = 1
        elif all(f <= 1.0 - one_sided_share for f in fracs):
            direction = -1
        else:
            direction = 0
        return tuple(qualifying), fracs, counts, direction

    # 先算出全部决策日的多年统计，再与 v2 的递推输出按 index 对齐。
    stats: dict[int, tuple[tuple[int, ...], tuple[float, ...],
                          tuple[int, ...], int]] = {}
    year_stats = _compute_year_stats(first_decision)
    stats[first_decision] = _stats_for(year_stats, states[first_decision])
    for decision in range(first_decision + 1, last_testable + 1):
        new_start = decision - horizon
        for entry in year_stats.values():
            entry[0] *= decay
            entry[1] *= decay
        if (
            new_start >= window - 1
            and labels[new_start] is not None
            and states[new_start] is not None
        ):
            key = (states[new_start], years[new_start])
            entry = year_stats.setdefault(key, [0.0, 0.0, 0.0])
            entry[0] += new_weight
            entry[1] += new_weight * labels[new_start]
            entry[2] += 1
        stats[decision] = _stats_for(year_stats, states[decision])
    v2_preds = generate_predictions_v2(
        nav, kind, signal, window, test_start, half_life, shrinkage_m
    )
    return [
        _gate(pred, *stats[pred.index]) for pred in v2_preds
    ]


# 供测试与运行脚本复用的标签函数（与 v2 相同口径）。
__all__ = [
    "MIN_YEAR_N",
    "ONE_SIDED_SHARE",
    "WINDOW_YEARS",
    "PredictionV9",
    "generate_predictions_v9",
    "label_drawdown_breach",
    "label_positive_return",
    "weighted_predict_at_v9",
]
