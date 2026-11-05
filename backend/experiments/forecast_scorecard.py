"""预测评估框架（条目 9，离线实验，不进产品页面、不注册接口）。

给条目 8 的概率基线实验补齐“成绩单”口径：校准分档表、Brier 相对
基准率的技能分数、逐年失效清单、证据不足规则。只做评估，不改预测器
口径；输入为条目 8 的 ``Prediction`` 列表（或同样字段的替身对象），
与产品代码隔离。

写死的阈值（条目 7 提案，条目 9 在此写死并在报告中披露，不得运行时
调参）：
- ``MIN_OUT_OF_SAMPLE_N = 100``：样本外预测数低于 100，整体结论只能
  写“证据不足”。
- ``MIN_HISTORY_TRADING_DAYS = 1260``：基金历史不足 5 年（5×252 个交易日
  近似），整体结论只能写“证据不足”。
- ``MIN_BUCKET_N = 30``：某回撤档位样本外数低于 30，该档的结论只能写
  “证据不足”；从未出现的档位（n=0）记为“未出现”，不下结论。

关于 2014 年案例（110020 A 类 Brier 恰 1.0）的处理决定（条目 8 报告
交接给条目 9 的开放问题）：只披露，不另加数值规则。理由：档位训练
样本即使过 30 也可能全部来自单一行情（当年 <5% 档 37 个训练样本全来自
2009–2010 年熊市）；任何“训练年份跨度”阈值都会是又一个可调参数，
与本项目“不开放任意参数扫描、防数据窥探”的产品决策相冲突。代替做法：
成绩单报告中必须逐档列出最终决策日的档位训练样本数，并把 2014 年案例
作为已核实的 regime 集中警告写入报告；原型文案（条目 11）不得引用
单档结论而不提这一局限。

文案红线：本模块输出的只是“概率预测/前景概率”的成绩单，任何对外
呈现都必须同页附“概率不是保证、历史校准不代表未来必然如此”的披露；
禁止点位预测、涨跌断言、买卖推荐表述。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.forecast_baseline import brier_score, non_overlapping_count

# 写死的证据不足阈值（见模块 docstring，不得运行时调参）。
MIN_OUT_OF_SAMPLE_N = 100
MIN_HISTORY_TRADING_DAYS = 5 * 252  # 1260，历史满 5 年的近似
MIN_BUCKET_N = 30

# 校准分档：预测概率分 5 档，下界含入、上界不含，1.0 归入最后一档。
CALIBRATION_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
CALIBRATION_LABELS = ("0%–20%", "20%–40%", "40%–60%", "60%–80%", "80%–100%")


def calibration_bucket_index(prob: float) -> int:
    """预测概率所属的校准档下标（0–4）；1.0 归入最后一档。"""
    if prob <= 0.0:
        return 0
    if prob >= 1.0:
        return 4
    for i in range(len(CALIBRATION_EDGES) - 1):
        if CALIBRATION_EDGES[i] <= prob < CALIBRATION_EDGES[i + 1]:
            return i
    return 4


@dataclass
class CalibrationRow:
    label: str
    n: int
    mean_pred: float | None  # 该档平均预测概率；n=0 时为 None
    actual_rate: float | None  # 该档实际发生频率；n=0 时为 None
    gap: float | None  # mean_pred - actual_rate；n=0 时为 None


def calibration_table(preds, use_state: bool = True) -> list[CalibrationRow]:
    """校准分档表：5 档固定列出，空档保留 n=0、其余字段为 None。"""
    sums = [0.0] * 5
    outcomes = [0] * 5
    counts = [0] * 5
    for pred in preds:
        prob = pred.state_prob if use_state else pred.baseline_prob
        idx = calibration_bucket_index(prob)
        sums[idx] += prob
        outcomes[idx] += pred.outcome
        counts[idx] += 1
    rows = []
    for i, label in enumerate(CALIBRATION_LABELS):
        if counts[i] == 0:
            rows.append(CalibrationRow(label, 0, None, None, None))
        else:
            mean_pred = sums[i] / counts[i]
            actual_rate = outcomes[i] / counts[i]
            rows.append(
                CalibrationRow(label, counts[i], mean_pred, actual_rate, mean_pred - actual_rate)
            )
    return rows


def skill_score(state_brier: float | None, baseline_brier: float | None) -> float | None:
    """Brier 技能分数 = 1 − 状态 Brier / 基准率 Brier。

    任一 Brier 为 None（空集），或基准率 Brier 为 0（退化：双方恒为 0，
    如 217022 B 类事件从未发生），技能分数无法计算，返回 None——
    这不是“满分”，是问题本身在该样本上没有区分度。
    """
    if state_brier is None or baseline_brier is None or baseline_brier == 0:
        return None
    return 1.0 - state_brier / baseline_brier


@dataclass
class YearlyRow:
    year: int
    n: int
    brier_state: float | None
    brier_baseline: float | None
    state_worse: bool  # 当年状态 Brier 严格大于基准率 Brier 即为失效年份


def yearly_table(preds, years: list[int]) -> list[YearlyRow]:
    """逐年 Brier 表。``years`` 与 ``preds`` 等长、按决策日顺序对应年份。

    失效年份定义：当年状态 Brier 严格大于基准率 Brier。两者相等（含
    均为 0 的退化年份）不算失效，只是不分优劣。
    """
    if len(preds) != len(years):
        raise ValueError("preds and years must have the same length")
    grouped: dict[int, list] = {}
    for pred, year in zip(preds, years):
        grouped.setdefault(year, []).append(pred)
    rows = []
    for year in sorted(grouped):
        group = grouped[year]
        state = brier_score(group, use_state=True)
        baseline = brier_score(group, use_state=False)
        worse = (
            state is not None
            and baseline is not None
            and state > baseline
        )
        rows.append(YearlyRow(year, len(group), state, baseline, worse))
    return rows


def failure_years(rows: list[YearlyRow]) -> list[int]:
    """失效年份清单：逐年表中状态差于基准率的年份（升序）。"""
    return [row.year for row in rows if row.state_worse]


def bucket_verdict(n: int) -> str:
    """单档证据 verdict：``ok`` / ``insufficient`` / ``absent``。

    n=0 为“未出现”（该档在样本外从未进入，不下结论，不是证据不足）；
    1<=n<30 为“证据不足”；n>=30 为可报该档数字。
    """
    if n == 0:
        return "absent"
    if n < MIN_BUCKET_N:
        return "insufficient"
    return "ok"


@dataclass
class EvidenceAssessment:
    verdict: str  # "sufficient" 或 "insufficient"
    reasons: list[str] = field(default_factory=list)
    bucket_verdicts: dict[str, str] = field(default_factory=dict)


def assess_evidence(preds, history_days: int, bucket_ns: dict[str, int] | None = None) -> EvidenceAssessment:
    """整体证据评估。整体“证据不足”当且仅当：样本外预测数 <100，
    或基金历史 <1260 个交易日。档位 verdict 由 ``bucket_verdict`` 逐档给；
    未传 ``bucket_ns`` 时从 ``preds`` 的 ``bucket`` 字段现算（三个回撤档
    的样本外数，未出现档记 0）。
    """
    reasons = []
    if len(preds) < MIN_OUT_OF_SAMPLE_N:
        reasons.append(f"样本外预测数 {len(preds)} < {MIN_OUT_OF_SAMPLE_N}")
    if history_days < MIN_HISTORY_TRADING_DAYS:
        reasons.append(f"基金历史 {history_days} 个交易日 < {MIN_HISTORY_TRADING_DAYS}（约 5 年）")
    if bucket_ns is None:
        bucket_ns = {}
        for pred in preds:
            bucket_ns[pred.bucket] = bucket_ns.get(pred.bucket, 0) + 1
    verdicts = {}
    for bucket in ("<5%", "5%-10%", ">10%"):
        verdicts[bucket] = bucket_verdict(bucket_ns.get(bucket, 0))
    verdict = "insufficient" if reasons else "sufficient"
    return EvidenceAssessment(verdict, reasons, verdicts)


@dataclass
class Scorecard:
    n: int
    non_overlapping_blocks: int
    actual_rate: float | None
    mean_state_prob: float | None
    mean_baseline_prob: float | None
    brier_state: float | None
    brier_baseline: float | None
    skill: float | None
    degenerate: bool  # 基准率 Brier 为 0，技能分数无法计算
    calibration: list[CalibrationRow]
    yearly: list[YearlyRow]
    failures: list[int]
    evidence: EvidenceAssessment


def build_scorecard(preds, years: list[int], history_days: int, horizon: int) -> Scorecard:
    """组装一张基金×类别的完整成绩单。``years`` 与 ``preds`` 等长对应年份；
    ``horizon`` 用于不重叠 block 数（与条目 8 口径一致）。"""
    yearly = yearly_table(preds, years) if preds else []
    state = brier_score(preds, use_state=True)
    baseline = brier_score(preds, use_state=False)
    calibration = calibration_table(preds, use_state=True)
    evidence = assess_evidence(preds, history_days)
    if preds:
        actual = sum(p.outcome for p in preds) / len(preds)
        mean_state = sum(p.state_prob for p in preds) / len(preds)
        mean_baseline = sum(p.baseline_prob for p in preds) / len(preds)
    else:
        actual = mean_state = mean_baseline = None
    return Scorecard(
        n=len(preds),
        non_overlapping_blocks=non_overlapping_count(preds, horizon),
        actual_rate=actual,
        mean_state_prob=mean_state,
        mean_baseline_prob=mean_baseline,
        brier_state=state,
        brier_baseline=baseline,
        skill=skill_score(state, baseline),
        degenerate=baseline == 0 and bool(preds),
        calibration=calibration,
        yearly=yearly,
        failures=failure_years(yearly),
        evidence=evidence,
    )
