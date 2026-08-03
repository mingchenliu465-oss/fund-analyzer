from fastapi import APIRouter, HTTPException, Query

from models.fund import FundDetail, FundSummary
from models.market import NavPeriod, NavPoint
from services import fund_service

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
