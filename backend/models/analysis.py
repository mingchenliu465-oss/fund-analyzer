from pydantic import BaseModel, ConfigDict, Field


class FlowPeriod(BaseModel):
    label: str
    inflow: float
    outflow: float
    net: float
    trend: str


class FundFlow(BaseModel):
    code: str
    periods: list[FlowPeriod]


class AICommentary(BaseModel):
    performance: str
    risk_warning: str
    suitable_for: str
    suggestion: str


class PeerComparison(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    type: str
    one_year_return: float = Field(alias="oneYearReturn")
    volatility: float
    sharpe: float
    risk_level: str = Field(alias="riskLevel")


class ReturnRanking(BaseModel):
    rank: int
    total: int
    percentile: float


class AllocationItem(BaseModel):
    category: str
    weight: float
    color: str


class PortfolioOverview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_assets: float = Field(alias="totalAssets")
    today_return: float = Field(alias="todayReturn")
    today_return_pct: float = Field(alias="todayReturnPct")
    cumulative_return: float = Field(alias="cumulativeReturn")
    cumulative_return_pct: float = Field(alias="cumulativeReturnPct")
    allocation: list[AllocationItem]
    risk_level: str = Field(alias="riskLevel")
    risk_score: float = Field(alias="riskScore")
