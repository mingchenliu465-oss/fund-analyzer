"""持仓管理服务：CRUD + 实时净值计算。

净值获取策略：
- 批量查询（list_holdings / portfolio_summary）：优先从已缓存的基金列表
  （_load_fund_list, TTL 1 小时, 启动预热）获取 NAV，避免 N+1 次 akshare 调用。
- 单条查询（add_holding / get_holding / mark_sold / update_holding）：调用
  fund_service.get_by_code() 获取实时净值（含 akshare 调用，3-8 秒）。
"""

from __future__ import annotations

import logging
import math
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any

from database import get_connection
from models.portfolio import DripCreate, HoldingCreate, HoldingItem, PortfolioSummary, SellRequest
from services import fund_service

logger = logging.getLogger(__name__)


def _row_to_dict(row: Any) -> dict:
    return dict(row) if row else {}


def _looks_mojibake(s: str) -> bool:
    """粗略判断字符串是否编码损坏（含多处问号或替换符）。"""
    if not s:
        return True
    if "\ufffd" in s:
        return True
    if s.count("?") >= 3:
        return True
    return False


def _resolve_fund_name(code: str, fallback: str) -> str:
    """解析基金权威名称，优先后端缓存列表，缺失/乱码时回退前端值。

    根治前端中文名编码损坏（?????）导致的脏数据：后端以 fund_code 为准，
    从已缓存基金列表取正确名称，即使前端传了乱码也会被覆盖。
    """
    code = str(code or "").strip()
    try:
        funds = fund_service._load_fund_list()
        for f in funds:
            if f.code == code and f.name and not _looks_mojibake(f.name):
                return f.name
    except Exception as exc:
        logger.warning("resolve fund name from list failed for %s: %s", code, exc)

    # 列表拿不到权威名且 fallback 是乱码/空时，尝试单只接口
    if not fallback or _looks_mojibake(fallback):
        try:
            detail = fund_service.get_by_code(code)
            if detail.name and not _looks_mojibake(detail.name):
                return detail.name
        except Exception:
            pass

    return fallback or code


# ---------------------------------------------------------------------------
# NAV 批量查询（基于缓存基金列表，无 akshare 调用）
# ---------------------------------------------------------------------------

