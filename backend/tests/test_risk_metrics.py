"""P0-4 回归测试：风险指标真实性。

背景（审计，2026-09-19）：
  * `fund_service._risk_profile()` 是一张**硬编码查表**：货币型→("低", 8)、
    债券型→("中低", 28)、混合型→("中", 52)、ETF联接→("中高", 65)、
    ETF→("高", 80/85)；其余类型才用波动率分档，分数同样是硬编码的
    10/30/50/68/80。缺 volatility 时返回 ("中高", 70)。
  * `_risk_level_for_type()` 按基金类型字符串直接猜等级。
  * `_style_for_type()` 由基金类型猜"投资风格"（债券型→"稳健收益" 等）。
  * `excess.std() == 0` 时夏普写成 0.0（缺数据变成 0）。
  * `models.FundMetrics` 把 risk_level/risk_score 声明为**必填**，从类型层面
    强制必须编一个值。
  * 前端还各有一份 80/60/40/20/10 的硬编码映射。

核心口径：
    真实风险指标（volatility / max_drawdown / sharpe）> 明确 unavailable > 主观评分
    risk_score 没有可复现定义 -> 一律 None，绝不编造 0-100 分数。
    risk_level 只由**真实年化波动率**推导，不按基金类型查表。
"""

from datetime import date, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from models.fund import FundMetrics
from services import analysis_service, fund_service, review_service


def _recent_dates(count: int, span_days: int | None = None) -> list[str]:
    """最近 count 个观测日（含今天）。

    span_days 用于把首个观测日推到足够久以前，以覆盖"近一年收益"这类
    需要 >= 365 天历史的计算。
    """
    from datetime import datetime

    today = datetime.now().date()
    if span_days is None:
        return [(today - timedelta(days=offset)).isoformat() for offset in reversed(range(count))]
    step = span_days / max(count - 1, 1)
    return [
        (today - timedelta(days=int(round(span_days - index * step)))).isoformat()
        for index in range(count)
    ]


def nav_frame(cumulative: list[float], span_days: int | None = None):
    """与 _fetch_nav_history 同构的净值帧；单位净值 == 累计净值（无分红）。"""
    return pd.DataFrame(
        {
            "净值日期": pd.to_datetime(_recent_dates(len(cumulative), span_days)),
            "单位净值": cumulative,
            "累计净值": cumulative,
            "日增长率": [0.0] * len(cumulative),
        }
    )


def year_long_nav_frame():
    """跨度超过 365 天的净值帧，使近一年收益可计算。"""
    return nav_frame([1.00, 1.10, 1.20, 1.15, 1.30], span_days=400)


def stub_fund(code="000001", name="测试基金", ftype="股票型"):
    return fund_service.FundSummary(
        code=code, name=name, company="测试公司", type=ftype,
        nav=1.0, nav_date=None, nav_status=None,
        change_pct=None, one_year_return=None, risk_level=None, size="-", heat=None,
    )


# ---------------------------------------------------------------------------
# 1. 有真实历史收益 -> 风险指标正常计算
# ---------------------------------------------------------------------------


def test_real_history_metrics_are_computed_from_the_series():
    frame = nav_frame([1.00, 1.10, 1.05, 1.20, 1.15, 1.30])

    metrics = fund_service._metrics_from_nav(frame, "股票型")

    assert metrics.volatility > 0
    assert metrics.max_drawdown < 0  # 真实出现过回撤
    assert metrics.sharpe is not None


def test_volatility_matches_hand_computed_value():
    """波动率必须能用真实序列复现（不是查表值）。

    口径说明：实现把累计净值取成 numpy 数组后调 `.std()`，即**总体标准差
    （ddof=0）**，而不是 pandas 的样本标准差（ddof=1）。这里按实现口径复算，
    确认公式可复现。ddof 属于估计量约定（大样本下差异可忽略），不是
    "缺数据变 0" 一类真实性问题，因此不在本轮改动范围。
    """
    values = [1.00, 1.10, 1.05, 1.20, 1.15, 1.30]
    frame = nav_frame(values)

    arr = np.asarray(values, dtype=float)
    expected = float((arr[1:] / arr[:-1] - 1).std() * (252 ** 0.5))

    assert fund_service._metrics_from_nav(frame, "股票型").volatility == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 2. 无历史数据 -> 风险指标不是 0（而是直接拒绝计算）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rows", [0, 1, 2])
def test_insufficient_history_refuses_to_produce_risk_metrics(rows):
    with pytest.raises(ValueError):
        fund_service._metrics_from_nav(nav_frame([1.0] * rows), "股票型")


