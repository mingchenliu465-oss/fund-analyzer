"""持仓管理 REST API。"""

from fastapi import APIRouter, HTTPException

from models.portfolio import HoldingCreate, HoldingItem, PortfolioSummary, SellRequest
from services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioSummary)
def get_portfolio():
    return portfolio_service.portfolio_summary()


@router.get("/holdings", response_model=list[HoldingItem])
def list_holdings(include_sold: bool = False):
    return portfolio_service.list_holdings(include_sold=include_sold)


@router.get("/holdings/{holding_id}", response_model=HoldingItem)
def get_holding(holding_id: int):
    h = portfolio_service.get_holding(holding_id)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    return h


@router.post("/holdings", response_model=HoldingItem, status_code=201)
def create_holding(data: HoldingCreate):
    return portfolio_service.add_holding(data)


@router.put("/holdings/{holding_id}", response_model=HoldingItem)
def update_holding(holding_id: int, data: HoldingCreate):
    h = portfolio_service.update_holding(holding_id, data)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    return h


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int):
    if not portfolio_service.delete_holding(holding_id):
        raise HTTPException(status_code=404, detail="Holding not found")
    return {"ok": True}


@router.post("/holdings/{holding_id}/sell", response_model=HoldingItem)
def sell_holding(holding_id: int, data: SellRequest):
    h = portfolio_service.mark_sold(holding_id, data)
    if not h:
        raise HTTPException(status_code=404, detail="Holding not found")
    return h