def _build_nav_map() -> dict[str, float]:
    """从已缓存的基金列表构建 code → 当前净值 映射。

    数据来源：fund_service._load_fund_list()，TTL 1 小时，启动时后台预热。
    该列表的 nav 字段来自 akshare 公募基金排行榜（fund_open_fund_rank_em），
    包含热门基金的实时单位净值和日涨跌幅。

    注意：排行榜只覆盖热门基金，非热门持仓基金的净值需单独用 get_by_code
    补齐（见 _get_holding_nav）。此映射仅用于组合总览的快速展示。
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


# 持仓基金单独净值缓存（TTL 30 分钟），避免对非热门持仓重复调用 akshare
_HOLDING_NAV_TTL = 1800


def _set_holding_nav_cache(code: str, nav: float) -> None:
    """写入持仓基金净值缓存（含净值日期与更新时间，供未来 AI 复用）。"""
    from datetime import datetime

    fund_service._set_cache(
        f"holding_nav:{code}",
        {
            "fund_code": code,
            "nav": float(nav),
            "nav_date": date.today().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        ttl=_HOLDING_NAV_TTL,
    )


def _get_holding_nav(code: str) -> float | None:
    """获取单只持仓基金当前净值，优先缓存。

    查找顺序：
    1. 持仓净值缓存（_holding_nav_cache，TTL 30 分钟，含 nav/nav_date/updated_at）
    2. 基金列表缓存 nav_map（排行榜，热门基金）
    3. 用 fund_service.get_by_code() 单只接口补齐（非热门基金），并写缓存

    返回 None 表示该基金当前拿不到净值（调用方需妥善处理，不得导致归零）。
    """
    cached = fund_service._get_cache(f"holding_nav:{code}")
    if cached is not None and cached.get("nav", 0) > 0:
        return cached["nav"]

    # 从列表缓存取（可能仍是 0 或缺省）
    try:
        funds = fund_service._load_fund_list()
        summary = next((f for f in funds if f.code == code), None)
        if summary is not None and summary.nav > 0:
            _set_holding_nav_cache(code, summary.nav)
            return summary.nav
    except Exception as exc:
        logger.warning("nav lookup from list failed for %s: %s", code, exc)

    # 非热门基金：用单只接口补齐
    try:
        detail = fund_service.get_by_code(code)
        nav = detail.nav
        if nav > 0:
            _set_holding_nav_cache(code, nav)
            return nav
    except Exception as exc:
        logger.warning("get_by_code nav failed for %s: %s", code, exc)

    return None


# 兜底：持仓基金最近一次有效净值的内存记录（遇到 akshare 失败时使用，避免归零）
_LAST_GOOD_NAV: dict[str, float] = {}
_LAST_GOOD_NAV_FETCHED: dict[str, bool] = {}


def _getportfolio_nav_fallback(code: str, buy_nav: float) -> tuple[float | None, bool]:
    """获取持仓净值（带异常保护）。

    Returns: (nav, stale) —— nav 为 None 表示完全拿不到；stale=True 表示为
    最近一次有效净值（可能是买入净值兜底），当前净值处于"待更新"状态。
    """
    nav = _get_holding_nav(code)
    # 0 或负数不是可用于估值的净值，必须继续走已知有效值/买入净值兜底。
    if nav is not None and nav > 0:
        _LAST_GOOD_NAV[code] = nav
        return nav, False

    # 拿不到实时净值：优先最近一次有效净值，其次买入净值
    if code in _LAST_GOOD_NAV:
        return _LAST_GOOD_NAV[code], True
    if buy_nav > 0:
        return buy_nav, True
    return None, True


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


def _holding_no_nav(row: dict) -> HoldingItem:
    """为一条持仓记录构造 HoldingItem，但不做任何远程净值查询。

    用于 add_holding / update_holding / mark_sold 等写路径：写库后立即返回，
    净值与盈亏字段置空（由后续 list_holdings / portfolio_summary 走缓存 NAV
    映射表补齐展示），避免 akshare 慢查询阻塞写入或拖慢接口响应。
    """
    shares = float(row["shares"])
    buy_amount = float(row["buy_amount"])
    cost = buy_amount + float(row.get("fee", 0))

    return HoldingItem(
        id=row["id"],
        fund_code=row["fund_code"],
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
        current_nav=None,
        current_value=None,
        cost=cost,
        profit=None,
        profit_pct=None,
    )


# ---------------------------------------------------------------------------
# 单条实时查询（保留原有逻辑，用于 get_holding 等需要精确净值的场景）
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
    fund_name = _resolve_fund_name(data.fund_code, data.fund_name)
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO holdings (fund_code, fund_name, fund_type, buy_date, buy_amount, buy_nav, shares, fee, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [data.fund_code, fund_name, data.fund_type, data.buy_date,
         data.buy_amount, data.buy_nav, data.shares, data.fee, data.notes],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [cur.lastrowid]).fetchone()
    conn.close()
    return _holding_no_nav(_row_to_dict(row))


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
    return _holding_no_nav(_row_to_dict(row))


def delete_holding(holding_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM holdings WHERE id = ?", [holding_id])
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def update_holding(holding_id: int, data: HoldingCreate) -> HoldingItem | None:
    fund_name = _resolve_fund_name(data.fund_code, data.fund_name)
    conn = get_connection()
    conn.execute(
        """UPDATE holdings SET fund_code=?, fund_name=?, fund_type=?, buy_date=?,
           buy_amount=?, buy_nav=?, shares=?, fee=?, notes=?
           WHERE id=?""",
        [data.fund_code, fund_name, data.fund_type, data.buy_date,
         data.buy_amount, data.buy_nav, data.shares, data.fee, data.notes, holding_id],
    )
    conn.commit()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    conn.close()
    if not row:
        return None
    return _holding_no_nav(_row_to_dict(row))


# ── 查询 ────────────────────────────────────────────────────────────────────


def get_holding(holding_id: int) -> HoldingItem | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM holdings WHERE id = ?", [holding_id]).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_holding(_row_to_dict(row))


def list_holdings(include_sold: bool = False) -> list[HoldingItem]:
    """列出持仓记录，支持非热门基金的净值补齐。

    数据来源：
    - 持仓记录：SQLite
    - 当前净值：优先基金列表缓存（热门），非热门持仓用 get_by_code 补齐并缓存，
      确保任何用户持仓基金都能正确计算市值与盈亏，不因榜单缺失而变为 0。
    """
    conn = get_connection()
    if include_sold:
        rows = conn.execute("SELECT * FROM holdings ORDER BY buy_date DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM holdings WHERE is_sold = 0 ORDER BY buy_date DESC").fetchall()
    conn.close()

    dict_rows = [_row_to_dict(r) for r in rows]
    if not dict_rows:
        return []
    nav_map = _build_nav_map()
    result: list[HoldingItem] = []
    for r in dict_rows:
        code = r["fund_code"]
        nav = nav_map.get(code)
        stale = False
        if nav is None or nav <= 0:
            # 榜单缺失：单只补齐（带缓存 + 异常保护）
            nav, stale = _getportfolio_nav_fallback(code, float(r.get("buy_nav", 0)))
        result.append(_enrich_holding_from_map_r(r, code, nav, stale))

    return result


def _enrich_holding_from_map_r(row: dict, code: str, current_nav: float | None, stale: bool = False) -> HoldingItem:
    """基于单个持仓代码与净值构造 HoldingItem（供 list_holdings 使用）。"""
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
        nav_stale=stale,
    )


def portfolio_summary() -> PortfolioSummary:
    """组合总览：当前持仓汇总。

    使用缓存基金列表 NAV + 单只补齐（非热门），确保总资产不回零。
    """
    holdings = list_holdings(include_sold=False)
    total_cost = 0.0
    total_value = 0.0
    has_stale = False
    for h in holdings:
        total_cost += h.cost or 0
        total_value += h.current_value or 0
        if h.nav_stale:
            has_stale = True
    total_profit = round(total_value - total_cost, 2) if total_cost > 0 else 0.0
    total_profit_pct = round(total_profit / total_cost * 100, 2) if total_cost > 0 else 0.0

    # 记录当日快照（幂等 upsert），为资产历史曲线积累数据。
    _upsert_snapshot(
        total_value=total_value,
        total_cost=total_cost,
        profit=total_profit,
        profit_rate=total_profit_pct,
    )

    return PortfolioSummary(
        total_cost=round(total_cost, 2),
        total_value=round(total_value, 2),
        total_profit=total_profit,
        total_profit_pct=total_profit_pct,
        holding_count=len(holdings),
        holdings=holdings,
        has_stale_nav=has_stale,
    )


# ---------------------------------------------------------------------------
# 资产历史快照
# ---------------------------------------------------------------------------

def _upsert_snapshot(
    total_value: float,
    total_cost: float,
    profit: float,
    profit_rate: float,
) -> None:
    """把当日组合快照写入 portfolio_snapshots（幂等 upsert）。

    独立成函数，未来可被定时任务复用（保留扩展点）。
    """
    today = date.today().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT INTO portfolio_snapshots
               (date, total_value, total_cost, profit, profit_rate)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               total_value = excluded.total_value,
               total_cost  = excluded.total_cost,
               profit      = excluded.profit,
               profit_rate = excluded.profit_rate""",
        [
            today,
            round(float(total_value), 2),
            round(float(total_cost), 2),
            round(float(profit), 2),
            round(float(profit_rate), 2),
        ],
    )
    conn.commit()
    conn.close()


