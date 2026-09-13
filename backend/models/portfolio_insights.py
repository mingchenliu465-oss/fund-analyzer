"""Portfolio insights response models.

The models intentionally expose data quality and availability fields.  A
missing market/holdings source must be visible to the caller instead of being
silently replaced with illustrative numbers.
"""

from pydantic import BaseModel, Field


class InsightHeadline(BaseModel):
    today_return: float = 0.0
    today_return_pct: float = 0.0
    sentence: str = "暂无持仓，无法生成组合洞察。"
    data_status: str = "empty"


class InsightContribution(BaseModel):
    fund_code: str
    fund_name: str
    fund_type: str = ""
    current_value: float = 0.0
    change_pct: float = 0.0
    contribution: float = 0.0
    contribution_rate: float = 0.0
    nav_stale: bool = False


class ReturnExplanation(BaseModel):
    contributions: list[InsightContribution] = Field(default_factory=list)
    top_gainers: list[InsightContribution] = Field(default_factory=list)
    top_draggers: list[InsightContribution] = Field(default_factory=list)
    positive_total: float = 0.0
    negative_total: float = 0.0
    stale_count: int = 0


class AllocationItem(BaseModel):
    category: str
    value: float = 0.0
    weight_pct: float = 0.0
    holding_count: int = 0


class MaxHolding(BaseModel):
    fund_code: str | None = None
    fund_name: str | None = None
    value: float = 0.0
    weight_pct: float = 0.0


class OverlapPair(BaseModel):
    fund_a: str
    fund_b: str
    shared_holdings: list[str] = Field(default_factory=list)
    overlap_pct: float = 0.0
    data_as_of: str | None = None


class RiskInsight(BaseModel):
    allocation: list[AllocationItem] = Field(default_factory=list)
    max_holding: MaxHolding = Field(default_factory=MaxHolding)
    concentration_ratio: float = 0.0
    hhi: float = 0.0
    concentration_level: str = "暂无"
    overlap_status: str = "unavailable"
    overlap_pairs: list[OverlapPair] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MarketComparison(BaseModel):
    code: str
    name: str
    portfolio_return_pct: float | None = None
    index_return_pct: float | None = None
    relative_return_pct: float | None = None
    available: bool = False
    reason: str | None = None


class HistoryPoint(BaseModel):
    date: str
    total_value: float
    profit: float
    day_change: float | None = None
    day_change_pct: float | None = None
    is_anomaly: bool = False


class HistoryInsight(BaseModel):
    points: list[HistoryPoint] = Field(default_factory=list)
    trend: str = "暂无"
    anomaly_detected: bool = False
    anomaly_date: str | None = None
    anomaly_reason: str | None = None
    data_sufficiency: str = "insufficient"
    note: str = "历史数据基于组合资产快照，未扣除期间现金流。"


class ReviewFact(BaseModel):
    key: str
    label: str
    value: str
    source: str


class PortfolioInsights(BaseModel):
    period: str = "1M"
    generated_at: str
    data_status: str = "empty"
    headline: InsightHeadline
    return_explanation: ReturnExplanation
    risk: RiskInsight
    market_comparison: list[MarketComparison] = Field(default_factory=list)
    history: HistoryInsight
    review_context: list[ReviewFact] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
