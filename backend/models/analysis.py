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


class ConfidenceInterval(BaseModel):
    """统计量的 Bootstrap 置信区间。"""

    lower: float
    upper: float
    confidence: float = 0.95


class ReturnOutlier(BaseModel):
    """仅供复核的极端日收益；不会驱动任何数据删除。"""

    model_config = ConfigDict(populate_by_name=True)

    date: str
    return_pct: float = Field(alias="returnPct")
    modified_z_score: float = Field(alias="modifiedZScore")


class FundStatisticsAudit(BaseModel):
    """基金累计净值序列的数据质量与统计诊断。"""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    period: str
    status: str
    observations: int
    valid_returns: int = Field(alias="validReturns")
    duplicate_dates: int = Field(alias="duplicateDates")
    non_positive_navs: int = Field(alias="nonPositiveNavs")
    data_start: str | None = Field(alias="dataStart")
    data_end: str | None = Field(alias="dataEnd")
    outliers: list[ReturnOutlier]
    volatility_ci: ConfidenceInterval | None = Field(default=None, alias="volatilityCi")
    notes: list[str]


class PeerComparison(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    type: str
    one_year_return: float | None = Field(default=None, alias="oneYearReturn")
    volatility: float | None = None
    sharpe: float | None = None
    risk_level: str | None = Field(default=None, alias="riskLevel")


class ReturnRanking(BaseModel):
    rank: int
    total: int
    percentile: float | None = None


class AllocationItem(BaseModel):
    category: str
    weight: float
    color: str


class PortfolioOverview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_assets: float | None = Field(default=None, alias="totalAssets")
    today_return: float | None = Field(default=None, alias="todayReturn")
    today_return_pct: float | None = Field(default=None, alias="todayReturnPct")
    cumulative_return: float | None = Field(default=None, alias="cumulativeReturn")
    cumulative_return_pct: float | None = Field(default=None, alias="cumulativeReturnPct")
    allocation: list[AllocationItem]
    risk_level: str | None = Field(default=None, alias="riskLevel")
    risk_score: float | None = Field(default=None, alias="riskScore")


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