def portfolio_history(period: str = "1M") -> list[dict]:
    """读取资产历史快照，按 period 过滤日期范围。

    period: 1W / 1M / 3M / 1Y / ALL
    返回日粒度数据（未聚合），供前端画资产/收益率曲线。
    """
    days_map = {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    days = days_map.get(period)
    cutoff = None
    if days is not None:
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

    conn = get_connection()
    if cutoff:
        rows = conn.execute(
            "SELECT date, total_value, total_cost, profit, profit_rate "
            "FROM portfolio_snapshots WHERE date >= ? ORDER BY date ASC",
            [cutoff],
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT date, total_value, total_cost, profit, profit_rate "
            "FROM portfolio_snapshots ORDER BY date ASC"
        ).fetchall()
    conn.close()

    return [
        {
            "date": row["date"],
            "total_value": row["total_value"],
            "total_cost": row["total_cost"],
            "profit": row["profit"],
            "profit_rate": row["profit_rate"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 收益归因（今日收益来自哪里）
# ---------------------------------------------------------------------------

def _etf_nav_change(code: str) -> tuple[float, float, float]:
    """获取场内 ETF 的最近两条净值，返回 (今日净值, 昨日净值, 涨跌幅%)。

    场内 ETF 不在开放式基金排行榜里，故单独从行情序列取最近两条 close。
    """
    try:
        df = fund_service._fetch_etf_history(code)
        if df.empty or len(df) < 2:
            return 0.0, 0.0, 0.0
        latest = float(df["单位净值"].iloc[-1])
        prev = float(df["单位净值"].iloc[-2])
        change_pct = (latest - prev) / prev * 100 if prev else 0.0
        return latest, prev, change_pct
    except Exception:
        return 0.0, 0.0, 0.0


def _open_fund_nav_change(code: str) -> tuple[float, float, float]:
    """获取场外基金的最近两条净值，返回 (今日净值, 昨日净值, 涨跌幅%)。

    用于收益归因的兜底：当某只持仓场外基金不在缓存基金列表里（或其榜单
    涨跌幅缺失/为 0）时，直接从该基金的历史净值序列取最近两条计算真实
    涨跌幅，避免"今日收益"被错误地显示为 +¥0 / 0%。
    """
    try:
        df = fund_service._fetch_nav_history(code)
        if df.empty or len(df) < 2:
            return 0.0, 0.0, 0.0
        latest = float(df["单位净值"].iloc[-1])
        prev = float(df["单位净值"].iloc[-2])
        change_pct = (latest - prev) / prev * 100 if prev else 0.0
        return latest, prev, change_pct
    except Exception:
        return 0.0, 0.0, 0.0


def attribution() -> dict:
    """收益归因：回答"今天我的组合为什么涨跌"。

    计算口径（严格）：
        单只贡献 = shares × (今日净值 − 昨日净值)
        组合今日收益 = Σ 贡献
        组合收益率   = 组合今日收益 / 组合昨日市值 × 100%

    场外基金：优先用缓存基金列表的 change_pct（昨日净值 = 今日净值 /
              (1 + change_pct/100) 反推）；当某只持仓场外基金不在缓存列表或
              榜单涨跌幅缺失/为 0 时，回退 _open_fund_nav_change 取最近两条
              真实净值计算，避免今日收益被硬编码为 0。
    场内 ETF：回退 _fetch_etf_history 取最近两条 close。

    返回包含 summary（供未来 AI 每日复盘）与每只基金 contribution_rate。
    """
    holdings = list_holdings(include_sold=False)

    empty_summary = {
        "total_assets": 0.0,
        "today_return": 0.0,
        "today_return_pct": 0.0,
        "holding_count": 0,
        "has_stale_nav": False,
        "gainers_count": 0,
        "losers_count": 0,
        "top_gainer_name": None,
        "top_loser_name": None,
        "note": "场外基金为 T-1 净值，ETF 为实时/收盘价",
    }
    if not holdings:
        return {
            "today_return": 0.0,
            "today_return_pct": 0.0,
            "yesterday_value": 0.0,
            "summary": empty_summary,
            "contributions": [],
            "top_gainer": None,
            "top_loser": None,
        }

    # 构建 code → (nav, change_pct) 映射（来自缓存基金列表，零额外 akshare 调用）
    nav_change: dict[str, dict[str, float]] = {}
    try:
        for f in fund_service._load_fund_list():
            nav_change[f.code] = {"nav": f.nav, "change_pct": f.change_pct}
    except Exception:
        pass

    contributions: list[dict] = []
    total_prev_value = 0.0
    total_today_value = 0.0

    for h in holdings:
        code = h.fund_code
        shares = float(h.shares)

        if fund_service._is_etf_code(code):
            nav, prev_nav, change_pct = _etf_nav_change(code)
        else:
            info = nav_change.get(code)
            if info and info.get("nav", 0) > 0 and info.get("change_pct", 0.0) != 0:
                nav = float(info["nav"])
                change_pct = float(info.get("change_pct", 0.0) or 0.0)
                denom = 100 + change_pct
                prev_nav = nav / (denom / 100) if denom > 0 else 0.0
            else:
                # 缓存基金列表缺失/榜单无涨跌幅：回退到该基金历史净值序列，
                # 取最近两条真实净值计算涨跌幅，避免"今日收益"被硬编码为 0。
                nav, prev_nav, change_pct = _open_fund_nav_change(code)

        nav_stale = not all(math.isfinite(v) and v > 0 for v in (nav, prev_nav))
        if nav_stale:
            nav = float(h.current_nav or h.buy_nav)
            prev_nav = nav
            change_pct = 0.0
        contribution = shares * (nav - prev_nav)
        contributions.append(
            {
                "fund_code": code,
                "fund_name": h.fund_name,
                "fund_type": h.fund_type,
                "current_value": shares * nav,
                "nav_stale": nav_stale,
                "shares": round(shares, 2),
                "nav": round(nav, 4),
                "prev_nav": round(prev_nav, 4),
                "change_pct": round(change_pct, 2),
                "contribution": contribution,
            }
        )
        total_prev_value += shares * prev_nav
        total_today_value += shares * nav

    grouped: dict[str, dict] = {}
    for c in contributions:
        code = c["fund_code"]
        if code not in grouped:
            grouped[code] = c.copy()
        else:
            for key in ("shares", "contribution", "current_value"):
                grouped[code][key] += c[key]
            grouped[code]["nav_stale"] |= c["nav_stale"]
    contributions = list(grouped.values())
    for c in contributions:
        c["contribution"] = round(c["contribution"], 2)
        c["current_value"] = round(c["current_value"], 2)
    today_return = round(sum(c["contribution"] for c in contributions), 2)
    total_abs = sum(abs(c["contribution"]) for c in contributions)

    # contribution_rate = 该基金贡献 / Σ|贡献|（保留正负号，正值=贡献、负值=拖累）
    for c in contributions:
        c["contribution_rate"] = (
            round(c["contribution"] / total_abs, 4) if total_abs > 0 else 0.0
        )

    contributions.sort(key=lambda c: c["contribution"], reverse=True)

    today_return_pct = (
        round(today_return / total_prev_value * 100, 2) if total_prev_value > 0 else 0.0
    )

    gainers = [c for c in contributions if c["contribution"] > 0]
    losers = [c for c in contributions if c["contribution"] < 0]
    top_gainer = gainers[0] if gainers else None
    top_loser = losers[-1] if losers else None

    summary = {
        "total_assets": round(total_today_value, 2),
        "today_return": today_return,
        "today_return_pct": today_return_pct,
        "holding_count": len(contributions),
        "gainers_count": len(gainers),
        "losers_count": len(losers),
        "top_gainer_name": gainers[0]["fund_name"] if gainers else None,
        "top_loser_name": top_loser["fund_name"] if top_loser else None,
        "has_stale_nav": any(c["nav_stale"] for c in contributions),
        "note": "场外基金为 T-1 净值，ETF 为实时/收盘价",
    }

    return {
        "today_return": today_return,
        "today_return_pct": today_return_pct,
        "yesterday_value": round(total_prev_value, 2),
        "summary": summary,
        "contributions": contributions,
        "top_gainer": top_gainer,
        "top_loser": top_loser,
    }


# ---------------------------------------------------------------------------
# 自动定投（定投计划 → 自动生成日期/取净值/算份额 → 批量入库）
# ---------------------------------------------------------------------------

def _generate_drip_dates(start_date: str, end_date: str, frequency: str, schedule_day: int) -> list[str]:
    """生成定投日期序列（yyyy-mm-dd 升序）。

    frequency: daily → 每个自然日；monthly → 每月的 day_of_month 号；
               weekly → 每周 schedule_day（1=周一、7=周日）。
    end_date 按自然日边界：生成的日期 <= end_date 才纳入。
    """
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    dates: list[str] = []
    cursor = start

    while cursor <= end:
        if frequency == "daily":
            target = cursor
        elif frequency == "weekly":
            # Python weekday(): 周一=0；接口语义：周一=1。取 cursor 当日或之后
            # 最近的目标星期，避免起始日在目标星期之后时漏掉下一周。
            offset = ((schedule_day - 1) - cursor.weekday()) % 7
            target = cursor + timedelta(days=offset)
        else:  # monthly
            last_day = 28
            try:
                # 找本月最后一天
                if cursor.month == 12:
                    next_month_first = cursor.replace(year=cursor.year + 1, month=1, day=1)
                else:
                    next_month_first = cursor.replace(month=cursor.month + 1, day=1)
                last_day = (next_month_first - timedelta(days=1)).day
            except ValueError:
                last_day = 28
            day = min(schedule_day, last_day)
            target = cursor.replace(day=day)

        if start <= target <= end:
            dates.append(target.isoformat())

        # 前进
        if frequency == "weekly":
            cursor += timedelta(days=7)
        elif frequency == "daily":
            cursor += timedelta(days=1)
        else:
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1, day=1)

    return dates


def _lookup_nav_on(df, target_iso: str) -> float | None:
    """在净值历史 DataFrame 中，找 定投日或之前最近一个交易日的单位净值。

    df 需含"净值日期"(datetime) 与"单位净值"列，且已按日期升序。
    """
    import pandas as pd

    if df is None or df.empty:
        return None
    target = pd.Timestamp(target_iso)
    mask = df["净值日期"] <= target
    if not mask.any():
        return None
    return float(df.loc[mask, "单位净值"].iloc[-1])


def auto_drip(data: DripCreate) -> dict:
    """自动定投：生成日期序列 → 取历史净值 → 计算份额 → 批量创建持仓。

    返回：{"created": count, "items": [HoldingItem...], "skipped": [{date, reason}]}
    """
    from services import fund_service

    upper = data.fund_code.strip().upper()
    dt = datetime.strptime(data.start_date, "%Y-%m-%d").date()

    # 1) 生成定投日期
    day = data.day_of_week if data.day_of_week else 1
    dates = _generate_drip_dates(data.start_date, data.end_date, data.frequency, day)
    if not dates:
        return {"created": 0, "items": [], "skipped": [{"date": data.start_date, "reason": "定投日期为空，请检查开始/结束日期"}]}

    # 1.5) 权威基金名（避免前端编码损坏写入乱码）
    fund_name = _resolve_fund_name(data.fund_code, data.fund_name)

    # 2) 取历史净值（一次性，ETF 用行情、场外用净值）
    nav_df = None
    try:
        if fund_service._is_etf_code(upper):
            nav_df = fund_service._fetch_etf_history(upper)
        else:
            nav_df = fund_service._fetch_nav_history(upper)
    except Exception as exc:
        logger.warning("auto_drip nav fetch failed for %s: %s", upper, exc)
        nav_df = None

    # 3) 批量入库
    conn = get_connection()
    created: list[HoldingItem] = []
    skipped: list[dict] = []
    try:
        for d in dates:
            nav = _lookup_nav_on(nav_df, d) if nav_df is not None else None
            if nav is None or nav <= 0:
                skipped.append({"date": d, "reason": f"定投日 {d} 无可用净值（可能是非交易日或数据缺失）"})
                continue
            shares = round(data.amount / nav, 2)
            notes = data.notes or f"自动定投 {d}"
            cur = conn.execute(
                """INSERT INTO holdings (fund_code, fund_name, fund_type, buy_date, buy_amount, buy_nav, shares, fee, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [data.fund_code, fund_name, data.fund_type, d,
                 data.amount, nav, shares, data.fee, notes],
            )
            row = conn.execute("SELECT * FROM holdings WHERE id = ?", [cur.lastrowid]).fetchone()
            created.append(_holding_no_nav(_row_to_dict(row)))
        conn.commit()
    except Exception as exc:
        logger.exception("auto_drip batch insert failed")
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"created": len(created), "items": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Portfolio Insights（组合洞察）
# ---------------------------------------------------------------------------

_INSIGHT_INDEXES = (
    ("sh000300", "沪深300"),
    ("sh000905", "中证500"),
    ("sz399006", "创业板指"),
    ("H11001", "中证全债"),
)


def _insight_period_days(period: str) -> int | None:
    return {"1W": 7, "1M": 30, "3M": 90, "1Y": 365}.get(period.upper())


def _build_history_insight(points: list[dict]) -> dict:
    """将现有日快照转换成趋势和异常波动提示。

    快照无法识别期间申购/赎回，因此字段名称明确使用 day_change，避免把
    资产变化误称为精确的账户收益。
    """
    rows: list[dict] = []
    changes: list[float] = []
    for index, point in enumerate(points):
        value = float(point.get("total_value", 0) or 0)
        change = None
        change_pct = None
        if index > 0:
            previous = float(points[index - 1].get("total_value", 0) or 0)
            change = round(value - previous, 2)
            if previous > 0:
                change_pct = round(change / previous * 100, 2)
                changes.append(change_pct)
        rows.append({
            "date": str(point.get("date", "")),
            "total_value": round(value, 2),
            "profit": round(float(point.get("profit", 0) or 0), 2),
            "day_change": change,
            "day_change_pct": change_pct,
            "is_anomaly": False,
        })

    anomaly_date = None
    anomaly_reason = None
    # 用当前点之前的变化估计范围，避免异常值把自己的阈值抬高。
    if len(changes) >= 5:
        for row_index, row in enumerate(rows[1:], start=0):
            value = row.get("day_change_pct")
            prior = changes[:row_index]
            if value is None or len(prior) < 4:
                continue
            mean = statistics.mean(prior)
            stdev = statistics.pstdev(prior)
            threshold = max(2.0, abs(mean) + 2 * stdev)
            if abs(value) >= threshold:
                row["is_anomaly"] = True
                anomaly_date = row["date"]
                anomaly_reason = f"该日资产快照变化 {value:+.2f}%，明显偏离近期波动范围。"
                break

    if len(rows) < 2:
        trend = "暂无"
    elif rows[-1]["total_value"] > rows[0]["total_value"]:
        trend = "上升"
    elif rows[-1]["total_value"] < rows[0]["total_value"]:
        trend = "下降"
    else:
        trend = "基本持平"

    return {
        "points": rows,
        "trend": trend,
        "anomaly_detected": anomaly_date is not None,
        "anomaly_date": anomaly_date,
        "anomaly_reason": anomaly_reason,
        "data_sufficiency": "ready" if len(rows) >= 2 else "insufficient",
        "note": "历史数据基于组合资产快照，未扣除期间现金流。",
    }


def _fetch_index_return(code: str, cutoff: str | None) -> float | None:
    """读取指数日线并计算区间涨跌幅；失败时返回 None。"""
    try:
        from models.market import NavPeriod
        from services import market_service

        points = market_service.index_kline(code, NavPeriod.DAILY)
        if not points:
            return None
        visible = [p for p in points if not cutoff or p.date >= cutoff]
        if len(visible) < 2:
            return None
        first = float(visible[0].close)
        last = float(visible[-1].close)
        return round((last / first - 1) * 100, 2) if first else None
    except Exception as exc:
        logger.warning("portfolio insight index return failed for %s: %s", code, exc)
        return None


def _build_overlap_pairs(value_by_code: dict[str, float]) -> tuple[str, list[dict]]:
    """基于真实季报十大持仓计算基金之间的底层重叠。

    _fetch_real_holdings 返回 None 时表示数据源不可用；绝不调用
    get_by_code() 的默认持仓，避免把示例数据当成真实风险结论。
    """
    if len(value_by_code) < 2:
        return "unavailable", []

    from services import fund_service

    codes = [code for code, _ in sorted(value_by_code.items(), key=lambda item: item[1], reverse=True)[:8]]
    with ThreadPoolExecutor(max_workers=min(4, len(codes))) as executor:
        futures = {code: executor.submit(fund_service._fetch_real_holdings, code) for code in codes}
        holdings_map = {code: future.result() for code, future in futures.items()}

    available_codes = [code for code, rows in holdings_map.items() if rows]
    if len(available_codes) < 2:
        return "unavailable", []

    pairs: list[dict] = []
    for index, code_a in enumerate(available_codes):
        rows_a = {str(row.code): (str(row.name), float(row.weight)) for row in holdings_map[code_a] if row.code}
        for code_b in available_codes[index + 1:]:
            rows_b = {str(row.code): (str(row.name), float(row.weight)) for row in holdings_map[code_b] if row.code}
            shared = sorted(set(rows_a) & set(rows_b))
            if not shared:
                continue
            overlap = sum(min(rows_a[code][1], rows_b[code][1]) for code in shared)
            if overlap >= 10:
                pairs.append({
                    "fund_a": code_a,
                    "fund_b": code_b,
                    "shared_holdings": [rows_a[code][0] for code in shared],
                    "overlap_pct": round(overlap, 2),
                    "data_as_of": "2024",
                })
    pairs.sort(key=lambda item: item["overlap_pct"], reverse=True)
    return "available", pairs[:5]


def insights(period: str = "1M") -> dict:
    """生成组合洞察：收益解释、集中度、市场对比与历史变化。"""
    period = period.upper()
    if period not in {"1W", "1M", "3M", "1Y", "ALL"}:
        period = "1M"

    summary = portfolio_summary()
    attribution_result = attribution()
    contributions = attribution_result.get("contributions", [])
    active_values = {c["fund_code"]: float(c.get("current_value", 0) or 0) for c in contributions}
    total_value = sum(active_values.values())

    top_gainers = [c for c in contributions if c.get("contribution", 0) > 0][:3]
    top_draggers = [c for c in reversed(contributions) if c.get("contribution", 0) < 0][:3]
    stale_count = sum(1 for c in contributions if c.get("nav_stale"))
    today_return = float(attribution_result.get("today_return", 0) or 0)
    today_return_pct = float(attribution_result.get("today_return_pct", 0) or 0)
    if not contributions:
        sentence = "暂无持仓，录入真实交易后即可生成组合洞察。"
        data_status = "empty"
    elif today_return > 0:
        sentence = f"今天组合上涨 ¥{today_return:,.2f}，主要由 {top_gainers[0]['fund_name']} 贡献。" if top_gainers else "今天组合小幅上涨。"
        data_status = "partial" if stale_count else "ready"
    elif today_return < 0:
        sentence = f"今天组合下跌 ¥{abs(today_return):,.2f}，主要拖累来自 {top_draggers[0]['fund_name']}。" if top_draggers else "今天组合小幅下跌。"
        data_status = "partial" if stale_count else "ready"
    else:
        sentence = "今天组合基本持平，暂无明显的收益来源。"
        data_status = "partial" if stale_count else "ready"

    allocation_map: dict[str, dict[str, float]] = {}
    for c in contributions:
        category = c.get("fund_type") or "其他"
        bucket = allocation_map.setdefault(category, {"value": 0.0, "holding_count": 0})
        bucket["value"] += float(c.get("current_value", 0) or 0)
        bucket["holding_count"] += 1
    allocation = [
        {
            "category": category,
            "value": round(bucket["value"], 2),
            "weight_pct": round(bucket["value"] / total_value * 100, 2) if total_value else 0.0,
            "holding_count": int(bucket["holding_count"]),
        }
        for category, bucket in allocation_map.items()
    ]
    allocation.sort(key=lambda item: item["weight_pct"], reverse=True)

    sorted_values = sorted(active_values.items(), key=lambda item: item[1], reverse=True)
    max_code, max_value = sorted_values[0] if sorted_values else (None, 0.0)
    max_name = next((c.get("fund_name") for c in contributions if c.get("fund_code") == max_code), None)
    weights = [value / total_value for value in active_values.values()] if total_value else []
    hhi = round(sum(weight * weight for weight in weights) * 10000, 2) if weights else 0.0
    max_weight = max_value / total_value * 100 if total_value else 0.0
    if not weights:
        concentration_level = "暂无"
    elif hhi >= 2500 or max_weight >= 50:
        concentration_level = "高"
    elif hhi >= 1500 or max_weight >= 30:
        concentration_level = "中"
    else:
        concentration_level = "低"
    overlap_status, overlap_pairs = _build_overlap_pairs(active_values)
    risk_notes = []
    if max_weight >= 40:
        risk_notes.append(f"最大持仓占比 {max_weight:.1f}%，组合对单只基金依赖较高。")
    if overlap_status != "available":
        risk_notes.append("暂未取得至少两只基金的真实季报十大持仓，无法可靠判断底层重叠。")
    if stale_count:
        risk_notes.append("部分基金净值待更新，收益归因可能不完整。")

    history_points = portfolio_history(period)
    history = _build_history_insight(history_points)
    cutoff = None
    days = _insight_period_days(period)
    if days is not None:
        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    first_snapshot = next((p for p in history_points if not cutoff or p["date"] >= cutoff), None)
    last_snapshot = history_points[-1] if history_points else None
    portfolio_period_return = None
    if first_snapshot and last_snapshot and float(first_snapshot.get("total_value", 0) or 0) > 0 and first_snapshot is not last_snapshot:
        portfolio_period_return = round((float(last_snapshot["total_value"]) / float(first_snapshot["total_value"]) - 1) * 100, 2)

    market_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(_INSIGHT_INDEXES)) as executor:
        futures = {code: executor.submit(_fetch_index_return, code, cutoff) for code, _ in _INSIGHT_INDEXES}
        for code, name in _INSIGHT_INDEXES:
            index_return = futures[code].result()
            available = portfolio_period_return is not None and index_return is not None
            market_results.append({
                "code": code,
                "name": name,
                "portfolio_return_pct": portfolio_period_return,
                "index_return_pct": index_return,
                "relative_return_pct": round(portfolio_period_return - index_return, 2) if available else None,
                "available": available,
                "reason": None if available else "组合或指数在所选区间缺少足够历史数据。",
            })

    review_context = [
        {"key": "today_return", "label": "今日组合收益", "value": f"{today_return:+.2f}", "source": "portfolio.attribution"},
        {"key": "today_return_pct", "label": "今日组合收益率", "value": f"{today_return_pct:+.2f}%", "source": "portfolio.attribution"},
        {"key": "concentration_level", "label": "集中度等级", "value": concentration_level, "source": "portfolio.holdings"},
        {"key": "history_trend", "label": "快照趋势", "value": history["trend"], "source": "portfolio.snapshots"},
    ]

    if data_status != "empty" and (
        stale_count
        or history["data_sufficiency"] != "ready"
        or not any(item["available"] for item in market_results)
    ):
        data_status = "partial"

    return {
        "period": period,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_status": data_status,
        "headline": {
            "today_return": round(today_return, 2),
            "today_return_pct": round(today_return_pct, 2),
            "sentence": sentence,
            "data_status": data_status,
        },
        "return_explanation": {
            "contributions": contributions,
            "top_gainers": top_gainers,
            "top_draggers": top_draggers,
            "positive_total": round(sum(c.get("contribution", 0) for c in contributions if c.get("contribution", 0) > 0), 2),
            "negative_total": round(sum(c.get("contribution", 0) for c in contributions if c.get("contribution", 0) < 0), 2),
            "stale_count": stale_count,
        },
        "risk": {
            "allocation": allocation,
            "max_holding": {"fund_code": max_code, "fund_name": max_name, "value": round(max_value, 2), "weight_pct": round(max_weight, 2)},
            "concentration_ratio": round(max_weight, 2),
            "hhi": hhi,
            "concentration_level": concentration_level,
            "overlap_status": overlap_status,
            "overlap_pairs": overlap_pairs,
            "notes": risk_notes,
        },
        "market_comparison": market_results,
        "history": history,
        "review_context": review_context,
        "notes": ["收益归因使用最近两次可用净值；场外基金通常为 T-1 净值。", "历史趋势基于资产快照，未扣除期间现金流。"],
    }
