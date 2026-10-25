"""诚实回测引擎第一层验证（机器验证）：已知答案、防未来函数、费用边界、
永不触发退化。期望值全部由测试内独立手算，不调用引擎内部函数反推。
"""

from dateutil.relativedelta import relativedelta

import pandas as pd
import pytest

from services.backtest_service import (
    FeeModel,
    INITIAL_CASH,
    simulate_buy_and_hold,
    simulate_strategy,
)

FEES = FeeModel()  # 申购 0.15%（示例口径）；赎回 <7 日 1.5% 法定下限，≥7 日 0.5% 假设值


def _series(values, start="2023-01-02"):
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


# ---------------------------------------------------------------------------
# 已知答案：构造序列，触发点、成交价、费用、最终权益全部手算核对
# ---------------------------------------------------------------------------

def test_known_answer_single_trade():
    # 前 302 天净值 2.00（窗口高点 2.00）；第 302 天（0 起）跌到 1.80，
    # 回撤恰为 10%，阈值 10% 组合应在当天以 1.80 买入；之后涨到 2.16 平台。
    values = [2.00] * 302 + [1.80] + [2.16] * 200
    nav = _series(values)
    equity, trades = simulate_strategy(
        nav, threshold=0.10, hold=relativedelta(months=6), fees=FEES, eval_start_idx=250
    )
    completed = [t for t in trades if t.sell_date is not None]
    assert len(completed) == 1
    trade = completed[0]
    assert trade.buy_date == nav.index[302]
    assert trade.buy_nav == pytest.approx(1.80)
    assert trade.sell_nav == pytest.approx(2.16)
    # 手算：申购费 100000*0.15% = 150；份额 = 99850/1.80；卖出额 = 份额*2.16 = 119820.00
    assert trade.buy_fee == pytest.approx(150.0)
    gross = 99850 / 1.80 * 2.16
    assert gross == pytest.approx(119820.0)
    # 持有约 6 个月（≥7 日）→ 赎回费走 0.5% 假设档
    assert trade.holding_days >= 7
    assert trade.sell_fee == pytest.approx(gross * 0.005)
    assert equity.iloc[-1] == pytest.approx(gross * (1 - 0.005))
    assert trade.return_pct == pytest.approx(gross * (1 - 0.005) / INITIAL_CASH - 1)


def test_no_trigger_before_threshold_reached():
    # 回撤只到 9%：阈值 10% 不应触发
    values = [2.00] * 300 + [1.82] * 100
    nav = _series(values)
    _, trades = simulate_strategy(
        nav, threshold=0.10, hold=relativedelta(months=6), fees=FEES, eval_start_idx=250
    )
    assert trades == []


# ---------------------------------------------------------------------------
# 防未来函数：改动样本外某日之后的全部净值，此前决策与权益逐点不变
# ---------------------------------------------------------------------------

def test_anti_lookahead_future_mutation_does_not_change_past():
    import numpy as np

    rng = np.random.default_rng(42)
    returns = rng.normal(0.0004, 0.013, 700)
    values = 2.0 * np.cumprod(1 + returns)
    nav = _series(values, start="2020-01-02")
    kwargs = dict(
        threshold=0.10, hold=relativedelta(months=6), fees=FEES, eval_start_idx=250
    )
    equity_before, trades_before = simulate_strategy(nav, **kwargs)

    cutoff_idx = 500
    cutoff_date = nav.index[cutoff_idx]
    mutated = nav.copy()
    mutated.iloc[cutoff_idx + 1 :] = mutated.iloc[cutoff_idx + 1 :] * 4.0 + 1.0
    equity_after, trades_after = simulate_strategy(mutated, **kwargs)

    # 截止日（含）之前的权益必须逐点完全一致
    pd.testing.assert_series_equal(
        equity_before.loc[:cutoff_date], equity_after.loc[:cutoff_date]
    )
    # 在截止日前已完成的交易必须完全一致
    done_before = [t for t in trades_before if t.sell_date is not None and t.sell_date <= cutoff_date]
    done_after = [t for t in trades_after if t.sell_date is not None and t.sell_date <= cutoff_date]
    assert len(done_before) >= 1  # 保证本测试不是空转
    assert len(done_before) == len(done_after)
    for a, b in zip(done_before, done_after):
        assert (a.buy_date, a.buy_nav, a.sell_date, a.sell_nav, a.sell_fee) == (
            b.buy_date, b.buy_nav, b.sell_date, b.sell_nav, b.sell_fee,
        )
    # 截止日之后两条权益必须出现差异（保证突变真的生效，测试非空转）
    assert not equity_before.loc[cutoff_date:].equals(equity_after.loc[cutoff_date:])


# ---------------------------------------------------------------------------
# 费用边界：持有 6 天卖出必须命中 1.5% 法定档
# ---------------------------------------------------------------------------

def test_fee_tier_function_boundaries():
    assert FEES.redemption_rate(0) == 0.015
    assert FEES.redemption_rate(6) == 0.015
    assert FEES.redemption_rate(7) == FEES.redemption_rate_after_7d


def test_short_hold_six_days_hits_15pct_redemption_fee():
    # 用自然日序列保证持有天数精确为 6 天
    idx = pd.date_range("2024-01-01", periods=300, freq="D")
    nav = pd.Series(2.00, index=idx, dtype=float)
    buy_day = pd.Timestamp("2024-03-04")
    nav.loc[buy_day] = 1.80  # 回撤恰 10%，触发买入
    nav.loc[buy_day + pd.Timedelta(days=1) :] = 1.98
    equity, trades = simulate_strategy(
        nav, threshold=0.10, hold=relativedelta(days=6), fees=FEES, eval_start_idx=10
    )
    completed = [t for t in trades if t.sell_date is not None]
    assert len(completed) == 1
    trade = completed[0]
    assert trade.buy_date == buy_day
    assert trade.holding_days == 6
    # 手算：份额 = 99850/1.80；卖出额 = 份额*1.98 = 109835.00；费 = 1.5%
    gross = 99850 / 1.80 * 1.98
    assert gross == pytest.approx(109835.0)
    assert trade.sell_fee == pytest.approx(gross * 0.015)
    assert equity.iloc[-1] == pytest.approx(gross * (1 - 0.015))


# ---------------------------------------------------------------------------
# 基准一致性：永不触发时策略退化为现金（全程不亏不赚），基准只亏一次申购费
# ---------------------------------------------------------------------------

def test_never_trigger_degenerates_to_cash():
    nav = _series([1.50] * 800, start="2020-01-02")
    equity, trades = simulate_strategy(
        nav, threshold=0.10, hold=relativedelta(months=6), fees=FEES, eval_start_idx=250
    )
    assert trades == []
    assert (equity == INITIAL_CASH).all()
    benchmark = simulate_buy_and_hold(nav, fees=FEES, eval_start_idx=250)
    benchmark_return = benchmark.iloc[-1] / INITIAL_CASH - 1
    assert benchmark_return == pytest.approx(-FEES.subscription_rate)
    strategy_return = equity.iloc[-1] / INITIAL_CASH - 1
    assert strategy_return == 0.0
    assert strategy_return > benchmark_return