def test_empty_series_never_yields_zero_volatility():
    """没有数据时必须报错，绝不能得到 volatility == 0。"""
    try:
        metrics = fund_service._metrics_from_nav(nav_frame([]), "股票型")
    except ValueError:
        return
    pytest.fail(f"空序列不得产出风险指标，却得到 volatility={metrics.volatility}")


# ---------------------------------------------------------------------------
# 3. 波动率真实为 0 -> 允许返回 0
# ---------------------------------------------------------------------------


def test_genuinely_flat_series_yields_zero_volatility_and_zero_drawdown():
    """这是**真实计算出来的 0**，必须允许。"""
    metrics = fund_service._metrics_from_nav(nav_frame([1.0, 1.0, 1.0, 1.0]), "股票型")

    assert metrics.volatility == 0.0
    assert metrics.max_drawdown == 0.0


def test_zero_variance_sharpe_is_none_not_zero():
    """方差为 0 时夏普无定义（分母为 0）-> None，不得写成 0。"""
    metrics = fund_service._metrics_from_nav(nav_frame([1.0, 1.0, 1.0, 1.0]), "股票型")

    assert metrics.sharpe is None


# ---------------------------------------------------------------------------
# 4. risk_score：没有可复现定义 -> 一律不可用，不补 0
# ---------------------------------------------------------------------------


def test_risk_score_is_always_unavailable():
    """任何基金、任何波动率下 risk_score 都是 None。"""
    for values in ([1.0, 1.1, 1.2], [1.0, 1.0, 1.0], [1.0, 2.0, 0.5, 3.0]):
        metrics = fund_service._metrics_from_nav(nav_frame(values), "股票型")
        assert metrics.risk_score is None
        assert metrics.risk_score != 0

    for ftype in ("货币型", "债券型", "混合型", "ETF", "ETF联接", "股票型"):
        metrics = fund_service._metrics_from_nav(nav_frame([1.0, 1.1, 1.2]), ftype)
        assert metrics.risk_score is None, f"{ftype} 不得产出伪造评分"


def test_risk_score_is_optional_in_the_model():
    """模型层面必须允许 None —— 否则又会强制调用方编一个值。"""
    model = FundMetrics(max_drawdown=-0.1, volatility=0.15, sharpe=0.5)

    assert model.risk_score is None
    assert model.risk_level is None


def test_old_hardcoded_risk_profile_table_is_gone():
    assert not hasattr(fund_service, "_risk_profile"), "硬编码评分表必须已删除"
    assert not hasattr(fund_service, "_risk_level_for_type"), "类型->等级查表必须已删除"
    assert not hasattr(fund_service, "_style_for_type"), "类型->风格推断必须已删除"


# ---------------------------------------------------------------------------
# 5. risk_level：只由真实波动率推导，不按基金类型
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "volatility,expected",
    [(0.0, "低"), (0.049, "低"), (0.05, "中低"), (0.119, "中低"),
     (0.12, "中"), (0.179, "中"), (0.18, "中高"), (0.249, "中高"), (0.25, "高")],
)
def test_risk_level_is_a_monotone_function_of_real_volatility(volatility, expected):
    assert fund_service.risk_level_from_volatility(volatility) == expected


def test_risk_level_is_none_when_volatility_is_unknown():
    assert fund_service.risk_level_from_volatility(None) is None


def test_risk_level_does_not_depend_on_fund_type():
    """同一波动率下，不同类型必须得到同一个等级（原实现按类型给不同答案）。"""
    same_volatility = 0.30
    levels = {
        ftype: fund_service.risk_level_from_volatility(same_volatility)
        for ftype in ("货币型", "债券型", "混合型", "ETF", "ETF联接", "股票型")
    }

    assert set(levels.values()) == {"高"}, levels


def test_risk_level_reflects_real_series_not_label():
    """低波动真实序列（即使类型是"股票型"）应得低等级。"""
    metrics = fund_service._metrics_from_nav(nav_frame([1.0, 1.0001, 1.0, 1.0001]), "股票型")

    assert metrics.volatility < 0.05
    assert metrics.risk_level == "低"


# ---------------------------------------------------------------------------
# 6. investment_style：无可靠依据 -> 不猜
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ftype", ["货币型", "债券型", "混合型", "ETF", "ETF联接", "股票型"])
def test_investment_style_is_unavailable_for_every_fund_type(ftype):
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund(ftype=ftype)]), patch.object(
        fund_service, "_fetch_nav_history", return_value=nav_frame([1.0, 1.1, 1.2, 1.15])
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        detail = fund_service.get_by_code("000001")

    assert detail.investment_style is None


# ---------------------------------------------------------------------------
# 7. 列表/排行榜不再按类型标注风险等级
# ---------------------------------------------------------------------------


def test_fund_list_does_not_label_risk_by_type():
    upstream = pd.DataFrame(
        [{"基金代码": "000001", "基金简称": "某股票基金", "基金类型": "股票型-普通"}]
    )
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_name_em", return_value=upstream
    ), patch.object(
        fund_service, "_build_enrichment_lookup", return_value={}
    ), patch.object(
        fund_service, "_etf_registry", return_value={}
    ):
        funds = fund_service._load_fund_list()

    assert funds
    for fund in funds:
        assert fund.risk_level is None


