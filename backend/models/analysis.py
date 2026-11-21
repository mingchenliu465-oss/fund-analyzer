from enum import Enum

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


class ResearchPeriod(str, Enum):
    """研究页独立周期；不向旧 NavPeriod 添加值，避免破坏旧接口。"""

    ONE_MONTH = "1m"
    THREE_MONTH = "3m"
    SIX_MONTH = "6m"
    ONE_YEAR = "1y"
    THREE_YEAR = "3y"
    ALL = "all"


class OverviewMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period_return: float | None = Field(default=None, alias="periodReturn")
    volatility: float | None = None
    max_drawdown: float | None = Field(default=None, alias="maxDrawdown")
    sharpe: float | None = None


class OverviewCurvePoint(BaseModel):
    date: str
    fund: float
    benchmark: float | None = None


class BenchmarkComparison(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    status: str
    source: str
    period_return: float | None = Field(default=None, alias="periodReturn")
    matched_samples: int = Field(alias="matchedSamples")
    fund_only_dates: int = Field(alias="fundOnlyDates")
    benchmark_only_dates: int = Field(alias="benchmarkOnlyDates")
    note: str


class FundOverview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    period: ResearchPeriod
    data_start: str | None = Field(default=None, alias="dataStart")
    data_end: str | None = Field(default=None, alias="dataEnd")
    sample_count: int = Field(alias="sampleCount")
    metric_status: str = Field(alias="metricStatus")
    metrics: OverviewMetrics
    curve: list[OverviewCurvePoint]
    benchmark: BenchmarkComparison
    quality_status: str = Field(alias="qualityStatus")
    quality_notes: list[str] = Field(alias="qualityNotes")
    duplicate_dates: int = Field(alias="duplicateDates")
    invalid_nav_records: int = Field(alias="invalidNavRecords")
    source: str
    generated_at: str = Field(alias="generatedAt")


class CalendarReturn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    return_value: float | None = Field(default=None, alias="return")
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    observations: int
    is_partial: bool = Field(alias="isPartial")


class PerformanceMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period_return: float | None = Field(default=None, alias="periodReturn")
    annualized_return: float | None = Field(default=None, alias="annualizedReturn")
    benchmark_return: float | None = Field(default=None, alias="benchmarkReturn")
    excess_return: float | None = Field(default=None, alias="excessReturn")


class PerformancePeriod(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period: ResearchPeriod
    status: str
    sample_count: int = Field(alias="sampleCount")
    fund_return: float | None = Field(default=None, alias="fundReturn")
    annualized_return: float | None = Field(default=None, alias="annualizedReturn")
    benchmark_return: float | None = Field(default=None, alias="benchmarkReturn")
    excess_return: float | None = Field(default=None, alias="excessReturn")


class DataCoverage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    data_start: str | None = Field(default=None, alias="dataStart")
    data_end: str | None = Field(default=None, alias="dataEnd")
    sample_count: int = Field(alias="sampleCount")
    matched_samples: int = Field(alias="matchedSamples")
    quality_status: str = Field(alias="qualityStatus")


class FundPerformance(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    period: ResearchPeriod
    metric_status: str = Field(alias="metricStatus")
    metrics: PerformanceMetrics
    curve: list[OverviewCurvePoint]
    annual_returns: list[CalendarReturn] = Field(alias="annualReturns")
    monthly_returns: list[CalendarReturn] = Field(alias="monthlyReturns")
    period_comparisons: list[PerformancePeriod] = Field(alias="periodComparisons")
    coverage: DataCoverage
    source: str
    benchmark_source: str = Field(alias="benchmarkSource")
    generated_at: str = Field(alias="generatedAt")
    definitions: list[str]


class DrawdownDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    peak_date: str | None = Field(default=None, alias="peakDate")
    trough_date: str | None = Field(default=None, alias="troughDate")
    recovery_date: str | None = Field(default=None, alias="recoveryDate")
    drawdown_days: int | None = Field(default=None, alias="drawdownDays")
    recovery_days: int | None = Field(default=None, alias="recoveryDays")
    underwater_days: int | None = Field(default=None, alias="underwaterDays")
    recovery_status: str = Field(alias="recoveryStatus")


class RiskMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    volatility: float | None = None
    max_drawdown: float | None = Field(default=None, alias="maxDrawdown")
    sharpe: float | None = None
    downside_deviation: float | None = Field(default=None, alias="downsideDeviation")


class RiskPeriod(RiskMetrics):
    model_config = ConfigDict(populate_by_name=True)

    period: ResearchPeriod
    status: str
    sample_count: int = Field(alias="sampleCount")


class DrawdownCurvePoint(BaseModel):
    date: str
    fund: float
    benchmark: float | None = None


class FundRisk(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    period: ResearchPeriod
    metric_status: str = Field(alias="metricStatus")
    metrics: RiskMetrics
    benchmark_metrics: RiskMetrics = Field(alias="benchmarkMetrics")
    drawdown: DrawdownDetails
    drawdown_curve: list[DrawdownCurvePoint] = Field(alias="drawdownCurve")
    period_comparisons: list[RiskPeriod] = Field(alias="periodComparisons")
    data_start: str | None = Field(default=None, alias="dataStart")
    data_end: str | None = Field(default=None, alias="dataEnd")
    sample_count: int = Field(alias="sampleCount")
    source: str
    benchmark_source: str = Field(alias="benchmarkSource")
    generated_at: str = Field(alias="generatedAt")
    definitions: list[str]