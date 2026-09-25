"""回归测试：抓取失败与列映射缺失时，不得把"取不到"变成"真实值"。

已修复的两个 bug：

  1. `_fetch_real_holdings` / `_fetch_real_sectors` 的**异常路径**把空结果按
     `_HOLDINGS_CACHE_TTL`（24 小时）缓存。一次网络抖动就会让这只基金的重仓/
     行业整整一天都是空的，而数据其实拿得到。
     现在异常路径用 `_HOLDINGS_FAILURE_TTL`（5 分钟）。
     注意：空结果本身也可能是合法稳态（例如股票持仓为空的债基），所以
     **只有异常路径**改短，正常取到空值的分支仍按 24 小时缓存。

  2. `analysis_service.hold_structure()` 在列名没匹配全时只打一条 warning，
     然后继续用 `col_map.get(k, "")` 取值 + `float(... or 0)` 回退 0，
     把"取不到机构持有比例"显示成"机构持有 0%"。
     现在列映射不全时**不产出任何数据点**。
"""

import time
from unittest.mock import patch

import pandas as pd
import pytest

from services import analysis_service, fund_service


# ---------------------------------------------------------------------------
# 1. 失败缓存必须是短 TTL
# ---------------------------------------------------------------------------


def test_holdings_failure_is_cached_briefly_not_for_a_day():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_hold_em", side_effect=RuntimeError("offline")
    ):
        assert fund_service._fetch_real_holdings("000001") is None
        _, expiry = fund_service._CACHE["holdings:000001"]

    remaining = expiry - time.time()
    assert remaining <= fund_service._HOLDINGS_FAILURE_TTL + 5
    assert remaining < fund_service._HOLDINGS_CACHE_TTL / 10, (
        "抓取失败不得按 24 小时缓存：一次抖动会让该基金重仓空一整天"
    )


def test_sectors_failure_is_cached_briefly_not_for_a_day():
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_industry_allocation_em",
        side_effect=RuntimeError("offline"),
    ):
        assert fund_service._fetch_real_sectors("000001") is None
        _, expiry = fund_service._CACHE["sectors:000001"]

    remaining = expiry - time.time()
    assert remaining <= fund_service._HOLDINGS_FAILURE_TTL + 5
    assert remaining < fund_service._HOLDINGS_CACHE_TTL / 10


def test_successful_holdings_keep_the_long_ttl():
    """正常取到数据仍按 24 小时缓存（季报不常变），避免每次请求都打上游。"""
    frame = pd.DataFrame([{
        "股票代码": "300308", "股票名称": "中际旭创",
        "占净值比例": 6.45, "季度": "2026年2季度股票投资明细",
    }])

    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_portfolio_hold_em", return_value=frame
    ):
        assert fund_service._fetch_real_holdings("000001")
        _, expiry = fund_service._CACHE["holdings:000001"]

    assert expiry - time.time() > fund_service._HOLDINGS_FAILURE_TTL * 10


def test_failure_ttl_is_shorter_than_the_success_ttl():
    assert fund_service._HOLDINGS_FAILURE_TTL < fund_service._HOLDINGS_CACHE_TTL


# ---------------------------------------------------------------------------
# 2. hold_structure 列映射缺失时不得产出 0 填充的点
# ---------------------------------------------------------------------------

COMPLETE_COLUMNS = ["截止日期", "基金家数", "机构持有比例", "个人持有比例", "内部持有比例", "总份额"]

ROW = {
    "截止日期": "2026-06-30",
    "基金家数": 12000,
    "机构持有比例": 45.5,
    "个人持有比例": 54.5,
    "内部持有比例": 2.1,
    "总份额": 3.3e12,
}


def hold_structure_with(columns: list[str]):
    frame = pd.DataFrame([[ROW[column] for column in columns]], columns=columns)
    with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        analysis_service, "_call_akshare", return_value=frame
    ):
        return analysis_service.hold_structure()


def test_complete_column_mapping_produces_real_points():
    result = hold_structure_with(COMPLETE_COLUMNS)

    assert len(result.points) == 1
    point = result.points[0]
    assert point.institution_pct == pytest.approx(45.5)
    assert point.individual_pct == pytest.approx(54.5)
    assert point.fund_count == 12000


@pytest.mark.parametrize("dropped", ["机构持有比例", "个人持有比例", "内部持有比例", "总份额", "基金家数", "截止日期"])
def test_missing_column_produces_no_points_instead_of_zeros(dropped):
    """缺任意一个关键列时，绝不产出用 0 填充的持仓结构点。"""
    columns = [column for column in COMPLETE_COLUMNS if column != dropped]

    result = hold_structure_with(columns)

    assert result.points == [], f"缺少 {dropped} 时不得产出 0 填充的点"


def test_zero_filled_point_would_be_indistinguishable_from_real_zero():
    """说明为什么必须拒绝：真实 0% 与缺失 0% 在数据上完全一样。"""
    result = hold_structure_with([c for c in COMPLETE_COLUMNS if c != "机构持有比例"])

    assert all(point.institution_pct != 0.0 for point in result.points)
    assert result.points == []
