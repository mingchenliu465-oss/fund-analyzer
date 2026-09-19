"""P0-3 回归测试：持仓/行业必须锁定单一「报告期」。

背景（实测，2026-09-19）：
    上游 `fund_portfolio_hold_em(date="")` 与
    `fund_portfolio_industry_allocation_em(date="")` 会一次性返回**多个报告期**，
    且行序不保证最新在前。

    实测 000001 的持仓 frame 顺序是
        ['2026年1季度股票投资明细', '2026年2季度股票投资明细']
    原实现取 `iloc[0]` → 拿到的是**旧季度**：中际旭创 4.31%，而最新披露的
    2 季度是 6.45%。as_of 也跟着标成旧季度。

    实测 000001 的行业配置 frame 含 2026-06-30 与 2026-03-31 两期，
    原实现遍历全部行并按行业名相加：制造业 72.78 + 61.14 = 133.92，
    再整体缩放回 100% → 展示 87.8%。这是两个季度叠加出来的、数据源从未
    披露过的配置。

这里的测试锁定：取最新报告期、权重原样输出、不做跨期相加、不做归一化缩放、
缺失权重不得变成 0。
"""

from unittest.mock import patch

import pandas as pd
import pytest

from models.fund import TopHolding
from services import fund_service, portfolio_service

QUARTER_OLD = "2026年1季度股票投资明细"
QUARTER_NEW = "2026年2季度股票投资明细"


@pytest.fixture(autouse=True)
def _isolate_period_state():
    """报告期字典是模块级全局状态，每个用例都必须从干净状态开始。"""
    with patch.dict(fund_service._HOLDINGS_AS_OF, {}, clear=True), patch.dict(
        fund_service._SECTORS_AS_OF, {}, clear=True
    ):
        yield


def holdings_frame() -> pd.DataFrame:
    """复刻上游真实布局：旧季度在前，新季度在后（顺序与实测一致）。"""
    return pd.DataFrame(
        [
            {"股票代码": "300308", "股票名称": "中际旭创", "占净值比例": 4.31, "季度": QUARTER_OLD},
            {"股票代码": "688012", "股票名称": "中微公司", "占净值比例": 3.07, "季度": QUARTER_OLD},
            {"股票代码": "300308", "股票名称": "中际旭创", "占净值比例": 6.45, "季度": QUARTER_NEW},
            {"股票代码": "688347", "股票名称": "华虹公司", "占净值比例": 5.57, "季度": QUARTER_NEW},
        ]
    )


def sectors_frame() -> pd.DataFrame:
    """复刻上游真实布局：同一 frame 里混着两个报告期。"""
    return pd.DataFrame(
        [
            {"行业类别": "制造业", "占净值比例": 72.78, "截止时间": "2026-06-30"},
            {"行业类别": "信息传输、软件和信息技术服务业", "占净值比例": 7.18, "截止时间": "2026-06-30"},
            {"行业类别": "制造业", "占净值比例": 61.14, "截止时间": "2026-03-31"},
        ]
    )


# ---------------------------------------------------------------------------
# 报告期解析
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,expected",
    [
        (QUARTER_OLD, (2026, 1)),
        (QUARTER_NEW, (2026, 2)),
        ("2026年4季度股票投资明细", (2026, 4)),
        ("2026-06-30", (2026, 2)),
        ("2026-03-31", (2026, 1)),
        ("2026-12-31", (2026, 4)),
        ("2026Q1", (2026, 1)),
        ("2026q3", (2026, 3)),
        ("", (0, 0)),
        (None, (0, 0)),
        ("不是报告期", (0, 0)),
    ],
)
def test_report_period_is_parsed_into_a_sortable_key(label, expected):
    assert fund_service._report_period_sort_key(label) == expected


# ---------------------------------------------------------------------------
# 持仓：必须取最新报告期
# ---------------------------------------------------------------------------


def test_holdings_use_newest_report_period_not_first_row():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_hold_em", return_value=holdings_frame()
    ):
        holdings = fund_service._fetch_real_holdings("000001")

    assert holdings is not None
    # 新季度的权重，而不是 iloc[0] 所在旧季度的 4.31 / 3.07
    assert [row.weight for row in holdings] == [6.45, 5.57]
    assert [row.name for row in holdings] == ["中际旭创", "华虹公司"]


def test_holdings_as_of_reports_the_newest_period():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_hold_em", return_value=holdings_frame()
    ):
        fund_service._fetch_real_holdings("000001")

    assert fund_service._HOLDINGS_AS_OF["000001"] == QUARTER_NEW


