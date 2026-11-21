"""概率预测实验 v14（离线实验，不进产品页面、不注册接口）。

与 v1–v13 的本质区别（换方法族）：
- v1–v13 属于“门槛 / 门控族（Hard Gating）”：依据样本量、行情集中度、
  标签极性、多年一边倒或趋势段一致性对决策日做硬切分，触发时直接丢弃
  状态信号并整段回退到基准率，导致边界跳变及误杀原本方向正确的信号。
- v14 属于“滚动保序校准映射族（Rolling Isotonic Calibration Mapping）”：
  **不丢弃任何状态信号、保持原始模型排序（Rank Order）**，而是在每个
  决策日 t，仅利用标签已经在 t 之前完全到期兑现（``tau <= t - horizon``）
  的 ``v1`` 历史预测—实际结果配对序列，在线拟合单调非减的保序回归函数
  （PAVA + 线性插值），并向窗口内历史基准率做固定比例收缩，将原始概率
  ``p_raw`` 重标定为校准概率 ``p_cal``。

所有常数在看任何跑分结果之前写死并披露，运行时不做任何参数扫描或调参：
- ``FIT_WINDOW_PREDS = 756``：滚动拟合窗口取最近 756 个已兑现历史预测点
  （约 3 个交易年，与 ``v1`` 的 ``HALF_LIFE_DAYS = 756`` 量纲对齐）。
- ``MIN_CALIBRATION_PREDS = 252``：冷启动门槛，已兑现历史预测点不足 252 个
  （约 1 个交易年）时不拟合映射，保持 ``v1`` 原始概率。
- ``REFIT_INTERVAL_DAYS = 63``：每 63 个交易日（约 1 个季度）重拟合一次
  校准映射并在该季度内复用，避免相邻交易日单样本进出引发映射抖动。
- ``SHRINKAGE_LAMBDA = 0.20``：向拟合窗口内实际发生率收缩的固定权重，
  抑制小分箱下保序回归在极端值处的过拟合。
- ``PROB_CLIP_MIN = 0.02`` / ``PROB_CLIP_MAX = 0.98``：输出概率裁剪上下界。

评估口径完全复用 ``forecast_baseline`` 与 ``forecast_scorecard``：
- 比较基准 ``baseline_prob`` 仍为 v0 无加权历史基准率；
- 成绩单由 ``forecast_scorecard.build_scorecard`` 生成；
- CLI 报告提供四只目标基金（161725、110020、110022、217022）A/B 共 8 组
  的完整成绩单，并与 ``v1`` 以及“无信号（仅用时效加权基准率 wbaseline）”
  同表对比，同时附上事先写明的预期核对表。

文案红线：本模块仅输出离线概率预测实验数据，严禁进入产品接口或前端页面。
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import sys
from typing import Sequence

if __package__ in (None, ""):
    _BACKEND_DIR = Path(__file__).resolve().parents[1]
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))

from experiments.forecast_baseline import (
    HORIZON_A_DAYS,
    HORIZON_B_DAYS,
    TEST_START_INDEX,
    WINDOW_DAYS,
)
from experiments.forecast_scorecard import Scorecard, build_scorecard
from experiments.forecast_v1 import (
    HALF_LIFE_DAYS,
    SHRINKAGE_M,
    PredictionV1,
    generate_predictions_v1,
)

# 事先写死的校准映射常数（看结果前锁定，不得运行时调参）。
FIT_WINDOW_PREDS = 756  # 滚动拟合窗口：近 756 个已兑现预测点（约 3 个交易年）
MIN_CALIBRATION_PREDS = 252  # 冷启动阈值：已兑现样本不足 252 个（约 1 年）时退化为恒等映射
REFIT_INTERVAL_DAYS = 63  # 更新频率：每 63 个交易日（约 1 个季度）重拟合一次
SHRINKAGE_LAMBDA = 0.20  # 向窗口基准率收缩的固定系数
PROB_CLIP_MIN = 0.02  # 校准后概率下界
PROB_CLIP_MAX = 0.98  # 校准后概率上界

TARGET_FUNDS: tuple[tuple[str, str], ...] = (
    ("161725", "招商中证白酒指数(LOF)A"),
    ("110020", "易方达沪深300ETF联接A"),
    ("110022", "易方达消费行业股票"),
    ("217022", "招商产业债券A"),
)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "database" / "nav_history.db"


@dataclass(frozen=True)
class IsotonicCalibrator:
    """保序校准映射器（PAVA 分段常数中点线性插值 + 窗口基准率收缩）。"""

    xs: tuple[float, ...]  # 单调递增的锚点 x（原始预测概率代表值）
    ys: tuple[float, ...]  # 单调非减的锚点 y（保序校准后条件频率）
    window_base_rate: float  # 拟合窗口内实际正例率
    sample_count: int  # 拟合窗口样本量
    shrinkage_lambda: float = SHRINKAGE_LAMBDA
    clip_min: float = PROB_CLIP_MIN
    clip_max: float = PROB_CLIP_MAX

    def predict(self, raw_prob: float) -> float:
        """将单个原始概率映射为校准后概率。"""
        if not self.xs:
            iso_val = raw_prob
        elif len(self.xs) == 1:
            iso_val = self.ys[0]
        elif raw_prob <= self.xs[0]:
            iso_val = self.ys[0]
        elif raw_prob >= self.xs[-1]:
            iso_val = self.ys[-1]
        else:
            pos = bisect_right(self.xs, raw_prob) - 1
            pos = max(0, min(pos, len(self.xs) - 2))
            x0, x1 = self.xs[pos], self.xs[pos + 1]
            y0, y1 = self.ys[pos], self.ys[pos + 1]
            if x1 <= x0:
                iso_val = y0
            else:
                ratio = (raw_prob - x0) / (x1 - x0)
                iso_val = y0 + ratio * (y1 - y0)

        shrunk = (
            1.0 - self.shrinkage_lambda
        ) * iso_val + self.shrinkage_lambda * self.window_base_rate
        return max(self.clip_min, min(self.clip_max, shrunk))


@dataclass
class PredictionV14:
    """v14 单日样本外预测记录（兼容 ``forecast_scorecard`` Duck Typing 接口）。"""

    index: int
    bucket: str
    baseline_prob: float  # v0 无加权历史基准率（成绩单统一分母）
    state_prob: float  # 经滚动保序映射校准后的概率
    raw_state_prob: float  # 校准前的 v1 原始概率
    outcome: int
    train_n: int
    bucket_train_n: int
    state_fallback: bool  # 是否处于冷启动期（已兑现样本 < MIN_CALIBRATION_PREDS，未做映射）
    baseline_weighted: float  # 时效加权基准率（无信号对照组）
    calibration_n: int  # 当前生效校准器使用的历史已兑现样本量
    refit_index: int | None  # 当前生效校准器拟合时的决策日下标（冷启动期为 None）


def fit_isotonic_calibrator(
    raw_probs: Sequence[float],
    outcomes: Sequence[int],
    shrinkage_lambda: float = SHRINKAGE_LAMBDA,
    clip_min: float = PROB_CLIP_MIN,
    clip_max: float = PROB_CLIP_MAX,
) -> IsotonicCalibrator:
    """使用 Pool Adjacent Violators Algorithm (PAVA) 拟合单调非减概率映射。

    步骤：
    1. 按 ``raw_prob`` 升序排列样本；相同 ``raw_prob`` 的点先合并为同权初始块，
       保证输入顺序无关且严格满足单调性。
    2. 自左向右扫描，若相邻两块的均值满足 ``prev_mean > curr_mean``（违反单调非减），
       则合并两块并重算加权均值，回溯检查直至全局单调非减。
    3. 每个最终保序块取 ``x_anchor = mean(raw_prob)``、``y_anchor = mean(outcome)``，
       作为分段线性插值锚点。
    """
    if len(raw_probs) != len(outcomes):
        raise ValueError("raw_probs and outcomes must have the same length")
    n = len(raw_probs)
    if n == 0:
        return IsotonicCalibrator(
            xs=(),
            ys=(),
            window_base_rate=0.5,
            sample_count=0,
            shrinkage_lambda=shrinkage_lambda,
            clip_min=clip_min,
            clip_max=clip_max,
        )

    pairs = sorted(zip(raw_probs, outcomes), key=lambda item: item[0])

    # 先按相同的 raw_prob 聚合为初始块：[sum_x, sum_y, count]
    blocks: list[list[float]] = []
    for p, y in pairs:
        if blocks and abs(p - (blocks[-1][0] / blocks[-1][2])) <= 1e-12:
            blocks[-1][0] += float(p)
            blocks[-1][1] += float(y)
            blocks[-1][2] += 1.0
        else:
            blocks.append([float(p), float(y), 1.0])

    # PAVA 合并违反单调非减的相邻块
    merged: list[list[float]] = []
    for blk in blocks:
        merged.append(blk)
        while len(merged) >= 2:
            prev = merged[-2]
            curr = merged[-1]
            prev_mean = prev[1] / prev[2]
            curr_mean = curr[1] / curr[2]
            if prev_mean > curr_mean:
                prev[0] += curr[0]
                prev[1] += curr[1]
                prev[2] += curr[2]
                merged.pop()
            else:
                break

    xs = tuple(b[0] / b[2] for b in merged)
    ys = tuple(b[1] / b[2] for b in merged)
    window_base_rate = sum(float(y) for y in outcomes) / n

    return IsotonicCalibrator(
        xs=xs,
        ys=ys,
        window_base_rate=window_base_rate,
        sample_count=n,
        shrinkage_lambda=shrinkage_lambda,
        clip_min=clip_min,
        clip_max=clip_max,
    )


def calibrate_predictions_v14(
    v1_preds: Sequence[PredictionV1],
    horizon: int,
    fit_window: int = FIT_WINDOW_PREDS,
    min_samples: int = MIN_CALIBRATION_PREDS,
    refit_interval: int = REFIT_INTERVAL_DAYS,
    shrinkage_lambda: float = SHRINKAGE_LAMBDA,
    clip_min: float = PROB_CLIP_MIN,
    clip_max: float = PROB_CLIP_MAX,
) -> list[PredictionV14]:
    """对按时间顺序排列的 ``PredictionV1`` 序列执行严格样本外滚动保序校准。

    因果纪律保证（Zero Lookahead）：
    - 在决策日 ``decision = pred.index``，仅允许使用满足
      ``hist.index <= decision - horizon`` 的历史 ``v1`` 预测点，
      确保这些历史样本的未来 ``horizon`` 日标签在 ``decision`` 当日或之前
      已经完整观测，绝不偷看未到期标签。
    """
    if fit_window <= 0:
        raise ValueError("fit_window must be positive")
    if min_samples <= 0:
        raise ValueError("min_samples must be positive")
    if refit_interval <= 0:
        raise ValueError("refit_interval must be positive")

    sorted_v1 = sorted(v1_preds, key=lambda p: p.index)
    calibrated: list[PredictionV14] = []

    matured_cursor = 0
    total_v1 = len(sorted_v1)

    active_calibrator: IsotonicCalibrator | None = None
    last_refit_decision: int | None = None

    for pred in sorted_v1:
        decision = pred.index
        matured_cutoff = decision - horizon

        # 推进已到期游标：仅纳入 index <= decision - horizon 的历史样本
        while (
            matured_cursor < total_v1
            and sorted_v1[matured_cursor].index <= matured_cutoff
        ):
            matured_cursor += 1

        if matured_cursor < min_samples:
            # 冷启动期：已兑现样本不足 min_samples，保持 v1 原始概率
            calibrated.append(
                PredictionV14(
                    index=pred.index,
                    bucket=pred.bucket,
                    baseline_prob=pred.baseline_prob,
                    state_prob=pred.state_prob,
                    raw_state_prob=pred.state_prob,
                    outcome=pred.outcome,
                    train_n=pred.train_n,
                    bucket_train_n=pred.bucket_train_n,
                    state_fallback=True,
                    baseline_weighted=pred.baseline_weighted,
                    calibration_n=matured_cursor,
                    refit_index=None,
                )
            )
            continue

        # 达到冷启动阈值后，首次或每间隔 refit_interval 个交易日重拟合一次映射
        need_refit = (
            active_calibrator is None
            or last_refit_decision is None
            or (decision - last_refit_decision) >= refit_interval
        )
        if need_refit:
            win_start = max(0, matured_cursor - fit_window)
            window_slice = sorted_v1[win_start:matured_cursor]
            active_calibrator = fit_isotonic_calibrator(
                raw_probs=[item.state_prob for item in window_slice],
                outcomes=[item.outcome for item in window_slice],
                shrinkage_lambda=shrinkage_lambda,
                clip_min=clip_min,
                clip_max=clip_max,
            )
            last_refit_decision = decision

        assert active_calibrator is not None
        cal_prob = active_calibrator.predict(pred.state_prob)
        calibrated.append(
            PredictionV14(
                index=pred.index,
                bucket=pred.bucket,
                baseline_prob=pred.baseline_prob,
                state_prob=cal_prob,
                raw_state_prob=pred.state_prob,
                outcome=pred.outcome,
                train_n=pred.train_n,
                bucket_train_n=pred.bucket_train_n,
                state_fallback=False,
                baseline_weighted=pred.baseline_weighted,
                calibration_n=active_calibrator.sample_count,
                refit_index=last_refit_decision,
            )
        )

    return calibrated


def generate_predictions_v14(
    nav: list[float],
    kind: str,
    window: int = WINDOW_DAYS,
    test_start: int = TEST_START_INDEX,
    half_life: float = HALF_LIFE_DAYS,
    shrinkage_m: float = SHRINKAGE_M,
    fit_window: int = FIT_WINDOW_PREDS,
    min_samples: int = MIN_CALIBRATION_PREDS,
    refit_interval: int = REFIT_INTERVAL_DAYS,
    shrinkage_lambda: float = SHRINKAGE_LAMBDA,
) -> list[PredictionV14]:
    """生成滚动原点样本外 v14 预测序列。"""
    if kind == "A":
        horizon = HORIZON_A_DAYS
    elif kind == "B":
        horizon = HORIZON_B_DAYS
    else:
        raise ValueError(f"unknown prediction kind: {kind!r}")

    v1_preds = generate_predictions_v1(
        nav=nav,
        kind=kind,
        mode="v1",
        window=window,
        test_start=test_start,
        half_life=half_life,
        shrinkage_m=shrinkage_m,
    )
    return calibrate_predictions_v14(
        v1_preds=v1_preds,
        horizon=horizon,
        fit_window=fit_window,
        min_samples=min_samples,
        refit_interval=refit_interval,
        shrinkage_lambda=shrinkage_lambda,
    )


def load_fund_nav_and_dates(
    fund_code: str, db_path: Path = DEFAULT_DB_PATH
) -> tuple[list[str], list[float]]:
    """从本地 ``nav_history.db`` 读取指定基金按日期升序排列的净值序列。

    自动兼容常见表名与列名（优先使用累计净值复权序列 ``adj_nav`` / ``accumulated_nav``，
    若不存在则回退至单位净值 ``nav`` / ``unit_nav``）。
    """
    if not db_path.exists():
        raise FileNotFoundError(f"NAV database not found: {db_path}")

    with sqlite3.connect(str(db_path)) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        candidate_tables = [
            t for t in ("nav_history", "fund_nav", "fund_nav_history") if t in tables
        ] + [t for t in tables if "nav" in t.lower()]

        for table in candidate_tables:
            cols_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = {c[1].lower(): c[1] for c in cols_info}
            code_col = next(
                (col_names[k] for k in ("fund_code", "code", "symbol") if k in col_names),
                None,
            )
            date_col = next(
                (col_names[k] for k in ("nav_date", "date", "trade_date") if k in col_names),
                None,
            )
            val_col = next(
                (
                    col_names[k]
                    for k in ("cumulative_nav", "adj_nav", "accumulated_nav", "acc_nav", "nav", "unit_nav")
                    if k in col_names
                ),
                None,
            )
            if code_col and date_col and val_col:
                rows = conn.execute(
                    f"SELECT {date_col}, {val_col} FROM {table} "
                    f"WHERE {code_col} = ? AND {val_col} IS NOT NULL AND {val_col} > 0 "
                    f"ORDER BY {date_col} ASC",
                    (fund_code,),
                ).fetchall()
                if rows:
                    dates = [str(r[0]) for r in rows]
                    navs = [float(r[1]) for r in rows]
                    return dates, navs

    raise RuntimeError(
        f"Unable to locate valid NAV rows for fund {fund_code} in {db_path}"
    )


def _years_for_preds(preds: Sequence, dates: Sequence[str]) -> list[int]:
    return [int(str(dates[p.index])[:4]) for p in preds]


def _calibration_metrics(sc: Scorecard) -> tuple[float, float, bool]:
    """计算校准分档指标：(加权平均绝对偏差 ECE, 非空档最大绝对偏差, 校准是否可接受)。

    校准可接受标准（与产品化门槛口径一致）：所有样本量 >= 30 的非空分档
    平均预测概率与实际频率绝对偏差 <= 0.10，且加权平均绝对偏差 ECE <= 0.08。
    """
    total_n = sum(r.n for r in sc.calibration)
    if total_n == 0:
        return 0.0, 0.0, False
    weighted_err = 0.0
    max_gap = 0.0
    sufficient_bucket_ok = True
    for row in sc.calibration:
        if row.n > 0 and row.gap is not None:
            abs_gap = abs(row.gap)
            weighted_err += row.n * abs_gap
            if abs_gap > max_gap:
                max_gap = abs_gap
            if row.n >= 30 and abs_gap > 0.10:
                sufficient_bucket_ok = False
    ece = weighted_err / total_n
    acceptable = (sc.evidence.verdict == "sufficient") and sufficient_bucket_ok and (ece <= 0.08)
    return ece, max_gap, acceptable


@dataclass
class GroupComparison:
    fund_code: str
    fund_name: str
    kind: str
    sc_wbase: Scorecard
    sc_v1: Scorecard
    sc_v14: Scorecard
    cal_ratio: float  # 脱离冷启动期、实际应用校准映射的预测占比


def evaluate_all_groups(
    db_path: Path = DEFAULT_DB_PATH,
    funds: Sequence[tuple[str, str]] = TARGET_FUNDS,
) -> list[GroupComparison]:
    """对 4 只目标基金的 A/B 两组跑通 wbaseline（无信号）、v1 与 v14 成绩单。"""
    results: list[GroupComparison] = []
    for code, name in funds:
        dates, nav = load_fund_nav_and_dates(code, db_path=db_path)
        history_days = len(nav)
        for kind, horizon in (("A", HORIZON_A_DAYS), ("B", HORIZON_B_DAYS)):
            preds_wbase = generate_predictions_v1(nav, kind=kind, mode="wbaseline")
            preds_v1 = generate_predictions_v1(nav, kind=kind, mode="v1")
            preds_v14 = generate_predictions_v14(nav, kind=kind)

            sc_wbase = build_scorecard(
                preds_wbase, _years_for_preds(preds_wbase, dates), history_days, horizon
            )
            sc_v1 = build_scorecard(
                preds_v1, _years_for_preds(preds_v1, dates), history_days, horizon
            )
            sc_v14 = build_scorecard(
                preds_v14, _years_for_preds(preds_v14, dates), history_days, horizon
            )
            active_n = sum(1 for p in preds_v14 if not p.state_fallback)
            cal_ratio = (active_n / len(preds_v14)) if preds_v14 else 0.0
            results.append(
                GroupComparison(
                    fund_code=code,
                    fund_name=name,
                    kind=kind,
                    sc_wbase=sc_wbase,
                    sc_v1=sc_v1,
                    sc_v14=sc_v14,
                    cal_ratio=cal_ratio,
                )
            )
    return results


def _fmt_float(val: float | None, digits: int = 4) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{digits}f}"


def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:+.2f}%"


def format_report(comparisons: Sequence[GroupComparison]) -> str:
    """生成完整 CLI 对比报告（含 8 组同表对比、逐组详细成绩单、预期核对）。"""
    lines: list[str] = []
    lines.append("=" * 96)
    lines.append("实验 v14 报告：滚动保序校准映射（Rolling Isotonic Calibration Mapping）")
    lines.append(
        f"写死常数: FIT_WINDOW_PREDS={FIT_WINDOW_PREDS}, "
        f"MIN_CALIBRATION_PREDS={MIN_CALIBRATION_PREDS}, "
        f"REFIT_INTERVAL_DAYS={REFIT_INTERVAL_DAYS}, "
        f"SHRINKAGE_LAMBDA={SHRINKAGE_LAMBDA:.2f}, "
        f"CLIP=[{PROB_CLIP_MIN:.2f}, {PROB_CLIP_MAX:.2f}]"
    )
    lines.append("=" * 96)
    lines.append("")
    lines.append("【一、8 组同表对比：无信号（时效加权基准率） vs v1 vs v14】")
    header = (
        f"{'基金':<8} {'类':<2} {'N':>5} {'映射率':>7} | "
        f"{'Brier(v0)':>9} {'Brier(无信号)':>12} {'Brier(v1)':>9} {'Brier(v14)':>10} | "
        f"{'BSS(无信号)':>10} {'BSS(v1)':>9} {'BSS(v14)':>9} | "
        f"{'ECE(v1)':>8} {'ECE(v14)':>8} | {'失效年(v1->v14)':<16} {'达标?':<6}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    ece_improved = 0
    bss_improved = 0
    positive_bss_v14 = 0
    prod_ready_count = 0

    for item in comparisons:
        ece_v1, _, _ = _calibration_metrics(item.sc_v1)
        ece_v14, _, cal_ok_v14 = _calibration_metrics(item.sc_v14)
        if ece_v14 < ece_v1:
            ece_improved += 1
        if (
            item.sc_v14.skill is not None
            and item.sc_v1.skill is not None
            and item.sc_v14.skill > item.sc_v1.skill
        ):
            bss_improved += 1
        if item.sc_v14.skill is not None and item.sc_v14.skill > 0:
            positive_bss_v14 += 1

        # 产品化门槛：技能不差于基准率(skill >= 0) 且 校准可接受
        skill_ok = item.sc_v14.skill is not None and item.sc_v14.skill >= 0.0
        prod_ok = skill_ok and cal_ok_v14
        if prod_ok:
            prod_ready_count += 1

        fail_str = f"{len(item.sc_v1.failures)}->{len(item.sc_v14.failures)}"
        lines.append(
            f"{item.fund_code:<8} {item.kind:<2} {item.sc_v14.n:>5} {item.cal_ratio * 100:>6.1f}% | "
            f"{_fmt_float(item.sc_v14.brier_baseline):>9} "
            f"{_fmt_float(item.sc_wbase.brier_state):>12} "
            f"{_fmt_float(item.sc_v1.brier_state):>9} "
            f"{_fmt_float(item.sc_v14.brier_state):>10} | "
            f"{_fmt_pct(item.sc_wbase.skill):>10} "
            f"{_fmt_pct(item.sc_v1.skill):>9} "
            f"{_fmt_pct(item.sc_v14.skill):>9} | "
            f"{ece_v1:>8.4f} {ece_v14:>8.4f} | "
            f"{fail_str:<16} {'YES' if prod_ok else 'NO':<6}"
        )

    lines.append("")
    lines.append("【二、事先写明的预期 vs 实测结果摘要】")
    lines.append(f"1. 校准误差(ECE)优于 v1 的组数（预期 >= 6/8）: {ece_improved}/{len(comparisons)}")
    lines.append(f"2. BSS 优于 v1 的组数 / v14 正技能组数（预期正技能 3-4/8）: {bss_improved}/{len(comparisons)} 提升, {positive_bss_v14}/{len(comparisons)} 正技能")
    lines.append(f"3. 触达产品化门槛（skill >= 0 且校准可接受，预期 1-3/8）: {prod_ready_count}/{len(comparisons)}")

    lines.append("")
    lines.append("【三、8 组完整成绩单明细（v14）】")
    for item in comparisons:
        sc = item.sc_v14
        ece_v14, max_gap_v14, cal_ok_v14 = _calibration_metrics(sc)
        lines.append("-" * 80)
        lines.append(
            f"基金 {item.fund_code} ({item.fund_name}) - 类别 {item.kind} | "
            f"N={sc.n}, 不重叠块={sc.non_overlapping_blocks}, 证据={sc.evidence.verdict}"
        )
        lines.append(
            f"实际发生率={_fmt_float(sc.actual_rate)}, "
            f"平均预测(v14)={_fmt_float(sc.mean_state_prob)}, "
            f"Brier(v14)={_fmt_float(sc.brier_state)}, "
            f"Brier(v0基准)={_fmt_float(sc.brier_baseline)}, "
            f"BSS(v14)={_fmt_pct(sc.skill)}"
        )
        lines.append(
            f"ECE={ece_v14:.4f}, 最大分档偏差={max_gap_v14:.4f}, "
            f"校准可接受={'YES' if cal_ok_v14 else 'NO'}, "
            f"失效年份={sc.failures}"
        )
        lines.append("校准分档表:")
        for row in sc.calibration:
            lines.append(
                f"  {row.label:<8} n={row.n:<4} "
                f"mean_pred={_fmt_float(row.mean_pred)} "
                f"actual={_fmt_float(row.actual_rate)} "
                f"gap={_fmt_float(row.gap)}"
            )

    lines.append("")
    lines.append("披露：本报告仅为离线历史样本外实验结果；概率不是保证，历史校准不代表未来必然如此。")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行概率预测 v14 滚动保序校准映射实验")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="nav_history.db 路径（默认 backend/database/nav_history.db）",
    )
    args = parser.parse_args(argv)
    comparisons = evaluate_all_groups(db_path=args.db)
    print(format_report(comparisons))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())