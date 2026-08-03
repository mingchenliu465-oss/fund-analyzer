"""持仓与交易 Pydantic 模型。"""

from pydantic import BaseModel, Field


class HoldingCreate(BaseModel):
    """新增持仓请求。"""
    fund_code: str
    fund_name: str
    fund_type: str = ""
    buy_date: str  # yyyy-mm-dd
    buy_amount: float  # 买入金额
    buy_nav: float  # 买入净值
    shares: float  # 买入份额
    fee: float = 0
    notes: str = ""


class SellRequest(BaseModel):
    """卖出请求。"""
    sell_date: str
    sell_amount: float
    sell_nav: float


class HoldingItem(BaseModel):
    """持仓记录。"""
    id: int
    fund_code: str
    fund_name: str
    fund_type: str
    buy_date: str
    buy_amount: float
    buy_nav: float
    shares: float
    fee: float
    notes: str
    is_sold: bool
    sell_date: str | None = None
    sell_amount: float | None = None
    sell_nav: float | None = None
    # 实时计算字段
    current_nav: float | None = None
    current_value: float | None = None
    cost: float | None = None
    profit: float | None = None
    profit_pct: float | None = None


class PortfolioSummary(BaseModel):
    """组合概览。"""
    total_cost: float = 0
    total_value: float = 0
    total_profit: float = 0
    total_profit_pct: float = 0
    holding_count: int = 0
    holdings: list[HoldingItem] = []
