from pydantic import BaseModel, ConfigDict, Field


class FundSummary(BaseModel):
    """基金列表项，与前端 FundSummary 对齐。"""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    company: str
    type: str
    nav: float
    change_pct: float = Field(alias="changePct")
    one_year_return: float = Field(alias="oneYearReturn")
    risk_level: str = Field(alias="riskLevel")
    size: str
    heat: int


class FundReturns(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    daily: float
    weekly: float
    monthly: float
    yearly: float


class FundMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    max_drawdown: float = Field(alias="maxDrawdown")
    volatility: float
    sharpe: float
    risk_level: str = Field(alias="riskLevel")
    risk_score: int = Field(alias="riskScore")
    alpha: float
    beta: float
    sortino: float
    information_ratio: float = Field(alias="informationRatio")


class Sector(BaseModel):
    name: str
    weight: float
    color: str


class TopHolding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    code: str | None = None
    weight: float
    change_pct: float = Field(alias="changePct")


class FundDetail(FundSummary):
    """基金详情，继承 FundSummary 并扩展。"""

    inception_date: str = Field(alias="inceptionDate")
    returns: FundReturns
    metrics: FundMetrics
    sectors: list[Sector]
    tags: list[str]
    description: str
    manager: str
    rating: int = Field(ge=1, le=5)
    top_holdings: list[TopHolding] = Field(alias="topHoldings")
    investment_style: str = Field(alias="investmentStyle")
