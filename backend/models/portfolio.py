"""持仓与交易 Pydantic 模型。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class HoldingCreate(BaseModel):
    """新增持仓请求。"""
    fund_code: str
    fund_name: str
    fund_type: str = ""
    buy_date: str  # yyyy-mm-dd
    buy_amount: float = Field(gt=0, description="买入金额，必须大于 0")
    buy_nav: float = Field(gt=0, description="买入净值，必须大于 0")
    shares: float = Field(gt=0, description="买入份额，必须大于 0")
    fee: float = Field(default=0, ge=0)
    notes: str = ""


class SellRequest(BaseModel):
    """卖出请求。"""
    sell_date: str
    sell_amount: float = Field(gt=0, description="卖出金额，必须大于 0")
    sell_nav: float = Field(gt=0, description="卖出净值，必须大于 0")


class DripCreate(BaseModel):
    """自动定投计划请求。

    后端根据定投参数自动生成日期序列，从历史净值取每个定投日的净值，
    计算份额并批量创建持仓记录。
    """
    fund_code: str
    fund_name: str
    fund_type: str = ""
    amount: float = Field(gt=0, description="每次定投金额，必须大于 0")
    frequency: Literal["daily", "weekly", "monthly"] = Field(
        default="monthly", description="定投频率：daily / weekly / monthly"
    )
    start_date: str  # yyyy-mm-dd，定投起始日
    end_date: str  # yyyy-mm-dd，定投截止日
    day_of_week: int | None = Field(
        default=None,
        ge=1,
        le=31,
        description="周频为星期（1=周一、7=周日）；月频为日期（1..31）",
    )
    fee: float = Field(default=0, ge=0)
    notes: str = ""

    @model_validator(mode="after")
    def validate_schedule(self):
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError("start_date 和 end_date 必须为有效的 yyyy-mm-dd 日期") from exc
        if start > end:
            raise ValueError("start_date 不能晚于 end_date")
        if self.frequency == "weekly" and self.day_of_week not in range(1, 8):
            raise ValueError("weekly 的 day_of_week 必须为 1..7（1=周一、7=周日）")
        if self.frequency == "monthly" and self.day_of_week is not None and not 1 <= self.day_of_week <= 31:
            raise ValueError("monthly 的 day_of_week 必须为 1..31")
        return self


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
    # 净值状态：True 表示当前净值待更新（用了最近一次有效净值或买入净值兜底）
    nav_stale: bool = False


class PortfolioSummary(BaseModel):
    """组合概览。"""
    total_cost: float = 0
    total_value: float = 0
    total_profit: float = 0
    total_profit_pct: float = 0
    holding_count: int = 0
    holdings: list[HoldingItem] = []
    # 组合中至少一只持仓使用了过期/买入净值估值。
    has_stale_nav: bool = False
