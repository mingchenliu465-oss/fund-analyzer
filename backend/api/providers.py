from datetime import date, timedelta

from fastapi import APIRouter, Query

from models.provider import CrossSourceCheck, ProviderRegistryStatus
from services import market_data

router = APIRouter(prefix="/providers", tags=["data-providers"])


@router.get("/status", response_model=ProviderRegistryStatus)
def provider_status():
    """披露真实 Provider 状态；Blocked 不会被翻译成空数据或成功。"""
    return market_data.provider_registry_status()


@router.get("/cross-check/{ticker}", response_model=CrossSourceCheck)
def cross_check(
    ticker: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    """核验指数或 ETF 行情；iFinD 不可用时返回 blocked，不伪造第二来源。"""
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=30))
    return market_data.cross_source_check(ticker, start, end)
