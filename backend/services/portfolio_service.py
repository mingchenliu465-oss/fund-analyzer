"""持仓管理服务：CRUD + 实时净值计算。

净值获取策略：
- 批量查询（list_holdings / portfolio_summary）：优先从已缓存的基金列表
  （_load_fund_list, TTL 1 小时, 启动预热）获取 NAV，避免 N+1 次 akshare 调用。
- 单条查询（add_holding / get_holding / mark_sold / update_holding）：调用
  fund_service.get_by_code() 获取实时净值（含 akshare 调用，3-8 秒）。
"""

from __future__ import annotations

import logging
from typing import Any

from database import get_connection
from models.portfolio import HoldingCreate, HoldingItem, PortfolioSummary, SellRequest
from services import fund_service

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> dict:
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# NAV 批量查询（基于缓存基金列表，无 akshare 调用）
# ---------------------------------------------------------------------------

def _build_nav_map() -> dict[str, float]:
    """从已缓存的基金列表构建 code → 当前净值 映射。

    数据来源：fund_service._load_fund_list()，TTL 1 小时，启动时后台预热。
    该列表的 nav 字段来自 akshare 公募基金排行榜（fund_open_fund_rank_em），
    包含全市场基金的实时单位净值和日涨跌幅。

    注意：此映射仅用于组合总览的快速展示和盈亏计算，不适用于需要完整
    基金详情的场景（如基金详情页、历史净值、分析页面）。
    """
    nav_map: dict[str, float] = {}
    try:
        funds = fund_service._load_fund_list()
        for f in funds:
            if f.nav > 0:
                nav_map[f.code] = f.nav
    except Exception as exc:
        logger.warning("Failed to build NAV map from fund list: %s", exc)
    return nav_map


def _enrich_holding_from_map(row: dict, nav_map: dict[str, float]) -> HoldingItem:
    """使用预构建的 NAV 映射表构造 HoldingItem（无 akshare 调用）。

    与 _enrich_holding() 的区别：
    - _enrich_holding()：调用 fund_service.get_by_code() 获取实时净值（含 akshare）
    - _enrich_holding_from_map()：从预构建的 dict 取净值，O(1) 查找，无网络调用

    用于 list_holdings / portfolio_summary 等批量查询场景。
    """
    code = row["fund_code"]
    current_nav = nav_map.get(code)

    shares = float(row["shares"])
    buy_amount = float(row["buy_amount"])
    cost = buy_amount + float(row.get("fee", 0))

    current_value = round(shares * current_nav, 2) if current_nav else None
    profit = round(current_value - cost, 2) if current_value is not None else None
    profit_pct = round(profit / cost * 100, 2) if profit is not None and cost > 0 else None

    return HoldingItem(
        id=row["id"],
        fund_code=code,
        fund_name=row["fund_name"],
        fund_type=row.get("fund_type", ""),
        buy_date=row["buy_date"],
        buy_amount=buy_amount,
        buy_nav=float(row["buy_nav"]),
        shares=shares,
        fee=float(row.get("fee", 0)),
        notes=row.get("notes", ""),
        is_sold=bool(row.get("is_sold", 0)),
        sell_date=row.get("sell_date"),
        sell_amount=float(row["sell_amount"]) if row.get("sell_amount") else None,
        sell_nav=float(row["sell_nav"]) if row.get("sell_nav") else None,
        current_nav=current_nav,
        current_value=current_value,
        cost=cost,
        profit=profit,
        profit_pct=profit_pct,
    )


# ---------------------------------------------------------------------------
# 单条实时查询（保留原有逻辑，用于 add/sell/edit 等单条操作）
# ---------------------------------------------------------------------------

