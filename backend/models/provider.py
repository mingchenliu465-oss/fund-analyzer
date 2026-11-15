from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ProviderStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    label: str
    status: str
    enabled: bool
    capabilities: list[str]
    detail: str


class ProviderRegistryStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    active_provider: str = Field(alias="activeProvider")
    providers: list[ProviderStatus]
    fund_accumulated_nav_status: str = Field(alias="fundAccumulatedNavStatus")
    fund_accumulated_nav_detail: str = Field(alias="fundAccumulatedNavDetail")
    generated_at: datetime = Field(alias="generatedAt")


class PriceDifference(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    primary_close: float = Field(alias="primaryClose")
    secondary_close: float = Field(alias="secondaryClose")
    difference: float
    difference_pct: float = Field(alias="differencePct")
    status: str


class CrossSourceCheck(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    start_date: date = Field(alias="startDate")
    end_date: date = Field(alias="endDate")
    status: str
    primary_source: str = Field(alias="primarySource")
    secondary_source: str = Field(alias="secondarySource")
    matched_samples: int = Field(alias="matchedSamples")
    primary_only_dates: int = Field(alias="primaryOnlyDates")
    secondary_only_dates: int = Field(alias="secondaryOnlyDates")
    max_difference_pct: float | None = Field(default=None, alias="maxDifferencePct")
    differences: list[PriceDifference]
    note: str
    generated_at: datetime = Field(alias="generatedAt")
