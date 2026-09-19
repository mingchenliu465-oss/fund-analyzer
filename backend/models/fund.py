from pydantic import BaseModel, ConfigDict, Field


class FundSummary(BaseModel):
    """基金列表项，与前端 FundSummary 对齐。"""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    name: str
    company: str
    type: str
    nav: float | None = None
    # 该 nav 的**真实观测日**（净值日期 / 行情日期）。没有它，nav 就无法被
    # 正确解读为"最近一次披露值"而不是"当前值"。
    nav_date: str | None = Field(default=None, alias="navDate")
    # 新鲜度状态：fresh / stale / inactive / unavailable / unknown。
    # 见 fund_service.nav_data_status 的状态模型。
    nav_status: str | None = Field(default=None, alias="navStatus")
    change_pct: float | None = Field(default=None, alias="changePct")
    one_year_return: float | None = Field(default=None, alias="oneYearReturn")
    risk_level: str | None = Field(default=None, alias="riskLevel")
    size: str
    heat: int | None = None


class FundReturns(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    daily: float | None = None
    weekly: float | None = None
    monthly: float | None = None
    yearly: float | None = None


class FundMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    max_drawdown: float = Field(alias="maxDrawdown")
    volatility: float
    # 分母为 0（收益序列方差为 0）时夏普无定义 -> None，不得写成 0。
    sharpe: float | None = None
    # 风险等级只由**真实年化波动率**推导；波动率不可用时为 None。
    # 绝不再按基金类型查表。
    risk_level: str | None = Field(default=None, alias="riskLevel")
    # 综合风险评分没有可复现的数学定义（无输入指标、无权重、无阈值依据），
    # 因此始终为 None。真实风险信息由 volatility / max_drawdown / sharpe 承载。
    risk_score: int | None = Field(default=None, alias="riskScore")
    # These metrics require a benchmark/downside definition.  Until those
    # inputs are available, null is the only truthful value.
    alpha: float | None = None
    beta: float | None = None
    sortino: float | None = None
    information_ratio: float | None = Field(default=None, alias="informationRatio")


class Sector(BaseModel):
    name: str
    weight: float
    color: str


class TopHolding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    code: str | None = None
    weight: float
    change_pct: float | None = Field(default=None, alias="changePct")
    asset_type: str | None = Field(default=None, alias="assetType")


class FundDetail(FundSummary):
    """基金详情，继承 FundSummary 并扩展。"""

    inception_date: str = Field(alias="inceptionDate")
    returns: FundReturns
    metrics: FundMetrics
    sectors: list[Sector]
    tags: list[str]
    description: str
    manager: str
    manager_days: int | None = Field(default=None, alias="managerDays")
    rating: int | None = Field(default=None, ge=1, le=5)
    top_holdings: list[TopHolding] = Field(alias="topHoldings")
    investment_style: str | None = Field(default=None, alias="investmentStyle")
    holdings_as_of: str | None = Field(default=None, alias="holdingsAsOf")
    sectors_as_of: str | None = Field(default=None, alias="sectorsAsOf")