def test_holdings_refuse_to_guess_when_period_is_unparsable():
    frame = holdings_frame()
    frame["季度"] = "某期"

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_hold_em", return_value=frame
    ):
        assert fund_service._fetch_real_holdings("000001") is None

    assert "000001" not in fund_service._HOLDINGS_AS_OF


def test_holdings_with_missing_weight_are_skipped_not_zeroed():
    """权重缺失不能变成 0 —— 0% 权重等于宣称这只持仓不存在。"""
    frame = pd.DataFrame(
        [
            {"股票代码": "300308", "股票名称": "中际旭创", "占净值比例": None, "季度": QUARTER_NEW},
            {"股票代码": "688347", "股票名称": "华虹公司", "占净值比例": 5.57, "季度": QUARTER_NEW},
        ]
    )

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_hold_em", return_value=frame
    ):
        holdings = fund_service._fetch_real_holdings("000001")

    assert holdings is not None
    assert [row.name for row in holdings] == ["华虹公司"]
    assert all(row.weight != 0 for row in holdings)


# ---------------------------------------------------------------------------
# 行业配置：单期 + 原样输出
# ---------------------------------------------------------------------------


def test_sectors_do_not_mix_report_periods():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_industry_allocation_em", return_value=sectors_frame()
    ):
        sectors = fund_service._fetch_real_sectors("000001")

    assert sectors is not None
    assert {sector.name for sector in sectors} == {"制造业", "信息传输、软件和信息技术服务业"}
    # 跨期相加会得到 133.92；缩放回 100% 会得到 94.92。
    assert sectors[0].name == "制造业"
    assert sectors[0].weight == 72.78


def test_sectors_preserve_true_weights_instead_of_rescaling_to_100():
    """合计不足 100% 是真实的（未披露部分），不能被"修正"成 100%。"""
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_industry_allocation_em", return_value=sectors_frame()
    ):
        sectors = fund_service._fetch_real_sectors("000001")

    assert sectors is not None
    assert sum(sector.weight for sector in sectors) == pytest.approx(79.96)
    assert sum(sector.weight for sector in sectors) != pytest.approx(100.0)


def test_sectors_as_of_reports_the_newest_period():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_industry_allocation_em", return_value=sectors_frame()
    ):
        fund_service._fetch_real_sectors("000001")

    assert fund_service._SECTORS_AS_OF["000001"] == "2026-06-30"


def test_sectors_refuse_to_merge_when_report_period_column_is_absent():
    """没有报告期就无法证明这些权重属于同一时点，不能拼成一张配置图。"""
    frame = sectors_frame().drop(columns=["截止时间"])

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_industry_allocation_em", return_value=frame
    ):
        assert fund_service._fetch_real_sectors("000001") is None


# ---------------------------------------------------------------------------
# 底层重叠：只用同期持仓比较，且 as_of 必须真实
# ---------------------------------------------------------------------------


def _holdings_stub(period: str):
    def _inner(code: str):
        fund_service._HOLDINGS_AS_OF[code] = period
        return [
            TopHolding(name="中际旭创", code="300308", weight=12.0),
            TopHolding(name="华虹公司", code="688347", weight=8.0),
        ]

    return _inner


def test_overlap_pairs_carry_the_real_report_period():
    with patch.object(fund_service, "_fetch_real_holdings", side_effect=_holdings_stub(QUARTER_NEW)):
        status, pairs = portfolio_service._build_overlap_pairs({"000001": 1000.0, "110022": 500.0})

    assert status == "available"
    assert pairs
    assert pairs[0]["data_as_of"] == QUARTER_NEW
    assert pairs[0]["data_as_of"] != "2024"
    assert pairs[0]["overlap_pct"] == pytest.approx(20.0)


def test_overlap_refuses_to_compare_different_report_periods():
    """跨期求交集会把两个季度之间的正常调仓误算成"重叠"。"""
    periods = {"000001": QUARTER_OLD, "110022": QUARTER_NEW}

    def _stub(code: str):
        fund_service._HOLDINGS_AS_OF[code] = periods[code]
        return [TopHolding(name="中际旭创", code="300308", weight=12.0)]

    with patch.object(fund_service, "_fetch_real_holdings", side_effect=_stub):
        status, pairs = portfolio_service._build_overlap_pairs({"000001": 1000.0, "110022": 500.0})

    assert pairs == []
    assert status == "period_mismatch"
