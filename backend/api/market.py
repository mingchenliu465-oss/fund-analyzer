from fastapi import APIRouter, Query

from models.market import KlinePoint, MarketIndex, MarketStatus, NavPeriod
from services import market_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/kline", response_model=list[KlinePoint])
def kline(
    code: str = Query(..., description="基金或 ETF 代码"),
    period: NavPeriod = Query(default=NavPeriod.ONE_YEAR, description="K线周期"),
):
    return market_service.kline(code, period)


@router.get("/indices", response_model=list[MarketIndex])
def market_indices():
    return market_service.indices()


@router.get("/status", response_model=MarketStatus)
def market_status():
    return market_service.status()
