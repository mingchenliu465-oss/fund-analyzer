"""诚实回测引擎：验证「回撤触发买入」这类说法在历史上到底成不成立。

定位（写死在设计里，不是文案）：本模块只做历史验证，不判断未来涨跌，
不提供任何买卖意见。防自欺靠结构约束，不靠使用者的自觉：

- 参数只有产品预设的 3 档阈值 × 2 档持有期 = 6 种组合，从不用某只基金的
  数据去拟合挑选；6 种组合的结果全部列示，不许只报最优（防数据窥探）。
- 前 ``LOOKBACK_DAYS`` 个交易日是预热段：只供回撤窗口取历史高点，
  不产生信号、不进入任何结论指标。结论只认其后的样本外评估段。
- 每个买卖决策只使用决策日（含）当日及之前的数据；由
  tests/test_backtest_engine.py 的防未来函数测试守住：改动未来净值，
  此前的决策与权益必须逐点不变。
- 收益一律走累计净值（经 fund_service.total_return_series 把关）：单位净值
  在除息日会被扣掉分红，用它回测等于把分红误算成亏损。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd
from dateutil.relativedelta import relativedelta

from services.fund_service import total_return_series

# ---- 产品预设（不开放任意参数扫描，这是防数据窥探的产品决策） ----
PRESET_THRESHOLDS: tuple[float, ...] = (0.10, 0.15, 0.20)
PRESET_HOLD_MONTHS: tuple[int, ...] = (6, 12)
LOOKBACK_DAYS = 250
MIN_HISTORY_YEARS = 3
INITIAL_CASH = 100_000.0  # 归一化本金，只影响金额列示，不影响任何收益率

# ---- 费用口径标注（报告必须逐项披露，假设值不许伪装成真实费率） ----
SUBSCRIPTION_FEE_LABEL = (
    "示例口径：天天基金申购费率全面 1 折后 A 类示例值，可配置；非本基金合同费率"
)
REDEMPTION_LT7_LABEL = (
    "法定下限：持有少于 7 日的赎回费不低于 1.5%，依据《公开募集开放式证券投资基金"
    "流动性风险管理规定》（证监会公告〔2017〕12 号）第二十三条，且全额计入基金财产"
)
REDEMPTION_ASSUMED_LABEL = "假设值：数据源未提供本基金合同赎回费率，此值为假设值"

FIXED_DISCLAIMER = "历史验证不代表未来表现。本报告只做历史验证，不提供买卖意见。"


@dataclass(frozen=True)
class FeeModel:
    """费用模型。申购费可配置；赎回费 <7 日走法定下限，其余走显式假设值。"""

    subscription_rate: float = 0.0015
    redemption_rate_after_7d: float = 0.005  # 假设值，披露中会标注

    def redemption_rate(self, holding_days: int) -> float:
        if holding_days < 7:
            return 0.015
        return self.redemption_rate_after_7d


@dataclass
class Trade:
    buy_date: pd.Timestamp
    buy_nav: float
    shares: float
    buy_fee: float
    sell_date: pd.Timestamp | None = None
    sell_nav: float | None = None
    sell_fee: float | None = None
    holding_days: int | None = None
    return_pct: float | None = None

    def to_dict(self) -> dict:
        return {
            "buy_date": self.buy_date.strftime("%Y-%m-%d"),
            "buy_nav": round(self.buy_nav, 4),
            "sell_date": self.sell_date.strftime("%Y-%m-%d") if self.sell_date is not None else None,
            "sell_nav": round(self.sell_nav, 4) if self.sell_nav is not None else None,
            "holding_days": self.holding_days,
            "buy_fee": round(self.buy_fee, 2),
            "sell_fee": round(self.sell_fee, 2) if self.sell_fee is not None else None,
            "return_pct": round(self.return_pct, 6) if self.return_pct is not None else None,
            "open": self.sell_date is None,
        }


def simulate_strategy(
    nav: pd.Series,
    *,
    threshold: float,
    hold: relativedelta,
    fees: FeeModel,
    eval_start_idx: int,
) -> tuple[pd.Series, list[Trade]]:
    """在样本外段内逐日推进回撤触发策略。

    因果性：i 日的信号只用 nav[:i+1]（回撤窗口为含当日在内的近 LOOKBACK_DAYS
    日最高累计净值）；卖出判定用当日净值与买入时已定下的到期日。
    同一日先判定到期卖出、卖出后当日不再买入。评估段之前的数据只用于窗口
    预热。返回（逐日权益 Series，交易列表）；期末未卖出的仓位记为 open 交易，
    权益按最后净值盯市，不计赎回费。
    """
    dates = nav.index
    values = nav.to_numpy(dtype=float)
    cash = INITIAL_CASH
    shares = 0.0
    open_trade: Trade | None = None
    sell_on_or_after: pd.Timestamp | None = None
    equity: dict[pd.Timestamp, float] = {}
    trades: list[Trade] = []

    for i in range(eval_start_idx, len(nav)):
        today = dates[i]
        price = float(values[i])
        sold_today = False
        if open_trade is not None and sell_on_or_after is not None and today >= sell_on_or_after:
            holding_days = (today - open_trade.buy_date).days
            gross = shares * price
            sell_fee = gross * fees.redemption_rate(holding_days)
            cash = gross - sell_fee
            open_trade.sell_date = today
            open_trade.sell_nav = price
            open_trade.sell_fee = sell_fee
            open_trade.holding_days = holding_days
            cost = open_trade.shares * open_trade.buy_nav + open_trade.buy_fee
            open_trade.return_pct = (cash / cost - 1.0) if cost > 0 else None
            trades.append(open_trade)
            open_trade = None
            sell_on_or_after = None
            shares = 0.0
            sold_today = True
        if open_trade is None and not sold_today:
            window = values[max(0, i - LOOKBACK_DAYS + 1) : i + 1]
            peak = float(window.max()) if len(window) else 0.0
            if peak > 0 and price <= peak * (1.0 - threshold):
                buy_fee = cash * fees.subscription_rate
                shares = (cash - buy_fee) / price
                open_trade = Trade(
                    buy_date=today, buy_nav=price, shares=shares, buy_fee=buy_fee
                )
                sell_on_or_after = today + hold
                cash = 0.0
        equity[today] = cash + shares * price

    if open_trade is not None:
        trades.append(open_trade)
    return pd.Series(equity, dtype=float), trades


def simulate_buy_and_hold(
    nav: pd.Series, *, fees: FeeModel, eval_start_idx: int
) -> pd.Series:
    """主基准：样本外段第一天以当日净值买入并持有到期末。

    只在买入时扣一次申购费；期末仍持有，不扣赎回费（报告披露中注明）。
    """
    start_price = float(nav.iloc[eval_start_idx])
    shares = INITIAL_CASH * (1.0 - fees.subscription_rate) / start_price
    return shares * nav.iloc[eval_start_idx:]


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1.0).min())


def _annualized_volatility(equity: pd.Series) -> float | None:
    returns = equity.pct_change().dropna()
    if len(returns) < 20:
        return None
    return float(returns.std(ddof=1) * math.sqrt(252))


def _yearly_table(strategy: pd.Series, benchmark: pd.Series) -> list[dict]:
    """逐年拆样本外段表现。年度收益以「上一年最后权益」为基数（首年为本金）。"""
    rows: list[dict] = []
    years = sorted({d.year for d in strategy.index})
    prev_s = INITIAL_CASH
    prev_b = INITIAL_CASH
    for year in years:
        s_year = strategy[strategy.index.year == year]
        b_year = benchmark[benchmark.index.year == year]
        if s_year.empty or b_year.empty:
            continue
        s_end, b_end = float(s_year.iloc[-1]), float(b_year.iloc[-1])
        s_ret = s_end / prev_s - 1.0
        b_ret = b_end / prev_b - 1.0
        s_curve = pd.concat([pd.Series([prev_s]), s_year.reset_index(drop=True)])
        rows.append(
            {
                "year": int(year),
                "strategy_return": round(s_ret, 6),
                "benchmark_return": round(b_ret, 6),
                "excess_return": round(s_ret - b_ret, 6),
                "strategy_max_drawdown": round(_max_drawdown(s_curve), 6),
                "strategy_volatility": (
                    round(v, 6) if (v := _annualized_volatility(s_year)) is not None else None
                ),
                "failed": bool(s_ret - b_ret < 0),
            }
        )
        prev_s, prev_b = s_end, b_end
    return rows


def _conclusion(
    *, eval_span_years: float, completed_trades: int, excess_total: float, yearly: list[dict]
) -> tuple[str, str]:
    """三段式结论的固定判定规则（预先写死并随报告披露，不临场发挥）。"""
    if eval_span_years < 3:
        return "证据不足", f"样本外评估段仅约 {eval_span_years:.1f} 年，不足 3 年"
    if completed_trades < 3:
        return "证据不足", f"样本外完成的交易仅 {completed_trades} 笔，不足 3 笔，样本太少"
    win_years = sum(1 for r in yearly if r["excess_return"] > 0)
    if excess_total > 0 and win_years * 2 >= len(yearly):
        return (
            "成立",
            f"样本外总收益跑赢买入持有，且 {len(yearly)} 年中有 {win_years} 年跑赢基准",
        )
    return (
        "不成立",
        f"样本外总超额收益为 {excess_total:+.2%}，或跑赢年份不足一半（{win_years}/{len(yearly)}）",
    )


def _clean_nav(nav_frame: pd.DataFrame) -> tuple[pd.Series, int]:
    """收敛为升序累计净值 Series；顺带统计被剔除的无效（缺失/非正）条数。"""
    basis = total_return_series(nav_frame)  # 无累计净值列直接抛错，绝不回退单位净值
    dates = pd.to_datetime(nav_frame["净值日期"])
    series = pd.Series(basis.to_numpy(dtype=float), index=dates)
    series = series[~series.index.duplicated(keep="last")].sort_index()
    valid = series[series > 0]
    dropped = int(len(series) - len(valid))
    return valid, dropped


def run_backtest(
    nav_frame: pd.DataFrame,
    code: str,
    name: str = "",
    fees: FeeModel | None = None,
    warmup_days: int = LOOKBACK_DAYS,
) -> dict:
    """对单只基金跑全部 6 种预设组合，返回结构化报告 dict（可直接 JSON 序列化）。"""
    fees = fees or FeeModel()
    nav, dropped = _clean_nav(nav_frame)
    disclosures = [
        f"收益口径：全程使用累计净值。单位净值在除息日会被扣掉分红，用它计算收益等于把分红误算成亏损。",
        f"参数纪律：只使用产品预设的 {len(PRESET_THRESHOLDS)} 档阈值 × {len(PRESET_HOLD_MONTHS)} 档持有期"
        f" = {len(PRESET_THRESHOLDS) * len(PRESET_HOLD_MONTHS)} 种组合，从不用本基金数据拟合挑选，6 种结果全部列示。",
        f"样本外：前 {warmup_days} 个交易日为预热段（供回撤窗口取历史高点），不进入任何结论指标；结论只认其后的样本外评估段。",
        "参数判定规则（结论）：评估段不足 3 年或完成交易不足 3 笔 → 证据不足；样本外总超额 > 0 且跑赢年份过半 → 成立；否则 → 不成立。",
        f"费用-申购费率 {fees.subscription_rate:.2%}：{SUBSCRIPTION_FEE_LABEL}。",
        f"费用-赎回费（持有 <7 日）{0.015:.2%}：{REDEMPTION_LT7_LABEL}。",
        f"费用-赎回费（持有 ≥7 日）{fees.redemption_rate_after_7d:.2%}：{REDEMPTION_ASSUMED_LABEL}。",
        "费用-基准：买入持有基准只在买入时扣一次申购费，期末仍持有、未扣赎回费。",
        "幸存者偏差：本工具只验证单只存续基金，未使用包含已清盘基金的历史基金池，幸存者偏差未消除；结论不可外推为全市场策略结论。",
        "成交简化：真实申购赎回存在确认日（T+1）与到账时滞，本回测按决策日当日净值成交，未做 T+1 确认模拟。",
        "指数说明：主基准为买入并持有同一只基金。指数多为价格口径、不含分红，用作基准会系统性低估基准收益，故不作为主基准。",
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
        "data_start": nav.index.min().strftime("%Y-%m-%d") if len(nav) else None,
        "data_end": nav.index.max().strftime("%Y-%m-%d") if len(nav) else None,
        "eval_start": None,
        "warmup_days": warmup_days,
        "combos": [],
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
    if len(nav) <= warmup_days:
        report["status"] = "refused"
        report["refusal_reason"] = "历史长度不足以在预热段之后留出样本外评估段，拒绝出结论"
        return report

    eval_start_idx = warmup_days
    report["eval_start"] = nav.index[eval_start_idx].strftime("%Y-%m-%d")
    eval_span_years = (nav.index.max() - nav.index[eval_start_idx]).days / 365.25
    benchmark_equity = simulate_buy_and_hold(nav, fees=fees, eval_start_idx=eval_start_idx)
    benchmark_total = float(benchmark_equity.iloc[-1] / INITIAL_CASH - 1.0)

    for threshold in PRESET_THRESHOLDS:
        for hold_months in PRESET_HOLD_MONTHS:
            equity, trades = simulate_strategy(
                nav,
                threshold=threshold,
                hold=relativedelta(months=hold_months),
                fees=fees,
                eval_start_idx=eval_start_idx,
            )
            total = float(equity.iloc[-1] / INITIAL_CASH - 1.0)
            yearly = _yearly_table(equity, benchmark_equity)
            completed = [t for t in trades if t.sell_date is not None]
            conclusion, reason = _conclusion(
                eval_span_years=eval_span_years,
                completed_trades=len(completed),
                excess_total=total - benchmark_total,
                yearly=yearly,
            )
            monthly = equity.resample("ME").last().dropna()
            report["combos"].append(
                {
                    "threshold": threshold,
                    "hold_months": hold_months,
                    "total_return": round(total, 6),
                    "benchmark_return": round(benchmark_total, 6),
                    "excess_return": round(total - benchmark_total, 6),
                    "max_drawdown": round(_max_drawdown(equity), 6),
                    "volatility": (
                        round(v, 6)
                        if (v := _annualized_volatility(equity)) is not None
                        else None
                    ),
                    "completed_trades": len(completed),
                    "open_trades": len(trades) - len(completed),
                    "trades": [t.to_dict() for t in trades],
                    "yearly": yearly,
                    "failed_years": [r["year"] for r in yearly if r["failed"]],
                    "conclusion": conclusion,
                    "conclusion_reason": reason,
                    "equity_monthly": {
                        "dates": [d.strftime("%Y-%m-%d") for d in monthly.index],
                        "strategy": [round(float(v / INITIAL_CASH), 6) for v in monthly],
                        "benchmark": [
                            round(float(v / INITIAL_CASH), 6)
                            for v in benchmark_equity.resample("ME").last().dropna()
                        ],
                    },
                }
            )
    return report


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2%}"


def _pct_plain(value: float | None) -> str:
    return "—" if value is None else f"{value:.2%}"


def render_report_markdown(report: dict) -> str:
    """把 run_backtest 的结构化报告渲染成 Markdown 文本报告。"""
    lines: list[str] = []
    title = f"# 诚实回测报告：{report['name'] or '（名称未知）'}（{report['code']}）"
    lines.append(title)
    lines.append("")
    lines.append(
        "定位：验证一句说法在历史上成不成立。只做历史验证，不判断未来涨跌，不提供买卖意见。"
    )
    lines.append("")
    if report["status"] == "refused":
        lines.append(f"**结论：拒绝出结论。** {report['refusal_reason']}")
        lines.append("")
        lines.append("## 披露与局限")
        lines.extend(f"- {d}" for d in report["disclosures"])
        return "\n".join(lines) + "\n"

    lines.append(
        f"数据区间：{report['data_start']} 至 {report['data_end']}；"
        f"样本外评估段自 {report['eval_start']} 开始（此前 {report['warmup_days']} 个交易日为预热段）。"
    )
    lines.append("")
    lines.append("## 六种预设组合结果（全部列示，不做挑选）")
    lines.append("")
    lines.append("| 回撤阈值 | 持有期 | 策略收益 | 基准收益（买入持有） | 超额 | 策略最大回撤 | 策略波动率 | 完成交易 | 结论 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for c in report["combos"]:
        lines.append(
            f"| {c['threshold']:.0%} | {c['hold_months']} 个月 | {_pct(c['total_return'])} | "
            f"{_pct(c['benchmark_return'])} | {_pct(c['excess_return'])} | {_pct_plain(c['max_drawdown'])} | "
            f"{_pct_plain(c['volatility'])} | {c['completed_trades']} 笔 | {c['conclusion']} |"
        )
    lines.append("")
    for c in report["combos"]:
        lines.append(f"## 组合：回撤 {c['threshold']:.0%} 触发 / 持有 {c['hold_months']} 个月")
        lines.append("")
        lines.append(f"结论：**{c['conclusion']}**——{c['conclusion_reason']}")
        lines.append("")
        lines.append("逐年表现（样本外）：")
        lines.append("")
        lines.append("| 年份 | 策略收益 | 基准收益 | 超额 | 策略最大回撤 | 策略波动率 | 是否跑输 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in c["yearly"]:
            lines.append(
                f"| {r['year']} | {_pct(r['strategy_return'])} | {_pct(r['benchmark_return'])} | "
                f"{_pct(r['excess_return'])} | {_pct_plain(r['strategy_max_drawdown'])} | "
                f"{_pct_plain(r['strategy_volatility'])} | {'是（失效年份）' if r['failed'] else '否'} |"
            )
        lines.append("")
        failed = "、".join(str(y) for y in c["failed_years"]) or "无"
        lines.append(f"失效年份清单（策略跑输买入持有的年份）：{failed}")
        lines.append("")
        lines.append("交易明细：")
        lines.append("")
        if c["trades"]:
            lines.append("| 买入日 | 买入净值 | 卖出日 | 卖出净值 | 持有天数 | 买入费 | 卖出费 | 本笔收益 | 状态 |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for t in c["trades"]:
                lines.append(
                    f"| {t['buy_date']} | {t['buy_nav']:.4f} | {t['sell_date'] or '—'} | "
                    f"{t['sell_nav'] if t['sell_nav'] is not None else '—'} | {t['holding_days'] if t['holding_days'] is not None else '—'} | "
                    f"{t['buy_fee']:.2f} | {t['sell_fee'] if t['sell_fee'] is not None else '—'} | "
                    f"{_pct(t['return_pct'])} | {'未平仓' if t['open'] else '已完成'} |"
                )
        else:
            lines.append("（样本外段内从未触发，全程现金。）")
        lines.append("")
    lines.append("## 披露与局限")
    lines.extend(f"- {d}" for d in report["disclosures"])
    return "\n".join(lines) + "\n"
