"""历史频率：只数过去发生了多少次，不对未来做任何判断。

定位（写死在设计里，不是文案）：本模块呈现的是**滚动历史频率**——
在每一个历史交易日站上去看，之后 6/12 个月里“赚钱的起点占多少、
一年内跌超某条线的起点占多少”。它与条目 8 的概率实验是两条路：
实验给“未来某类事件发生的概率”打分，本模块不给概率、不建模型、
不输出任何对未来的判断；频率高低只描述过去，不承诺未来重演。

口径（与条目 7 可行性报告第 2 节一致，实验代码不得另起口径）：
- 期限换算（交易日近似）：6 个月 = 126、12 个月 = 252、24 个月 = 504。
- 起点：每个交易日都是一个起点；起点必须拥有完整的未来窗口才计入
  （6 个月统计要求起点后至少 126 个交易日，12 个月统计要求 252 个）。
- 收益为正：起点后第 126/252 个交易日的累计净值严格高于起点当日。
- 未来 12 个月内最大回撤超阈值：从起点（含）起 252 个交易日内，净值
  相对期间内滚动高点的最大跌幅超过 5%/10%/15%（三档全列，不挑）。
- 回本时长（跌破 5% 后）：起点是**全部交易日**（不限于 12 个月完整窗口的
  起点，因为回本观察窗是 24 个月）。跌破指净值首次跌破决策日净值的 95%
  （即相对决策日下跌 5%，不是相对期间滚动高点——相对高点跌 5% 时净值
  常仍在决策日水平之上，“回到决策日水平”当天就满足，会得出中位数
  只有几天这种无意义的数字，条目 7 报告自己也记录过第一版探针的同类
  错误）；回升指跌破日之后首次回到决策日净值水平；观察窗均为决策日
  后 504 个交易日。回本天数 = 回升日 − **决策日**（含跌下去的过程，
  不是从跌破日起算——该口径经反推与条目 7 报告的回本数字逐项一致：
  事件 2036、中位 108、p75 169、p90 290、未回升 761/2036）。
  24 个月内或数据结束前未回升的记为“未回升”（含右删失）。
- 重叠警告：起点之间窗口高度重叠，n 是滚动起点数，不是独立样本数；
  报告必须并列不重叠 12 个月 block 数（全程交易日数 // 252），不得用
  滚动 n 暗示证据强度。

证据纪律（阈值写死，报告披露）：
- 可用历史不足 3 年 → 拒绝出结论（与回测引擎同一条纪律）。
- 12 个月起点数 < 100 → 整体只能写“证据不足”，数字照常列示、结论降级。
- 某年起点数 < 30 → 该年只能写“证据不足”；跌破 5% 事件数 < 30 →
  回本分布只能写“证据不足”，不报中位数当结论。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from services.backtest_service import MIN_HISTORY_YEARS, _clean_nav

# ---- 产品预设（写死，不开放任意参数） ----
HORIZON_6M = 126
HORIZON_12M = 252
PAYBACK_WINDOW = 504  # 回本观察窗：起点后 24 个月
DRAWDOWN_THRESHOLDS: tuple[float, ...] = (0.05, 0.10, 0.15)
MIN_ORIGINS_12M = 100  # 整体证据门槛：12 个月起点数低于此值只能写“证据不足”
MIN_YEAR_ORIGINS = 30  # 逐年证据门槛
MIN_PAYBACK_EVENTS = 30  # 回本分布证据门槛

FIXED_DISCLAIMER = "历史频率不代表未来表现。本页只数过去发生了多少次，不对未来做任何判断，不提供买卖意见。"


def _freq(count: int, total: int) -> dict:
    return {"freq": (count / total if total else None), "count": count, "n": total}


def _quantile(sorted_values: list[float], q: float) -> float | None:
    """线性插值分位数（与 numpy 默认 linear 口径一致），空列表返回 None。"""
    if not sorted_values:
        return None
    n = len(sorted_values)
    pos = q * (n - 1)
    lo = int(np.floor(pos))
    hi = int(np.ceil(pos))
    if lo == hi:
        return float(sorted_values[lo])
    frac = pos - lo
    return float(sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac)


def compute_history_frequency(nav: pd.Series) -> dict:
    """对已清洗的累计净值序列（正值、升序、去重）计算全部滚动历史频率。

    返回 dict 可直接 JSON 序列化；不做任何取数、不抛业务异常（空序列
    由调用方 run_history_frequency 按纪律翻译为拒绝）。
    """
    values = nav.to_numpy(dtype=float)
    dates = pd.to_datetime(nav.index)
    n = len(values)
    result: dict = {
        "origins_6m": max(n - HORIZON_6M, 0),
        "origins_12m": max(n - HORIZON_12M, 0),
        "non_overlapping_blocks_12m": n // HORIZON_12M,
        "positive_6m": None,
        "positive_12m": None,
        "drawdown_exceed_12m": {},
        "payback_5pct": None,
        "yearly": [],
    }
    if n <= HORIZON_6M:
        return result

    # -- 6 个月为正频率（起点 i 要求 i+126 <= n-1） --
    n6 = n - HORIZON_6M
    pos6 = int(np.sum(values[HORIZON_6M:] > values[:n6]))
    result["positive_6m"] = _freq(pos6, n6)

    if n <= HORIZON_12M:
        return result

    # -- 12 个月统计：为正频率 + 期间最大回撤超三档阈值的频率 --
    n12 = n - HORIZON_12M
    ret12 = values[HORIZON_12M:] / values[:n12] - 1.0
    pos12 = int(np.sum(ret12 > 0))
    result["positive_12m"] = _freq(pos12, n12)

    # 每个起点的 12 个月内最大回撤：窗口内相对滚动高点的最大跌幅。
    max_dd = np.empty(n12, dtype=float)
    for i in range(n12):
        window = values[i : i + HORIZON_12M + 1]
        running_max = np.maximum.accumulate(window)
        max_dd[i] = float(np.min(window / running_max - 1.0))
    for threshold in DRAWDOWN_THRESHOLDS:
        key = f"{int(threshold * 100)}"
        result["drawdown_exceed_12m"][key] = _freq(int(np.sum(max_dd < -threshold)), n12)

    # -- 逐年表（按起点年份分组；只含 12 个月统计） --
    years = dates[:n12].year.to_numpy()
    yearly = []
    for year in sorted(set(years.tolist())):
        mask = years == year
        yn = int(mask.sum())
        y_pos = int(np.sum(ret12[mask] > 0))
        y_dd10 = int(np.sum(max_dd[mask] < -0.10))
        yearly.append(
            {
                "year": int(year),
                "n": yn,
                "positive_12m": _freq(y_pos, yn),
                "drawdown_gt_10pct": _freq(y_dd10, yn),
                "evidence": "足" if yn >= MIN_YEAR_ORIGINS else "不足",
            }
        )
    result["yearly"] = yearly

    # -- 回本分布（跌破 5% 后回到决策日净值水平所需天数） --
    # 口径（与条目 7 报告第 2.3 节的实测数字逐项一致，见模块 docstring）：
    # 起点 = 全部交易日；跌破 = 净值首次跌破决策日净值的 95%（相对决策日
    # 下跌 5%），须在决策日后 504 个交易日内发生；回升 = 跌破日之后首次
    # 回到决策日净值水平，限决策日后 504 个交易日内；回本天数 = 回升日 −
    # 决策日（含跌下去的过程）；未回升含右删失。
    breaches: list[tuple[int, int]] = []  # (起点下标, 首次跌破日下标)
    for i in range(n - 1):
        horizon_end = min(i + PAYBACK_WINDOW, n - 1)
        if horizon_end <= i:
            continue
        hit = np.nonzero(values[i + 1 : horizon_end + 1] < 0.95 * values[i])[0]
        if len(hit):
            breaches.append((i, i + 1 + int(hit[0])))
    payback_days: list[int] = []
    unrecovered = 0
    for i, j in breaches:
        limit = min(i + PAYBACK_WINDOW, n - 1)
        recovered = np.nonzero(values[j + 1 : limit + 1] >= values[i])[0]
        if len(recovered):
            payback_days.append(int(recovered[0]) + 1 + (j - i))  # 天数 = 回升日 − 决策日
        else:
            unrecovered += 1
    events = len(breaches)
    payback_days.sort()
    result["payback_5pct"] = {
        "origins": n - 1,
        "events": events,
        "recovered": len(payback_days),
        "unrecovered": unrecovered,
        "unrecovered_share": (unrecovered / events if events else None),
        "median_days": _quantile(payback_days, 0.5) if events >= MIN_PAYBACK_EVENTS else None,
        "p75_days": _quantile(payback_days, 0.75) if events >= MIN_PAYBACK_EVENTS else None,
        "p90_days": _quantile(payback_days, 0.90) if events >= MIN_PAYBACK_EVENTS else None,
        "evidence": "足" if events >= MIN_PAYBACK_EVENTS else "不足",
    }
    return result


def run_history_frequency(nav_frame: pd.DataFrame, code: str, name: str = "") -> dict:
    """对单只基金跑滚动历史频率，返回结构化报告 dict（可直接 JSON 序列化）。

    净值清洗复用回测引擎的 _clean_nav（累计净值口径、丢弃缺失/非正行、
    绝不回退单位净值）；证据纪律见模块 docstring。
    """
    nav, dropped = _clean_nav(nav_frame)
    disclosures = [
        "口径：全程使用累计净值。单位净值在除息日会被扣掉分红，用它计算收益等于把分红误算成亏损。",
        "这是什么：下面所有数字都是对已经发生过的历史的计数——在每一个历史交易日站上去看，之后 6/12 个月里发生了什么。它们只描述过去，不对未来做任何判断。",
        "重叠起点警告：起点是每个交易日，相邻窗口重叠 251 天，n 是滚动起点数、不是独立样本数；并列的不重叠 12 个月 block 数才是可比的独立段数，不得用滚动 n 暗示证据强度。",
        "期限换算：6 个月 = 126 个交易日、12 个月 = 252 个交易日、24 个月 = 504 个交易日，是交易日近似，不是自然月精确换算。",
        "回本口径：起点是全部交易日（回本观察窗是 24 个月，不限于 12 个月完整窗口的起点）；跌破 5% 指净值首次跌破决策日净值的 95%（相对决策日下跌 5%），须在决策日后 504 个交易日内发生；回升指跌破日之后首次回到决策日净值水平，限决策日后 504 个交易日内；回本天数 = 回升日 − 决策日（含跌下去的过程）；24 个月内或数据结束前未回升的记为“未回升”（含右删失，即窗口被数据末尾截断的起点）。",
        "证据纪律：可用历史不足 3 年拒绝出结论；12 个月起点数不足 100 时整体只能写“证据不足”；某年起点数不足 30 时该年只能写“证据不足”；跌破 5% 事件不足 30 时回本分布不报中位数。",
        "费用：净值口径不含申购/赎回费，扣费后为正的频率会更低一点；本页不把净值频率包装成到手收益频率。",
        "幸存者偏差：本工具只统计单只存续基金，未使用包含已清盘基金的历史基金池，幸存者偏差未消除；频率不可外推为全市场结论。",
        FIXED_DISCLAIMER,
    ]
    if dropped:
        disclosures.insert(
            1, f"数据清洗：剔除 {dropped} 条无效净值记录（缺失或非正），未做任何插值或替代。"
        )

    report: dict = {
        "code": code,
        "name": name,
        "status": "ok",
        "refusal_reason": None,
        "evidence": "足",
        "evidence_reason": None,
        "data_start": nav.index.min().strftime("%Y-%m-%d") if len(nav) else None,
        "data_end": nav.index.max().strftime("%Y-%m-%d") if len(nav) else None,
        "dropped_rows": dropped,
        "origins_6m": 0,
        "origins_12m": 0,
        "non_overlapping_blocks_12m": 0,
        "positive_6m": None,
        "positive_12m": None,
        "drawdown_exceed_12m": {},
        "payback_5pct": None,
        "yearly": [],
        "disclosures": disclosures,
    }
    if len(nav) < 2:
        report["status"] = "refused"
        report["refusal_reason"] = "可用累计净值数据不足，拒绝出结论"
        return report
    history_years = (nav.index.max() - nav.index.min()).days / 365.25
    if history_years < MIN_HISTORY_YEARS:
        report["status"] = "refused"
        report["refusal_reason"] = (
            f"可用历史仅约 {history_years:.1f} 年（{report['data_start']} 至 {report['data_end']}），"
            f"不足 {MIN_HISTORY_YEARS} 年，按数据纪律拒绝出结论"
        )
        return report
    if len(nav) <= HORIZON_12M:
        report["status"] = "refused"
        report["refusal_reason"] = "历史长度不足以留出完整的 12 个月统计窗口，拒绝出结论"
        return report

    computed = compute_history_frequency(nav)
    report.update(computed)
    if computed["origins_12m"] < MIN_ORIGINS_12M:
        report["evidence"] = "不足"
        report["evidence_reason"] = (
            f"12 个月起点数仅 {computed['origins_12m']} 个（不足 {MIN_ORIGINS_12M} 个），"
            "数字照常列示，但只能写“证据不足”，不得据此下结论"
        )
    return report