# ---------------------------------------------------------------------------
# 8. 组合复盘不再由权益占比推导风险等级/评分
# ---------------------------------------------------------------------------


def test_daily_review_drops_the_derived_risk_segment():
    attribution = {
        "today_return": 10.0,
        "today_return_pct": 1.0,
        "contributions": [
            {"fund_code": "000001", "fund_name": "测试基金", "fund_type": "股票型",
             "current_value": 1000.0, "nav_stale": False},
        ],
        "summary": {"has_stale_nav": False, "top_gainer_name": None, "top_loser_name": None},
    }

    with patch.object(review_service.portfolio_service, "attribution", return_value=attribution), patch.object(
        review_service, "_load_recent_snapshots", return_value=[]
    ):
        result = review_service.generate_daily_review("rules")

    # 风险段落依赖 risk_level，现在恒为 None，因此不再输出主观风险结论。
    assert not any(segment["type"] == "风险" for segment in result["segments"])
    assert not any("评分" in segment["text"] for segment in result["segments"])


def test_review_service_no_longer_derives_risk_scores():
    assert not hasattr(review_service, "_derive_risk_level")
    assert not hasattr(review_service, "_derive_risk_score")


# ---------------------------------------------------------------------------
# 9. 与 P0-6 freshness 的衔接：历史指标必须与当前状态区分开
# ---------------------------------------------------------------------------


def test_inactive_fund_keeps_historical_metrics_but_no_current_nav():
    """已终止基金的历史波动/回撤是**历史事实**，可以保留；
    但不得把最后一条净值当作当前净值。"""
    stale_frame = pd.DataFrame(
        {
            "净值日期": pd.to_datetime(["2020-11-30", "2020-12-01", "2020-12-31"]),
            "单位净值": [1.20, 1.22, 1.25],
            "累计净值": [1.40, 1.42, 1.45],
            "日增长率": [0.0, 0.0, 0.0],
        }
    )

    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=stale_frame
    ), patch.object(
        fund_service, "_fetch_real_sectors", return_value=None
    ), patch.object(
        fund_service, "_fetch_real_holdings", return_value=None
    ), patch.object(
        fund_service, "_fetch_basic_info", return_value={}
    ):
        detail = fund_service.get_by_code("000001")

    # 当前状态：必须不可用
    assert detail.nav is None
    assert detail.change_pct is None
    assert detail.nav_status == fund_service.NAV_STATUS_INACTIVE
    assert detail.nav_date == "2020-12-31"

    # 历史指标：保留真实计算值，且不含任何伪造评分
    assert detail.metrics.volatility > 0
    assert detail.metrics.max_drawdown <= 0
    assert detail.metrics.risk_score is None


def test_stale_nav_is_not_treated_as_current_for_risk(calendar_unused=None):
    """P0-6 闸门不得被本轮破坏：过期净值仍不能作为当前值。"""
    from services import portfolio_service

    with patch.object(portfolio_service, "_get_holding_nav", return_value=(1.25, "2020-12-31")):
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")

    assert nav is None
    assert nav_date == "2020-12-31"
    assert stale is True


def test_freshness_status_constants_are_intact():
    """确认 P0-6 的状态模型未被本轮改动。"""
    assert fund_service.NAV_STATUS_FRESH == "fresh"
    assert fund_service.NAV_STATUS_STALE == "stale"
    assert fund_service.NAV_STATUS_INACTIVE == "inactive"
    assert fund_service.NAV_STATUS_UNAVAILABLE == "unavailable"
    assert fund_service.NAV_STATUS_UNKNOWN == "unknown"
    assert fund_service.nav_data_status(date(2020, 12, 31)) == fund_service.NAV_STATUS_INACTIVE


# ---------------------------------------------------------------------------
# 10. 解读文案不再依赖伪造评分
# ---------------------------------------------------------------------------


def test_commentary_does_not_use_risk_score():
    with patch.object(fund_service, "_load_fund_list", return_value=[stub_fund()]), patch.object(
        fund_service, "_fetch_nav_history", return_value=year_long_nav_frame()
    ):
        commentary = analysis_service.commentary("000001")

    assert "评分" not in commentary.suitable_for
    assert commentary.suitable_for  # 有波动率时给出与等级一致的文案
