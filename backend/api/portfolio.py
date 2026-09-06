"""持仓管理 REST API。"""

from fastapi import APIRouter, HTTPException

from models.portfolio import DripCreate, HoldingCreate, HoldingItem, PortfolioSummary, SellRequest
from services import portfolio_service

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioSummary)
def get_portfolio():
    return portfolio_service.portfolio_summary()


@router.get("/history")
def get_portfolio_history(period: str = "1M"):
    """资产历史快照。period: 1W / 1M / 3M / 1Y / ALL。"""
    points = portfolio_service.portfolio_history(period)
    return {"points": points}


@router.get("/attribution")
def get_portfolio_attribution():
    """收益归因：今日组合收益 + 每只基金贡献（含 summary 供 AI 复盘）。"""
    return portfolio_service.attribution()


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


@router.post("/auto-drip", status_code=201)
def auto_drip(data: DripCreate):
    """自动定投：按计划参数自动生成持仓记录。

    返回 {"created": 数量, "items": [HoldingItem], "skipped": [{date, reason}]}
    """
    return portfolio_service.auto_drip(data)


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