def _enrich_holding(row: dict) -> HoldingItem:
    """为一条持仓记录补充当前净值、市值、盈亏。

    数据来源：fund_service.get_by_code()，调用 akshare 获取实时净值
    （约 3-8 秒）。用于单条持仓的精确净值查询。

    批量场景请使用 _enrich_holding_from_map() 以避免 N+1 问题。
    """
    code = row["fund_code"]
    current_nav = None
    try:
        detail = fund_service.get_by_code(code)
        current_nav = detail.nav
    except Exception:
        current_nav = None

    shares = float(row["shares"])
    buy_amount = float(row["buy_amount"])
    cost = buy_amount + float(row.get("fee", 0))

    current_value = round(shares * current_nav, 2) if current_nav else None
    profit = round(current_value - cost, 2) if current_value is not None else None
    profit_pct = round(profit / cost * 100, 2) if profit is not None and cost > 0 else None

    return HoldingItem(
        id=row["id"],
        fund_code=code,
        fund_name=row["fund_name"],
        fund_type=row.get("fund_type", ""),
        buy_date=row["buy_date"],
        buy_amount=buy_amount,
        buy_nav=float(row["buy_nav"]),
        shares=shares,
        fee=float(row.get("fee", 0)),
        notes=row.get("notes", ""),
        is_sold=bool(row.get("is_sold", 0)),
        sell_date=row.get("sell_date"),
        sell_amount=float(row["sell_amount"]) if row.get("sell_amount") else None,
        sell_nav=float(row["sell_nav"]) if row.get("sell_nav") else None,
        current_nav=current_nav,
        current_value=current_value,
        cost=cost,
        profit=profit,
        profit_pct=profit_pct,
    )


# ── CRUD ────────────────────────────────────────────────────────────────────


def add_holding(data: HoldingCreate) -> HoldingItem:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO holdings (fund_code, fund_name, fund_type, buy_date, buy_amount, buy_nav, shares, fee, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [data.fund_code, data.fund_name, data.fund_type, data.buy_date,
         data.buy_amount, data.buy_nav, data.shares, data.fee, data.notes],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [cur.lastrowid]).fetchone()
    conn.close()
    return _enrich_holding(_row_to_dict(row))


def mark_sold(holding_id: int, data: SellRequest) -> HoldingItem | None:
    conn = get_connection()
    conn.execute(
        """UPDATE holdings SET is_sold = 1, sell_date = ?, sell_amount = ?, sell_nav = ?
           WHERE id = ?""",
        [data.sell_date, data.sell_amount, data.sell_nav, holding_id],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_holding(_row_to_dict(row))


def delete_holding(holding_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM holdings WHERE id = ?", [holding_id])
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_holding(holding_id: int, data: HoldingCreate) -> HoldingItem | None:
    conn = get_connection()
    conn.execute(
        """UPDATE holdings SET fund_code=?, fund_name=?, fund_type=?, buy_date=?,
           buy_amount=?, buy_nav=?, shares=?, fee=?, notes=?
           WHERE id=?""",
        [data.fund_code, data.fund_name, data.fund_type, data.buy_date,
         data.buy_amount, data.buy_nav, data.shares, data.fee, data.notes, holding_id],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_holding(_row_to_dict(row))


# ── 查询 ────────────────────────────────────────────────────────────────────


def get_holding(holding_id: int) -> HoldingItem | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_holding(_row_to_dict(row))


def list_holdings(include_sold: bool = False) -> list[HoldingItem]:
    """列出持仓记录，使用批量 NAV 查询避免 N+1。

    数据来源：
    - 持仓记录：SQLite
    - 当前净值：fund_service._load_fund_list() 缓存（TTL 1 小时，启动预热）
    """
    conn = get_connection()
    if include_sold:
        rows = conn.execute("SELECT * FROM holdings ORDER BY buy_date DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM holdings WHERE is_sold = 0 ORDER BY buy_date DESC").fetchall()
    conn.close()

    # 批量获取 NAV：一次构建映射表，所有持仓共享（O(1) 查找，无 akshare 调用）
    nav_map = _build_nav_map()
    dict_rows = [_row_to_dict(r) for r in rows]
    return [_enrich_holding_from_map(r, nav_map) for r in dict_rows]


def portfolio_summary() -> PortfolioSummary:
    """组合总览：当前持仓汇总。

    使用缓存基金列表 NAV（TTL 1 小时）进行快速计算，
    不触发 akshare 远程调用。
    """
    holdings = list_holdings(include_sold=False)
    total_cost = 0.0
    total_value = 0.0
    for h in holdings:
        total_cost += h.cost or 0
        total_value += h.current_value or 0
    total_profit = round(total_value - total_cost, 2) if total_cost > 0 else 0.0
    total_profit_pct = round(total_profit / total_cost * 100, 2) if total_cost > 0 else 0.0
    return PortfolioSummary(
        total_cost=round(total_cost, 2),
        total_value=round(total_value, 2),
        total_profit=total_profit,
        total_profit_pct=total_profit_pct,
        holding_count=len(holdings),
        holdings=holdings,
    )
