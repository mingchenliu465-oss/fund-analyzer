"""持仓管理服务：CRUD + 实时净值计算。"""

from __future__ import annotations

import logging
from typing import Any

from database import get_connection
from models.portfolio import HoldingCreate, HoldingItem, PortfolioSummary, SellRequest
from services import fund_service

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> dict:
    return dict(row) if row else {}


def _enrich_holding(row: dict) -> HoldingItem:
    """为一条持仓记录补充当前净值、市值、盈亏。"""
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
    conn = get_connection()
    if include_sold:
        rows = conn.execute("SELECT * FROM holdings ORDER BY buy_date DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM holdings WHERE is_sold = 0 ORDER BY buy_date DESC").fetchall()
    conn.close()
    return [_enrich_holding(_row_to_dict(r)) for r in rows]


def portfolio_summary() -> PortfolioSummary:
    """组合总览：当前持仓汇总。"""
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
