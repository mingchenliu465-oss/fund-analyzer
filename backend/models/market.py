from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class NavPeriod(str, Enum):
    # 新增专业周期
    FIVE_DAY = "5D"
    TEN_DAY = "10D"
    TWENTY_DAY = "20D"
    DAILY = "日K"
    WEEKLY = "周K"
    MONTHLY = "月K"
    YEARLY = "年K"
    # 保留旧值，向后兼容
    ONE_MONTH = "1M"
    THREE_MONTH = "3M"
    SIX_MONTH = "6M"
    ONE_YEAR = "1Y"
    THREE_YEAR = "3Y"


class KlinePoint(BaseModel):
    """K 线点，与前端 KlinePoint 对齐。volume/turnover 仅 ETF 有值。"""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    turnover: float | None = None


class NavPoint(BaseModel):
    date: str
    nav: float
    normalized: float


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float


class MarketIndex(BaseModel):
    name: str
    value: str
    change: float
    up: bool


class MarketStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    session: str
    update_time: str = Field(alias="updateTime")
