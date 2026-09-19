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


# 展示周期 → 天数。**必须是 NavPeriod 的完整映射**：新增枚举值时请同步这里，
# tests/test_period_mapping.py 会强制校验完整性，避免再出现"字典缺项 → 500"。
PERIOD_DAYS: dict[NavPeriod, int] = {
    NavPeriod.FIVE_DAY: 7,
    NavPeriod.TEN_DAY: 14,
    NavPeriod.TWENTY_DAY: 30,
    NavPeriod.DAILY: 60,
    NavPeriod.WEEKLY: 180,
    NavPeriod.MONTHLY: 730,
    NavPeriod.YEARLY: 1825,
    NavPeriod.ONE_MONTH: 30,
    NavPeriod.THREE_MONTH: 90,
    NavPeriod.SIX_MONTH: 180,
    NavPeriod.ONE_YEAR: 365,
    NavPeriod.THREE_YEAR: 1095,
}


def period_to_days(period: NavPeriod) -> int:
    """把展示周期换算为天数（唯一实现，供各路由/服务复用）。

    取不到时抛 ValueError（而不是裸 KeyError）：即使将来新增了枚举值，
    也会得到一条明确错误，并且完整性测试会先失败。
    """
    try:
        return PERIOD_DAYS[period]
    except KeyError:
        raise ValueError(f"不支持的周期: {period}") from None


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
    code: str
    name: str
    value: str
    change: float
    up: bool


class MarketStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    session: str
    update_time: str = Field(alias="updateTime")
