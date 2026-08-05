from fastapi import APIRouter, HTTPException, Query

from models.fund import FundDetail, FundSummary
from models.market import NavPeriod, NavPoint
from services import fund_service, portfolio_service

router = APIRouter(prefix="/funds", tags=["funds"])


@router.get("/search", response_model=list[FundSummary])
def search_funds(q: str = Query(..., min_length=1, description="基金代码或名称")):
    return fund_service.search(q)


@router.get("", response_model=list[FundSummary])
def list_funds(
    q: str | None = Query(default=None, description="可选搜索关键词"),
    limit: int = Query(default=1000, ge=1, le=5000, description="返回数量上限"),
):
    """返回基金列表。提供 q 时按代码/名称搜索，否则返回前 limit 条。"""
    if q:
        return fund_service.search(q)[:limit]
    return fund_service.list_all()[:limit]


@router.get("/rankings", response_model=list[FundSummary])
def fund_rankings(limit: int = Query(default=10, ge=1, le=50)):
    """近一年收益排行榜。"""
    return fund_service.rankings(limit)


@router.get("/popular", response_model=list[FundSummary])
def popular_funds(limit: int = Query(default=6, ge=1, le=20)):
    """热门基金。"""
    return fund_service.popular(limit)


@router.get("/recently-watched", response_model=list[FundSummary])
def recently_watched():
    """从持仓记录提取最近关注的基金（最多 6 只），返回 FundSummary。

    数据流：
    1. 读取 portfolio 活跃持仓 → 提取基金代码（去重，最多 6 个）
    2. 从已缓存的基金列表 (_load_fund_list, TTL 1h) 匹配 FundSummary
    3. 一次性返回，无 akshare 远程调用

    不修改已有的 portfolio API。
    """
    # 从 portfolio 获取活跃持仓的基金代码（去重，最多 6 个）
    try:
        holdings = portfolio_service.list_holdings(include_sold=False)
    except Exception:
        holdings = []

    seen: set[str] = set()
    codes: list[str] = []
    for h in holdings:
        if h.fund_code not in seen:
            seen.add(h.fund_code)
            codes.append(h.fund_code)
            if len(codes) >= 6:
                break

    if not codes:
        return []

    # 从缓存基金列表匹配 FundSummary（已在启动时预热，TTL 1 小时）
    try:
        all_funds = fund_service._load_fund_list()
    except Exception:
        return []

    code_set = set(codes)
    results = [f for f in all_funds if f.code in code_set]

    # 保持与持仓顺序一致
    results.sort(key=lambda f: codes.index(f.code) if f.code in codes else 999)

    return results


@router.get("/{code}", response_model=FundDetail)
def get_fund(code: str):
    try:
        return fund_service.get_by_code(code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{code}/nav-history", response_model=list[NavPoint])
def get_fund_nav_history(
    code: str,
    period: NavPeriod = Query(default=NavPeriod.ONE_YEAR, description="周期"),
):
    """获取基金净值历史（用于折线图）。"""
    df = fund_service.nav_history(code)
    if df.empty:
        return []

    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days={
        NavPeriod.ONE_MONTH: 30,
        NavPeriod.THREE_MONTH: 90,
        NavPeriod.SIX_MONTH: 180,
        NavPeriod.ONE_YEAR: 365,
        NavPeriod.THREE_YEAR: 1095,
    }[period])
    df = df[df["净值日期"] >= cutoff].copy()
    df = df.sort_values("净值日期").reset_index(drop=True)

    if df.empty:
        return []

    nav_values = df["单位净值"].astype(float).values
    base = float(nav_values[0]) if nav_values[0] != 0 else 1.0
    points: list[NavPoint] = []
    for _, row in df.iterrows():
        dt = row["净值日期"]
        nav = float(row["单位净值"])
        label = dt.strftime("%Y-%m" if period in (NavPeriod.ONE_YEAR, NavPeriod.THREE_YEAR) else "%m-%d")
        points.append(
            NavPoint(
                date=label,
                nav=round(nav, 4),
                normalized=round(nav / base, 4),
            )
        )
    return points
