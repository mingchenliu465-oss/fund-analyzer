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


class HoldStructurePoint(BaseModel):
    """单个时间点的全市场持有人结构数据。"""
    model_config = ConfigDict(populate_by_name=True)

    date: str
    fund_count: int = Field(alias="fundCount")
    institution_pct: float = Field(alias="institutionPct")
    individual_pct: float = Field(alias="individualPct")
    internal_pct: float = Field(alias="internalPct")
    total_shares: float = Field(alias="totalShares")


class HoldStructure(BaseModel):
    """全市场机构/个人持有比例趋势（非单只基金数据）。"""
    points: list[HoldStructurePoint]
    note: str  # 说明这是全市场数据
