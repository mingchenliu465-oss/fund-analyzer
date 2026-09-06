from fastapi import APIRouter, Query

from models.market import KlinePoint, MarketIndex, MarketStatus, NavPeriod
from services import market_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/kline", response_model=list[KlinePoint])
def kline(
    code: str = Query(..., description="基金或 ETF 代码"),
    period: NavPeriod = Query(default=NavPeriod.ONE_YEAR, description="K线聚合周期（日K/周K/月K，兼容旧值）"),
    range: str = Query(default="1Y", alias="range", description="时间范围：1M/3M/6M/1Y/3Y"),
):
    return market_service.kline(code, period, range)


@router.get("/indices", response_model=list[MarketIndex])
def market_indices():
    return market_service.indices()


@router.get("/indices/{code}/kline", response_model=list[KlinePoint])
def market_index_kline(
    code: str,
    period: NavPeriod = Query(default=NavPeriod.DAILY, description="K线聚合周期（日K/周K/月K）"),
):
    return market_service.index_kline(code, period)


@router.get("/status", response_model=MarketStatus)
def market_status():
    return market_service.status()
