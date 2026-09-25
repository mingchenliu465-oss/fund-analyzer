"""回归测试：市场指数行情缺数据时不得伪造 0。

已修复的 bug（`market_service._fetch_indices`）：
  原实现对缺失字段回退 0.0：
      price  = float(row["price"]) if pd.notna(...) else 0.0
      change = float(row["change_pct"]) if pd.notna(...) else 0.0
      up     = change >= 0
  后果：取不到行情时，指数会显示成 **0.00 点位 / 涨 0.00%**，而且 up=True
  让前端把它渲染成"上涨"。这是把"数据缺失"伪装成真实的市场事实。

  中证全债补齐路径同样有 `else: bond_change = 0.0` 的兜底。

修复原则：缺数据的指数**跳过不显示**，不补 0、不猜方向。
"""

from unittest.mock import patch

import pandas as pd
import pytest

from services import market_service


def spot_frame(rows):
    """与 stock_zh_index_spot_sina 重命名后的结构一致。"""
    return pd.DataFrame(rows, columns=["code", "name", "price", "change_pct"])


def indices_from(frame, bond_frame=None):
    with patch.object(market_service, "_call_akshare", return_value=frame), patch.object(
        market_service, "_fetch_bond_index_history",
        return_value=pd.DataFrame() if bond_frame is None else bond_frame,
    ):
        return market_service._fetch_indices()


# ---------------------------------------------------------------------------
# 缺失 -> 跳过，而不是 0
# ---------------------------------------------------------------------------


def test_index_with_missing_price_is_skipped_not_zeroed():
    frame = spot_frame([
        ["sh000001", "上证指数", 3200.0, 0.5],
        ["sz399001", "深证成指", None, 1.0],
    ])

    result = indices_from(frame)

    assert [item.name for item in result] == ["上证指数"]
    assert all(item.value != "0.00" for item in result)


def test_index_with_missing_change_is_skipped_not_zeroed():
    """涨跌幅缺失时不能显示成"涨 0.00%"，更不能标成上涨。"""
    frame = spot_frame([
        ["sh000001", "上证指数", 3200.0, 0.5],
        ["sz399001", "深证成指", 10500.0, None],
    ])

    result = indices_from(frame)

    assert [item.name for item in result] == ["上证指数"]
    assert all(not (item.change == 0.0 and item.name == "深证成指") for item in result)


def test_nan_change_is_not_rendered_as_flat():
    frame = spot_frame([
        ["sh000300", "沪深300", 4000.0, float("nan")],
    ])

    assert indices_from(frame) == []


def test_no_index_is_ever_reported_with_zero_change_when_data_is_missing():
    frame = spot_frame([
        ["sh000001", "上证指数", None, None],
        ["sz399001", "深证成指", None, 1.0],
        ["sh000300", "沪深300", 4000.0, None],
    ])

    assert indices_from(frame) == []


# ---------------------------------------------------------------------------
# 正常数据不受影响（防回归）
# ---------------------------------------------------------------------------


def test_complete_snapshot_is_returned_unchanged():
    frame = spot_frame([
        ["sh000001", "上证指数", 3200.55, 0.42],
        ["sh000300", "沪深300", 4000.10, -0.31],
    ])

    result = indices_from(frame)

    assert [item.name for item in result] == ["上证指数", "沪深300"]
    by_name = {item.name: item for item in result}
    assert by_name["上证指数"].value == "3,200.55"
    assert by_name["上证指数"].change == 0.42
    assert by_name["上证指数"].up is True
    assert by_name["沪深300"].up is False


def test_zero_change_from_real_data_is_kept():
    """真实的 0% 涨跌是合法数据，必须保留（与"缺失"区分开）。"""
    frame = spot_frame([["sh000001", "上证指数", 3200.0, 0.0]])

    result = indices_from(frame)

    assert len(result) == 1
    assert result[0].change == 0.0
    assert result[0].up is True


# ---------------------------------------------------------------------------
# 中证全债补齐路径
# ---------------------------------------------------------------------------


def test_bond_index_is_skipped_when_change_cannot_be_determined():
    """只有一条历史（无法算涨跌幅）时，不得补 0.00%。"""
    bond = pd.DataFrame({"净值日期": pd.to_datetime(["2026-09-18"]), "close": [210.5]})

    result = indices_from(spot_frame([["sh000001", "上证指数", 3200.0, 0.5]]), bond)

    assert [item.name for item in result] == ["上证指数"]
    assert all(item.name != "中证全债" for item in result)


def test_bond_index_change_is_computed_from_two_real_closes():
    bond = pd.DataFrame({
        "净值日期": pd.to_datetime(["2026-09-17", "2026-09-18"]),
        "close": [210.0, 212.1],
    })

    result = indices_from(spot_frame([["sh000001", "上证指数", 3200.0, 0.5]]), bond)

    bond_item = next(item for item in result if item.name == "中证全债")
    assert bond_item.change == pytest.approx(1.0, abs=0.01)
    assert bond_item.value == "212.10"


def test_bond_index_prefers_a_real_change_pct_column():
    bond = pd.DataFrame({
        "净值日期": pd.to_datetime(["2026-09-18"]),
        "close": [210.5],
        "change_pct": [0.37],
    })

    result = indices_from(spot_frame([["sh000001", "上证指数", 3200.0, 0.5]]), bond)

    bond_item = next(item for item in result if item.name == "中证全债")
    assert bond_item.change == pytest.approx(0.37)
