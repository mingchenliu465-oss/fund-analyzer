from fastapi import APIRouter, HTTPException

from models.analysis import (
    AICommentary,
    FundFlow,
    HoldStructure,
    PeerComparison,
    PortfolioOverview,
    ReturnRanking,
)
from models.market import DrawdownPoint, NavPeriod
from services import analysis_service, fund_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/flow/{code}", response_model=FundFlow)
def fund_flow(code: str):
    _ensure_exists(code)
    return analysis_service.flow(code)


@router.get("/ai/{code}", response_model=AICommentary)
def ai_commentary(code: str):
    _ensure_exists(code)
    return analysis_service.commentary(code)


@router.get("/drawdown/{code}", response_model=list[DrawdownPoint])
def fund_drawdown(code: str, period: NavPeriod = NavPeriod.ONE_YEAR):
    _ensure_exists(code)
    return analysis_service.drawdown(code, period)


@router.get("/peers/{code}", response_model=list[PeerComparison])
def fund_peers(code: str):
    _ensure_exists(code)
    return analysis_service.peers(code)


@router.get("/ranking/{code}", response_model=ReturnRanking)
def fund_ranking(code: str):
    _ensure_exists(code)
    return analysis_service.ranking(code)


@router.get("/hold-structure", response_model=HoldStructure)
def get_hold_structure():
    """全市场机构/个人持有比例趋势。"""
    return analysis_service.hold_structure()


@router.get("/portfolio", response_model=PortfolioOverview)
def portfolio_overview():
    return analysis_service.portfolio()


def _ensure_exists(code: str) -> None:
    """校验基金存在。数据源不可用时返回 503，而不是误报 404。

    基金列表为空说明外部数据源失败；此时把"取不到数据"说成"基金不存在"
    会误导用户。两种情况必须区分。
    """
    funds = fund_service.list_all()
    if not funds:
        raise HTTPException(
            status_code=503,
            detail="基金列表数据暂时不可用，请稍后重试",
        )
    if not any(f.code == code for f in funds):
        raise HTTPException(status_code=404, detail=f"Fund {code} not found")
