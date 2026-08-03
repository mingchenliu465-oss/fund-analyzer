from fastapi import APIRouter, HTTPException

from models.analysis import (
    AICommentary,
    FundFlow,
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


@router.get("/portfolio", response_model=PortfolioOverview)
def portfolio_overview():
    return analysis_service.portfolio()


def _ensure_exists(code: str) -> None:
    if not any(f.code == code for f in fund_service.list_all()):
        raise HTTPException(status_code=404, detail=f"Fund {code} not found")
